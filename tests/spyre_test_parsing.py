"""
YAML config parsing and op_db filtering for the Spyre PyTorch test framework.

Responsibilities:
  - load_yaml_config: read raw YAML
  - resolve_rel_path: expand ${PYTORCH} / ${TORCH_SPYRE} tokens
  - resolve_current_file: match a YAML file entry against cwd
  - parse_global_unsupported_dtypes: read global.unsupported_dtypes
  - parse_tests: parse allow_list / block_list into typed dicts
  - filter_op_db: monkey-patch pytorch op_db lists to supported_ops subset

No pytest imports, no SpyreTestBase references.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import torch
import yaml

from spyre_test_constants import (
    DEFAULT_UNSUPPORTED_DTYPES,
    MODE_MANDATORY_PASS,
    MODE_XFAIL,
    MODE_XFAIL_STRICT,
    OP_DB_ATTRS,
    REL_PATH_TOKENS,
    ENV_TEST_CONFIG,
)
from spyre_test_matching import parse_dtype


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def load_yaml_config(path: str) -> dict:
    """Load and return the raw YAML config dict from *path*."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Spyre config file not found: {config_path}")
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_rel_path(rel_path: str) -> str:
    """Expand ${PYTORCH} and ${TORCH_SPYRE} tokens in *rel_path* using env vars.

    Token -> env var mapping is defined in REL_PATH_TOKENS (spyre_test_constants).

    Example:
        ${PYTORCH}/test/test_binary_ufuncs.py
        -> $SPYRE_PYTORCH_ROOT/test/test_binary_ufuncs.py
    """
    for token, env_var in REL_PATH_TOKENS:
        if token in rel_path:
            root = os.environ.get(env_var)
            if not root:
                raise EnvironmentError(
                    f"rel_path contains {token!r} but ${env_var} env var is not set."
                )
            rel_path = rel_path.replace(token, root)
    return rel_path


def resolve_current_file(data: dict, config_path: str) -> str:
    """Match a YAML file entry against the current working directory.

    pytest is always invoked from pytorch/test/, so we find the entry
    whose resolved rel_path lives in cwd.  Raises EnvironmentError if
    no match is found (wrong directory or missing YAML entry).
    """
    cwd = os.path.abspath(os.getcwd())
    for file_entry in data.get("tests", {}).get("files", []):
        resolved = os.path.abspath(resolve_rel_path(file_entry["rel_path"]))
        if os.path.dirname(resolved) == cwd:
            return resolved
    raise EnvironmentError(
        f"No rel_path in {config_path!r} matches the current working directory {cwd!r}.\n"
        f"Make sure you are running pytest from the pytorch/test/ directory and that "
        f"the YAML has an entry for the test file you are running."
    )


# ---------------------------------------------------------------------------
# Global section parsers
# ---------------------------------------------------------------------------

def parse_global_unsupported_dtypes(data: dict) -> Set[torch.dtype]:
    """Parse tests.global.unsupported_dtypes.

    Falls back to DEFAULT_UNSUPPORTED_DTYPES when the key is absent.
    Per-test edits.unsupported_dtypes takes precedence over this at runtime.
    """
    global_cfg = data.get("tests", {}).get("global", {})
    if "unsupported_dtypes" in global_cfg:
        return {parse_dtype(dt) for dt in global_cfg["unsupported_dtypes"]}
    return DEFAULT_UNSUPPORTED_DTYPES.copy()


def parse_global_supported_ops(data: dict) -> Optional[Set[str]]:
    """Parse tests.global.supported_ops.

    Returns a set of op name strings if present, or None if the key is absent
    (meaning: no op filtering requested).
    """
    global_cfg = data.get("tests", {}).get("global", {})
    ops = global_cfg.get("supported_ops")
    if ops is None:
        return None
    return set(ops)


# ---------------------------------------------------------------------------
# op_db monkey-patching
# ---------------------------------------------------------------------------

def filter_op_db(supported_ops: Set[str]) -> None:
    """Restrict pytorch op_db lists to *supported_ops* in-place.

    Mutates the module-level lists in common_methods_invocations so that
    the @ops decorator only sees the ops we support.  Must be called before
    test collection (i.e. at module load time, not inside a test).

    Only attrs that exist and are plain lists are patched -- future pytorch
    refactors that make them lazy/properties will be caught by the assertion.

    Args:
        supported_ops: set of op name strings, e.g. {'add', 'mul'}.
                       If empty, raises ValueError -- likely a config mistake.
    """
    if not supported_ops:
        raise ValueError(
            "supported_ops is empty -- this would skip all ops. "
            "Remove the key from the YAML to run all ops, or add at least one op name."
        )

    import torch.testing._internal.common_methods_invocations as _cmi  # lazy: avoid circular import

    for attr in OP_DB_ATTRS:
        lst = getattr(_cmi, attr, None)
        if lst is None:
            continue 
        assert isinstance(lst, list), (
            f"pytorch's {attr!r} is no longer a plain list "
            f"-- op_db filtering needs revisiting (got {type(lst)})."
        )
        lst[:] = [op for op in lst if op.name in supported_ops]


# ---------------------------------------------------------------------------
# Test list parser
# ---------------------------------------------------------------------------

def parse_test_id(test_id: str) -> Tuple[str, str]:
    """Parse 'ClassName::method_name' into (class_name, method_name)."""
    parts = test_id.split("::")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid test id {test_id!r}, expected 'ClassName::method_name'"
        )
    return parts[0], parts[1]


def parse_tests(data: dict, current_file: str) -> Tuple[
    Dict[str, set],   # WHITELISTED_TESTS         {class_name -> set of method names}
    Dict[str, set],   # BLACKLISTED_TESTS          {class_name -> set of method names}
    Dict[str, set],   # XFAIL_TESTS               {class_name -> set of (method, strict)}
    Dict[str, set],   # EXTRA_ALLOWED_DTYPES       {method -> set of torch.dtype}
    Dict[str, float], # PRECISION_OVERRIDES        {method -> float}
    Dict[str, set],   # PER_TEST_UNSUPPORTED_DTYPES{method -> set of torch.dtype}
    Dict[str, List],  # TEST_TAGS                  {method -> [tag, ...]}
]:
    """Parse allow_list and block_list for the file entry matching *current_file*.

    Only the entry whose resolved rel_path matches *current_file* is processed;
    all other file entries in the YAML are ignored.
    """
    whitelisted: Dict[str, set] = {}
    blacklisted: Dict[str, set] = {}
    xfail: Dict[str, set] = {}
    extra_dtypes: Dict[str, set] = {}
    precision_overrides: Dict[str, float] = {}
    per_test_unsupported: Dict[str, set] = {}
    test_tags: Dict[str, List] = {}

    for file_entry in data.get("tests", {}).get("files", []):
        if os.path.abspath(resolve_rel_path(file_entry["rel_path"])) != current_file:
            continue

        # ── allow_list ───────────────────────────────────────────────
        for entry in file_entry.get("allow_list", []):
            class_name, method_name = parse_test_id(entry["test"])
            whitelisted.setdefault(class_name, set()).add(method_name)
            test_tags[method_name] = entry.get("tags", [])

            mode = entry.get("mode", MODE_MANDATORY_PASS)
            if mode in (MODE_XFAIL, MODE_XFAIL_STRICT):
                strict = mode == MODE_XFAIL_STRICT
                xfail.setdefault(class_name, set()).add((method_name, strict))

            edits = entry.get("edits", {}) or {}
            if "extra_allowed_dtypes" in edits:
                extra_dtypes[method_name] = {
                    parse_dtype(dt) for dt in edits["extra_allowed_dtypes"]
                }
            if "precision_override" in edits:
                precision_overrides[method_name] = float(edits["precision_override"])
            if "unsupported_dtypes" in edits:
                per_test_unsupported[method_name] = {
                    parse_dtype(dt) for dt in edits["unsupported_dtypes"]
                }

        # ── block_list ───────────────────────────────────────────────
        for entry in file_entry.get("block_list", []):
            class_name, method_name = parse_test_id(entry["test"])
            blacklisted.setdefault(class_name, set()).add(method_name)

    return (
        whitelisted,
        blacklisted,
        xfail,
        extra_dtypes,
        precision_overrides,
        per_test_unsupported,
        test_tags,
    )