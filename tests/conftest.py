# Copyright 2025 The Torch-Spyre Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from pathlib import Path
import yaml
import pytest


import shared_config
from oot_test_utilities import _RUNTIME_TAGS


# Attaches per-test tags to the pytest report object after each test call.
# Tags come from _RUNTIME_TAGS (set by print_test_tags_oot during test execution,
# includes per-occurrence op tags) with fallback to _spyre_method_tags
# (set at collection time, includes test-level + dynamic op__/dtype__ markers).
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if call.when == "call":
        method_name = getattr(item, "originalname", None) or item.name
        tags = _RUNTIME_TAGS.get(method_name, [])
        if not tags:
            fn = getattr(item, "function", None) or getattr(item, "obj", None)
            tags = getattr(fn, "_spyre_method_tags", [])
        if tags:
            # Store on report for use in logreport hook
            rep._spyre_tags = tags


# Prints [TAGS = ...] for every test alongside the result line.
# Uses os.write(1, ...) to write directly to stdout fd, bypassing pytest's output
# capture visible without -s. Fires after pytest_runtest_makereport so tags
# are already attached to the report.
def pytest_runtest_logreport(report):
    if report.when == "call":
        tags = getattr(report, "_spyre_tags", None)
        if tags:
            # Write directly to terminal
            os.write(1, f"  [TAGS = {' '.join(tags)}]\n".encode())


def _get_case_marks(case: dict) -> set[str]:
    """
    Support either:
      marks: paddedtensor
      marks: [paddedtensor, fpoperation]
    """
    marks = set()
    m = case.get("marks")
    if isinstance(m, str) and m.strip():
        marks.add(m.strip())

    ms = case.get("marks")
    if isinstance(ms, (list, tuple)):
        for x in ms:
            if isinstance(x, str) and x.strip():
                marks.add(x.strip())

    return marks


# ---------------------------------------------------------------------------
# Parallel card support (pytest-xdist)
#
# When pytest is invoked with -nN (N xdist workers) each worker needs to
# claim a distinct Spyre card.  Card assignment is baked in at process startup
# via ibm-aiu-setup.sh, so we must re-source it with the correct
# AIU_DEVICE_INDEX before any torch import happens.
#
# How it works:
#   Controller side  (pytest_configure_node):
#     Stamps each worker's input channel with its integer card index
#     (0 for gw0, 1 for gw1, ...) before the worker process starts.
#
#   Worker side  (pytest_sessionstart):
#     Detects the workerinput dict injected by xdist, reads spyre_card_index,
#     sources ibm-aiu-setup.sh with AIU_DEVICE_INDEX=N via a subprocess, and
#     applies the resulting environment variables to os.environ so that the
#     subsequent torch import binds to the correct card.
#
# The SPYRE_PARALLEL_CARDS env var (set by run_test.sh --parallel-cards) gates
# this logic so it is a no-op in all non-parallel runs.
# ---------------------------------------------------------------------------


def _apply_aiu_setup_for_card(card_index: int) -> None:
    """
    Source ibm-aiu-setup.sh with AIU_DEVICE_INDEX=<card_index> in a subprocess,
    then apply every env var it exports into the current process's os.environ.

    This must be called before any torch import in the worker process.
    """
    import subprocess

    aiu_setup = "/etc/profile.d/ibm-aiu-setup.sh"
    if not os.path.isfile(aiu_setup):
        # Not on an AIU runner -- skip silently
        return

    # Slice the Nth PCI address out of the full comma-separated list so
    # ibm-aiu-setup.sh sees only one device and binds to it exclusively.
    pci_all = os.environ.get("PCIDEVICE_IBM_COM_AIU_PF", "")
    pci_list = [p.strip() for p in pci_all.split(",") if p.strip()]
    if pci_list:
        if card_index >= len(pci_list):
            print(
                f"[spyre_parallel] WARNING: card_index {card_index} out of range "
                f"({len(pci_list)} cards available), using card 0",
                flush=True,
            )
            card_index = 0
        pci_for_worker = pci_list[card_index]
    else:
        pci_for_worker = ""

    # Set PCIDEVICE_IBM_COM_AIU_PF to only this worker's card BEFORE sourcing
    # the setup script, so the C++ runtime never sees the other cards' addresses.
    if pci_for_worker:
        os.environ["PCIDEVICE_IBM_COM_AIU_PF"] = pci_for_worker
        print(
            f"[spyre_parallel] Worker {card_index} assigned PCI device: {pci_for_worker}",
            flush=True,
        )

    script = (
        f"AIU_DEVICE_INDEX={card_index} "
        + (f"PCIDEVICE_IBM_COM_AIU_PF={pci_for_worker} " if pci_for_worker else "")
        + f"source {aiu_setup} 2>/dev/null; env"
    )

    # Source the setup script with the desired card index and print the
    # resulting environment.  We capture env-only lines (KEY=VALUE) by
    # diffing against a baseline env dump so we pick up only what the script
    # adds or changes.
    # script = f"AIU_DEVICE_INDEX={card_index} source {aiu_setup} 2>/dev/null; env"
    try:
        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:
        print(
            f"[spyre_parallel] WARNING: could not source {aiu_setup} "
            f"for card {card_index}: {exc}",
            flush=True,
        )
        return

    if result.returncode != 0:
        print(
            f"[spyre_parallel] WARNING: ibm-aiu-setup.sh exited "
            f"{result.returncode} for card {card_index}",
            flush=True,
        )

    # Parse KEY=VALUE lines from the subprocess env dump and apply them.
    # Skip vars that are internal to bash or already set identically so we
    # don't mess up things like PATH that were correctly set by the runner.
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        # Only propagate AIU-related vars to avoid unintended side effects.
        if (
            key.startswith("AIU")
            or key.startswith("SPYRE")
            or key.startswith("DT")
            or key.startswith("PCIDEVICE")
        ):
            os.environ[key] = val

    print(
        f"[spyre_parallel] Worker bound to Spyre card {card_index} "
        f"(AIU_DEVICE_INDEX={card_index})",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Controller-side hook: runs in the main pytest process before each xdist
# worker process is spawned.  Injects the card index into the worker's input
# channel so the worker can read it from config.workerinput at startup.
# ---------------------------------------------------------------------------
def pytest_configure_node(node) -> None:
    """Inject spyre_card_index into each xdist worker before it starts."""
    if not os.environ.get("SPYRE_PARALLEL_CARDS"):
        return
    worker_id = getattr(node, "workerid", "gw0")
    try:
        card_index = int(worker_id.lstrip("gw"))
    except ValueError:
        card_index = 0
    node.workerinput["spyre_card_index"] = card_index

    # Also pass the specific PCI address for this worker through workerinput
    # so the worker can apply it before torch_spyre._C is ever imported.
    pci_all = os.environ.get("PCIDEVICE_IBM_COM_AIU_PF", "")
    pci_list = [p.strip() for p in pci_all.split(",") if p.strip()]
    if pci_list and card_index < len(pci_list):
        node.workerinput["spyre_pci_device"] = pci_list[card_index]
    elif pci_list:
        node.workerinput["spyre_pci_device"] = pci_list[0]


def pytest_sessionstart(session):
    """
    Called after the Session object has been created and
    before performing collection and entering the run test loop.
    """

    if os.environ.get("SPYRE_PARALLEL_CARDS"):
        worker_input = getattr(session.config, "workerinput", None)
        if worker_input is not None:
            card_index = worker_input.get("spyre_card_index", 0)
            # Apply PCI device restriction immediately — before any import
            # that might trigger torch_spyre._C.start_runtime().
            pci_device = worker_input.get("spyre_pci_device", "")
            if pci_device:
                os.environ["PCIDEVICE_IBM_COM_AIU_PF"] = pci_device
            _apply_aiu_setup_for_card(card_index)

    # avoid circular imports when using xdist
    import torch  # noqa: F401

    os.environ.setdefault("DTLOG_LEVEL", "error")
    os.environ.setdefault("DT_DEEPRT_VERBOSE", "-1")

    cfg = session.config
    root = cfg.rootpath

    selected = set(cfg.getoption("--model") or [])

    if cfg.getoption("--list-models"):
        models = sorted({m for (m, _, __, ___, _case) in _iter_yaml_cases(root)})
        for m in models:
            print(m)
        pytest.exit("listed models", returncode=0)

    if cfg.getoption("--list-cases"):
        for model, name, op, p, _case in _iter_yaml_cases(root):
            if selected and model not in selected:
                continue
            print(f"{model}::{name}::{op}  ({p})")
        pytest.exit("listed cases", returncode=0)

    opt = cfg.getoption("--list-cases-by-mark")
    if opt is not None:
        if opt == "__USE_PYTEST_M__":
            # This is the *effective* -m expression after addopts + CLI parsing.
            expr = (cfg.option.markexpr or "").strip()
            # If no -m anywhere, treat as "select all"
            if not expr:
                expr = "True"
        else:
            expr = opt.strip()
        from _pytest.mark.expression import Expression

        compiled = Expression.compile(expr)

        show_excluded = cfg.getoption("--show-excluded")
        chosen = []
        excluded = []

        def case_selected(case: dict) -> bool:
            marks = _get_case_marks(case)  # set[str]
            return compiled.evaluate(lambda m: m in marks)

        for model, name, op, p, case in _iter_yaml_cases(root):
            if selected and model not in selected:
                continue

            rec = f"{model}::{name}::{op}  ({p})"
            if case_selected(case):
                chosen.append(rec)
            else:
                excluded.append(rec)

        if show_excluded:
            for r in excluded:
                print(r)
            pytest.exit(f"listed excluded cases by mark (NOT {expr})", returncode=0)
        else:
            for r in chosen:
                print(r)
            pytest.exit(f"listed selected cases by mark ({expr})", returncode=0)


def pytest_addoption(parser):
    parser.addoption(
        "--model",
        action="append",
        default=[],
        help="Run only these models (repeatable). Example: --model granite3-speech",
    )
    parser.addoption(
        "--dedupe",
        dest="dedupe",
        action="store_true",
        default=True,  # default ON
        help="Skip duplicate op+input signatures across models (runtime).",
    )
    parser.addoption(
        "--no-dedupe",
        action="store_false",
        dest="dedupe",
        help="Disable deduplication.",
    )
    parser.addoption(
        "--no-device-replace",
        action="store_true",
        help="Disable cuda device replacement in kwargs.",
    )

    # NEW: inventory modes
    parser.addoption(
        "--list-models",
        action="store_true",
        default=False,
        help="List models found in tests/resource/models/*.yaml and exit.",
    )
    parser.addoption(
        "--list-cases",
        action="store_true",
        default=False,
        help="List cases found in tests/resource/models/*.yaml and exit. Use --model to filter.",
    )
    parser.addoption(
        "--compile-backend",
        action="store",
        default=os.environ.get("TEST_COMPILE_BACKEND", "inductor"),
        help="If set, run test via torch.compile(..., backend=...).",
    )
    group = parser.getgroup("yaml-cases")
    group.addoption(
        "--list-cases-by-mark",
        action="store",
        const="__USE_PYTEST_M__",
        default=None,
        nargs="?",
        metavar="EXPR",
        help=(
            "List YAML test cases whose mark(s) match a pytest -m style expression. "
            "Examples: paddedtensor | 'paddedtensor and not fpoperation'"
            "If EXPR is omitted, uses the effective pytest -m expression (including pytest.ini addopts)."
        ),
    )
    group.addoption(
        "--show-excluded",
        action="store_true",
        default=False,
        help="With --list-cases-by-mark, list cases excluded by the mark expression (i.e., NOT matching).",
    )
    group.addoption(
        "--show-skipped",
        action="store_true",
        default=False,
        help="List cases skipped by model filtering or duplications",
    )
    parser.addoption(
        "--test-name",
        action="append",
        default=[],
        help="Run only tests matching these test names",
    )


def _models_dir(rootpath: Path) -> Path:
    return rootpath / "tests" / "resource" / "models"


def load_yaml_or_fail(path: Path) -> dict:
    text = path.read_text()
    try:
        data = yaml.safe_load(text)
        if data is None:
            raise pytest.UsageError(f"{path}: YAML is empty")
        return data
    except yaml.YAMLError as e:
        # Build a nice error message with file + location + snippet
        msg = [f"Invalid YAML in {path}"]

        mark = getattr(e, "problem_mark", None)
        if mark is not None:
            # PyYAML lines are 0-based internally; show 1-based to humans
            line = mark.line + 1
            col = mark.column + 1
            msg.append(f"Location: line {line}, column {col}")

            lines = text.splitlines()
            start = max(0, mark.line - 2)
            end = min(len(lines), mark.line + 3)

            msg.append("Context:")
            for i in range(start, end):
                prefix = ">>" if i == mark.line else "  "
                msg.append(f"{prefix} {i + 1:4d}: {lines[i]}")
                if i == mark.line:
                    msg.append(f"     {' ' * (col - 1)}^")

        # Include the underlying YAML error message too
        msg.append(f"YAML error: {e}")

        # Fail pytest configuration cleanly (instead of INTERNALERROR)
        raise pytest.UsageError("\n".join(msg)) from e


def _iter_yaml_cases(rootpath: Path):
    """
    Yields tuples: (model, case_name, op_name, yaml_path, case)
    Supports either:
      - per-case 'op'
      - or top-level 'op' applied to cases that don't specify 'op'
    """
    for p in sorted(_models_dir(rootpath).glob("*.yaml")):
        if p.name.endswith("template.yaml"):  # skip template.yaml file
            continue
        spec = load_yaml_or_fail(p)
        model = spec.get("model", p.stem)
        top_op = spec.get("op", None)
        for case in spec.get("cases", []):
            op = case.get("op", top_op)
            name = case.get("name", op or "<unnamed>")
            yield model, name, op, p, case


@pytest.fixture(scope="session")
def selected_models(pytestconfig):
    return set(pytestconfig.getoption("--model") or [])


@pytest.fixture(scope="session")
def dedupe_enabled(pytestconfig):
    return bool(pytestconfig.getoption("dedupe"))


@pytest.fixture(scope="session")
def test_device_str(pytestconfig):
    return "spyre"


@pytest.fixture(scope="session")
def seen_case_keys():
    # track which case has been run to avoid rerun again
    return set()


@pytest.fixture(scope="session")
def compile_backend(pytestconfig):
    s = str(pytestconfig.getoption("--compile-backend") or "").strip()
    return s or None


def pytest_configure(config):
    shared_config._PYTEST_CONFIG = config

    config.addinivalue_line(
        "markers",
        "requires_spyre_profiler: test requires Spyre hardware "
        "and USE_SPYRE_PROFILER=1",
    )
    # auto-register model_<name> markers based on YAML files
    mdir = config.rootpath / "tests" / "resource" / "models"
    for p in mdir.glob("*.yaml"):
        spec = load_yaml_or_fail(p)
        model = spec.get("model", p.stem)
        mark = "model_" + "".join(
            ch if ch.isalnum() or ch == "_" else "_" for ch in model
        )
        config.addinivalue_line(
            "markers", f"{mark}: auto-generated mark for model {model}"
        )

    # ── register upstream test tags from PYTORCH_TEST_CONFIG YAML ──
    # Tags defined under test_suite_config.files[].tests[].tags are registered
    # here so pytest does not emit PytestUnknownMarkWarning.
    # Each tag becomes a pytest mark usable with -m for test selection:
    #   pytest test_binary_ufuncs.py -m "model_1"
    #   pytest test_ops.py -m "model_2"
    yaml_path = os.environ.get("PYTORCH_TEST_CONFIG")
    if yaml_path and Path(yaml_path).exists():
        with open(yaml_path) as f:
            raw = yaml.safe_load(f) or {}
        tags: set = set()
        for file_entry in raw.get("test_suite_config", {}).get("files", []):
            for test_entry in file_entry.get("tests", []):
                for tag in test_entry.get("tags", []):
                    tags.add(tag)
        for tag in sorted(tags):
            config.addinivalue_line(
                "markers",
                f"{tag}: tests that depend on or are relevant to '{tag}'",
            )


def pytest_collection_modifyitems(config, items):
    # Files ignored for plain `pytest` runs (known failures outside `make tests`)
    # When run via run_test.sh / make tests, PYTORCH_TEST_CONFIG is set so skip the ignore.
    ignored_files = set()
    if not os.environ.get("PYTORCH_TEST_CONFIG"):
        ignored_files = {
            "tests/test_modules_custom.py",
        }

    selected_models = config.getoption("--model") or []
    if not selected_models:
        # Still deselect ignored files even without --model
        deselect = [
            i for i in items if any(i.nodeid.startswith(f) for f in ignored_files)
        ]
        if deselect:
            config.hook.pytest_deselected(items=deselect)
            items[:] = [i for i in items if i not in deselect]
        return

    # Keep only model-yaml runner tests
    keep = []
    deselect = []

    for item in items:
        if any(item.nodeid.startswith(f) for f in ignored_files):
            deselect.append(item)
        # item.nodeid includes the file path, e.g. "tests/models/test_model_ops.py::test_model_ops[...]"
        # if "tests/models/test_model_ops.py::" in item.nodeid:
        elif "tests/models/test_model_ops" in item.nodeid:
            keep.append(item)
        else:
            deselect.append(item)

    if deselect:
        config.hook.pytest_deselected(items=deselect)
        items[:] = keep


def pytest_report_teststatus(report, config):
    if report.when != "call":
        return

    tags = getattr(report, "_spyre_tags", [])
    if len(tags) > 0:
        tags_str = " ".join(map(str, tags))
        tags_msg = f" [TAGS = {tags_str}]"
    else:
        tags_msg = ""

    if report.failed:
        return "failed", "F", f"FAILED{tags_msg}"
    if report.passed:
        return "passed", ".", f"PASSED{tags_msg}"
    if report.skipped:
        return "skipped", "s", "SKIPPED"
    return None


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not config.getoption("--show-skipped"):
        return
    skipped = terminalreporter.stats.get("skipped", [])
    if not skipped:
        return

    terminalreporter.section("Skipped tests (full list)")
    for rep in skipped:
        # terminalreporter.write_line(rep)
        terminalreporter.write_line(rep.nodeid)


def _is_spyre_hardware_available() -> bool:
    """
    Detect whether Spyre hardware is available.

    Returns True if the torch_spyre runtime and device can be initialized.
    This function is defensive and returns False if any step fails.
    """
    try:
        import torch

        x = torch.empty(1, device="spyre")
        return x.device.type == "spyre"
    except (ImportError, RuntimeError):
        return False


def pytest_runtest_setup(item: pytest.Item) -> None:
    """
    Automatically skip tests marked with @pytest.mark.requires_spyre_profiler
    when the Spyre profiler is not available.
    """
    if "requires_spyre_profiler" in item.keywords:
        use_profiler = os.environ.get("USE_SPYRE_PROFILER") == "1"
        hardware_available = _is_spyre_hardware_available()

        if not (use_profiler and hardware_available):
            pytest.skip(
                "Skipping test: requires Spyre profiler "
                "(set USE_SPYRE_PROFILER=1 and ensure Spyre hardware is available)"
            )
