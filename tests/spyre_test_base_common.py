"""
Shared class and methods for all Spyre PyTorch test overrides.

Each per-suite file (e.g. spyre_test_binaryfuncs.py) imports
SpyreTestBase from here and declares ALLOW_LIST_TESTS and/or BLOCK_LIST_TESTS
as class attributes.  A single environment variable selects which dict
is active at runtime.

# ENV VAR
SPYRE_PYTORCH_TEST_FILTER_TYPE=allow_list --> use tests from allow_list  (default when it exists)
SPYRE_PYTORCH_TEST_FILTER_TYPE=block_list --> skip tests from block_list (default when only that exists)

If a suite file defines BOTH dicts, set SPYRE_PYTORCH_TEST_FILTER_TYPE explicitly to
choose which one governs the run.  When only one dict is defined the
mode is inferred automatically and SPYRE_PYTORCH_TEST_FILTER_TYPE need not be set.

Usage:
    export PYTORCH_TESTING_DEVICE_ONLY_FOR="privateuse1"

    # Clone pytorch
    $DTI_PROJECT_ROOT/torch-spyre-docs/scripts/checkout-pytorch-src.sh

    export TORCH_TEST_DEVICES="$DTI_PROJECT_ROOT/torch-spyre/tests/spyre_test_base_common.py"
    export SPYRE_PYTORCH_TEST_FILTER_TYPE=allow_list  # or block_list
    export SPYRE_PYTORCH_TEST_CONFIG=tests/test_binary_ufuncs.yaml

    cd $DTI_PROJECT_ROOT/pytorch/test/
    python3 -m pytest test_binary_ufuncs.py -v
"""

import os
import unittest
from functools import wraps
from typing import Dict, List, Optional, Set

import pytest  # type: ignore
import torch

from spyre_test_constants import (
    DEFAULT_FLOATING_PRECISION,
    DEFAULT_UNSUPPORTED_DTYPES,
    ENV_FILTER_TYPE,
    ENV_TEST_CONFIG,
    MODE_ALLOW_LIST,
    MODE_BLOCK_LIST,
)
from spyre_test_matching import (
    MatchSet,
    build_match_sets,
    extract_dtype_from_name,
    parse_dtype,
)
from spyre_test_parsing import (
    FileEntry,
    SpyreTestConfig,
    filter_op_db,
    load_yaml_config,
    resolve_current_file,
)


# ---------------------------------------------------------------------------
# PrivateUse1TestBase filter
# ---------------------------------------------------------------------------
# TODO: figure out why this filter is needed - expected to use default PrivateUse1TestBase
def remove_builtin_privateuse1_test_base():
    """
    Remove built-in PrivateUse1TestBase from device_type_test_bases.

    This ensures only SpyreTestBase handles the privateuse1 device type,
    preventing nondeterministic overwrites when list(set(...)) randomizes order.

    Side effect: Modifies the global device_type_test_bases list in-place.

    TODO: investigate whether this filter will still be needed once the upstream
          PrivateUse1TestBase correctly defers to registered custom backends.
    """
    device_type_test_bases[:] = [  # type: ignore[name-defined] # noqa: F821
        b
        for b in device_type_test_bases  # type: ignore[name-defined] # noqa: F821
        if b is not PrivateUse1TestBase  # type: ignore[name-defined] # noqa: F821
    ]


# Call the filter function to apply the side effect
remove_builtin_privateuse1_test_base()


class _SpyreOnlyOnPatcher:
    """Patches @onlyOn decorated test methods to also allow privateuse1.

    @onlyOn stores its allowed device list in the closure of the wrapper
    it creates. We walk the __wrapped__ chain to find the onlyOn closure
    cell that holds a list of device strings and append 'privateuse1' to it
    in-place so the runtime check allows our device.
    """

    _PRIVATEUSE1 = "privateuse1"

    def __init__(self, test: object) -> None:
        self._underlying_fn = (
            test.__func__  # type: ignore[union-attr]
            if hasattr(test, "__func__")
            else test
        )

    def patch(self) -> None:
        """Walk the decorator stack and patch any @onlyOn closure found.

        Iterates the __wrapped__ chain layer by layer. For each layer,
        inspects closure cells for a list of strings — that is the onlyOn
        device_type list. Appends 'privateuse1' to it in-place so the
        runtime check allows our device.
        """
        current = self._underlying_fn
        while current is not None:
            cells = getattr(current, "__closure__", None) or ()
            for cell in cells:
                try:
                    val = cell.cell_contents
                except ValueError:
                    continue

                if (
                    isinstance(val, list)
                    and all(isinstance(d, str) for d in val)
                    and self._PRIVATEUSE1 not in val
                ):
                    val.append(self._PRIVATEUSE1)
                    return  # patched, done

            current = getattr(current, "__wrapped__", None)


# ---------------------------------------------------------------------------
# Dtype patcher
# ---------------------------------------------------------------------------


class _SpyreDtypePatcher:
    """Patches @ops allowed_dtypes on a bound test method before instantiation.

    Needed because upstream @ops(..., allowed_dtypes=(...)) restricts which dtype
    variants are generated -- dtypes absent here are never instantiated, so they
    cannot be added to the allow_list. We inject extra dtypes before
    super().instantiate_test() calls _parametrize_test.
    """

    def __init__(self, test, extra_dtypes: set):
        from torch.testing._internal.common_device_type import ops as _ops_cls

        # @ops instance lives at test.__func__.parametrize_fn.__self__
        underlying_fn = test.__func__ if hasattr(test, "__func__") else test
        p = getattr(underlying_fn, "parametrize_fn", None)
        self._ops_instance = (
            p.__self__
            if p is not None
            and hasattr(p, "__self__")
            and isinstance(p.__self__, _ops_cls)
            else None
        )
        self._extra_dtypes = extra_dtypes

    def patch(self) -> None:
        if (
            self._ops_instance is not None
            and self._ops_instance.allowed_dtypes is not None
        ):
            self._ops_instance.allowed_dtypes |= self._extra_dtypes


# ---------------------------------------------------------------------------
# Helpers to build internal dicts from typed FileEntry
# ---------------------------------------------------------------------------


def _build_allow_list_map(file_entry: FileEntry) -> Dict[str, set]:
    """Build {class_name -> set of method_names} from allow_list entries."""
    result: Dict[str, set] = {}
    for entry in file_entry.allow_list:
        result.setdefault(entry.class_name, set()).add(entry.method_name)
    return result


def _build_block_list_map(file_entry: FileEntry) -> Dict[str, set]:
    """Build {class_name -> set of method_names} from block_list entries."""
    result: Dict[str, set] = {}
    for entry in file_entry.block_list:
        result.setdefault(entry.class_name, set()).add(entry.method_name)
    return result


def _build_xfail_map(file_entry: FileEntry) -> Dict[str, set]:
    """Build {class_name -> set of (method_name, strict)} from allow_list xfail entries."""
    from spyre_test_constants import MODE_XFAIL, MODE_XFAIL_STRICT

    result: Dict[str, set] = {}
    for entry in file_entry.allow_list:
        if entry.mode in (MODE_XFAIL, MODE_XFAIL_STRICT):
            strict = entry.mode == MODE_XFAIL_STRICT
            result.setdefault(entry.class_name, set()).add((entry.method_name, strict))
    return result


def _build_extra_dtypes_map(file_entry: FileEntry) -> Dict[str, set]:
    """Build {method_name -> set of torch.dtype} from allow_list edits."""
    return {
        entry.method_name: entry.edits.resolved_extra_allowed_dtypes()
        for entry in file_entry.allow_list
        if entry.edits.extra_allowed_dtypes
    }


def _build_precision_overrides_map(file_entry: FileEntry) -> Dict[str, float]:
    """Build {method_name -> float} from allow_list edits."""
    return {
        entry.method_name: entry.edits.precision_override
        for entry in file_entry.allow_list
        if entry.edits.precision_override is not None
    }


def _build_per_test_unsupported_map(
    file_entry: FileEntry,
) -> Dict[str, Set[torch.dtype]]:
    """Build {method_name -> set of torch.dtype} from allow_list edits."""
    result: Dict[str, Set[torch.dtype]] = {}
    for entry in file_entry.allow_list:
        if entry.edits.unsupported_dtypes is not None:
            result[entry.method_name] = entry.edits.resolved_unsupported_dtypes()
    return result


def _build_tags_map(file_entry: FileEntry) -> Dict[str, List]:
    """Build {method_name -> [tag, ...]} from allow_list entries."""
    return {entry.method_name: entry.tags for entry in file_entry.allow_list}


# ---------------------------------------------------------------------------
# SpyreTestBase
# ---------------------------------------------------------------------------


# PrivateUse1TestBase injected via globals() by runpy
class SpyreTestBase(PrivateUse1TestBase):  # type: ignore[name-defined]  # noqa: F821
    """Base class for all Spyre PyTorch test overrides.

    All configuration is loaded lazily from the YAML file pointed to by
    SPYRE_PYTORCH_TEST_CONFIG.  The YAML is validated by Pydantic on load.
    See spyre_test_config_schema.json for the full schema.
    """

    device_type: str = "privateuse1"
    precision: float = DEFAULT_FLOATING_PRECISION

    # Populated by _load_test_suite_config on first call.
    # Keyed by class_name from 'ClassName::method_name' in YAML.
    ALLOW_LIST_TESTS: Dict[str, set] = {}
    BLOCK_LIST_TESTS: Dict[str, set] = {}
    XFAIL_TESTS: Dict[str, set] = {}
    PRECISION_OVERRIDES: Dict[str, float] = {}
    EXTRA_ALLOWED_DTYPES: Dict[str, set] = {}
    PER_TEST_UNSUPPORTED_DTYPES: Dict[str, set] = {}
    TEST_TAGS: Dict[str, List] = {}
    unsupported_dtypes: Set[torch.dtype] = DEFAULT_UNSUPPORTED_DTYPES

    # ------------------------------------------------------------------
    # Config loading  (called once per test run via instantiate_test)
    # ------------------------------------------------------------------

    @classmethod
    def _load_test_suite_config(cls) -> None:
        """Load and apply YAML config. No-op after first successful load."""
        path = os.environ.get(ENV_TEST_CONFIG)
        if not path or getattr(cls, "_yaml_loaded", False):
            return

        # load_yaml_config returns a validated SpyreTestConfig (Pydantic model)
        config: SpyreTestConfig = load_yaml_config(path)

        # ── op_db filtering (must happen before @ops sees the lists) ──
        supported_ops = config.global_config.resolved_supported_ops()
        if supported_ops is not None:
            filter_op_db(supported_ops)

        # ── resolve which file entry applies to the current test file ──
        # pytest is always invoked from pytorch/test/, matched by cwd.
        file_entry: FileEntry = resolve_current_file(config, path)

        # ── populate class-level dicts from typed FileEntry ───────────
        cls.ALLOW_LIST_TESTS = _build_allow_list_map(file_entry)
        cls.BLOCK_LIST_TESTS = _build_block_list_map(file_entry)
        cls.XFAIL_TESTS = _build_xfail_map(file_entry)
        cls.EXTRA_ALLOWED_DTYPES = _build_extra_dtypes_map(file_entry)
        cls.PRECISION_OVERRIDES = _build_precision_overrides_map(file_entry)
        cls.PER_TEST_UNSUPPORTED_DTYPES = _build_per_test_unsupported_map(file_entry)
        cls.TEST_TAGS = _build_tags_map(file_entry)
        cls.unsupported_dtypes = config.global_config.resolved_unsupported_dtypes()

        cls._yaml_loaded = True

    # ------------------------------------------------------------------
    # Mode resolution
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_mode(cls) -> str:
        """Return the active filter mode: 'allow_list' or 'block_list'.

        Priority:
          1. SPYRE_PYTORCH_TEST_FILTER_TYPE env var (explicit)
          2. Inferred: MODE_ALLOW_LIST if both `allowed_list` and `block_list` are populated
          3. Default: MODE_ALLOW_LIST
        """
        env = os.environ.get(ENV_FILTER_TYPE, "").strip().lower()
        if env in (MODE_ALLOW_LIST, MODE_BLOCK_LIST):
            return env
        if env:
            raise ValueError(
                f"{ENV_FILTER_TYPE}={env!r} is invalid. "
                f"Use {MODE_ALLOW_LIST!r} or {MODE_BLOCK_LIST!r}."
            )
        if cls.ALLOW_LIST_TESTS:
            return MODE_ALLOW_LIST
        if cls.BLOCK_LIST_TESTS:
            return MODE_BLOCK_LIST
        return MODE_ALLOW_LIST  # default: run allowed_list

    # ------------------------------------------------------------------
    # Compiled match-set cache
    # ------------------------------------------------------------------

    @classmethod
    def _get_active_match_sets(cls) -> Dict[str, MatchSet]:
        """Return compiled MatchSets for whichever dict is active."""
        mode = cls._resolve_mode()
        cache_attr = f"_cached_msets_{mode}"
        if cache_attr not in cls.__dict__ or cls.__dict__[cache_attr] is None:
            source = (
                cls.ALLOW_LIST_TESTS
                if mode == MODE_ALLOW_LIST
                else cls.BLOCK_LIST_TESTS
            )
            setattr(cls, cache_attr, build_match_sets(source))
        return cls.__dict__[cache_attr]

    # ------------------------------------------------------------------
    # Dtype unsupported check
    # ------------------------------------------------------------------

    @classmethod
    def _is_dtype_unsupported(
        cls, method_name: str, base_test_name: str
    ) -> Optional[str]:
        """Return a skip reason string if the dtype is unsupported, else None.

        Per-test edits.unsupported_dtypes takes precedence over
        global.unsupported_dtypes (complete override, not a union).
        """
        dtype_str = extract_dtype_from_name(method_name)
        if dtype_str:
            try:
                active_unsupported = cls.PER_TEST_UNSUPPORTED_DTYPES.get(
                    base_test_name, cls.unsupported_dtypes
                )
                if parse_dtype(dtype_str) in active_unsupported:
                    return f"Unsupported dtype: {dtype_str}"
            except ValueError:
                pass
        return None

    # ------------------------------------------------------------------
    # xfail lookup
    # ------------------------------------------------------------------

    @classmethod
    def _get_xfail_entry(
        cls, method_name: str, base_test_name: str, generic_cls_name: str
    ) -> Optional[tuple]:
        """Return (strict,) if the test is in XFAIL_TESTS, else None.

        Matches on either the instantiated method name or the base test name.
        """
        entries = cls.XFAIL_TESTS.get(generic_cls_name, set())
        for xfail_name, strict in entries:
            if xfail_name in (method_name, base_test_name):
                return (strict,)
        return None

    # ------------------------------------------------------------------
    # _should_run
    # ------------------------------------------------------------------

    @classmethod
    def _should_run(
        cls,
        method_name: str,
        base_test_name: str,
        generic_cls_name: str,
    ) -> tuple:
        """Decide whether an instantiated test method should run.

        allow_list mode
          - name in ALLOW_LIST_TESTS -> RUN  (subject to dtype filter)
          - otherwise                -> SKIP

        block_list mode
          - name in BLOCK_LIST_TESTS -> SKIP
          - otherwise                -> RUN  (subject to dtype filter)

        Dtype filtering (both modes)
          Tests whose method name embeds an unsupported dtype are skipped.
          Per-test edits.unsupported_dtypes overrides global.unsupported_dtypes.

        Returns:
            (enabled: bool, reason: Optional[str])
        """
        mode = cls._resolve_mode()
        mset: Optional[MatchSet] = cls._get_active_match_sets().get(generic_cls_name)

        def _name_matches(ms: Optional[MatchSet]) -> bool:
            return ms is not None and (
                ms.matches(method_name) or ms.matches(base_test_name)
            )

        if mode == MODE_ALLOW_LIST:
            if _name_matches(mset):
                reason = cls._is_dtype_unsupported(method_name, base_test_name)
                return (False, reason) if reason else (True, None)
            return False, "Not in allow_list"

        else:  # block_list
            if _name_matches(mset):
                return False, "In block_list - disabled for Spyre"
            reason = cls._is_dtype_unsupported(method_name, base_test_name)
            return (False, reason) if reason else (True, None)

    # ------------------------------------------------------------------
    # instantiate_test override
    # ------------------------------------------------------------------

    @classmethod
    def instantiate_test(cls, name, test, *, generic_cls=None):
        cls._load_test_suite_config()

        # Print tags to real stderr (fd 2) so they appear without -s flag.
        # os.write bypasses pytest's sys.stderr redirection during collection.
        tags = cls.TEST_TAGS.get(name)
        if tags:
            os.write(
                2,
                f"[SpyreTestBase] {generic_cls.__name__}::{name} "
                f"tags: [{', '.join(tags)}]\n".encode(),
            )

        # Per-test precision override
        cls.precision = cls.PRECISION_OVERRIDES.get(name, DEFAULT_FLOATING_PRECISION)

        # Only patch @onlyOn and @ops for tests explicitly in the allow_list.
        # This is an intentional opt-in — if you add TestCommon::test_compare_cpu
        # to allow_list, we patch @onlyOn so it runs for privateuse1.
        mode = cls._resolve_mode()
        if mode == MODE_ALLOW_LIST:
            generic_cls_name = generic_cls.__name__ if generic_cls else ""
            mset = cls._get_active_match_sets().get(generic_cls_name)
            if mset is not None and (
                mset.matches(name) or mset.matches(f"{generic_cls_name}::{name}")
            ):
                _SpyreOnlyOnPatcher(test).patch()

        # Inject extra dtypes into @ops before super() generates variants
        extra_dtypes = cls.EXTRA_ALLOWED_DTYPES.get(name)
        if extra_dtypes:
            _SpyreDtypePatcher(test, extra_dtypes).patch()

        # Let the parent generate all variant methods, then apply our filters
        existing_methods = set(cls.__dict__.keys())
        super().instantiate_test(name, test, generic_cls=generic_cls)
        new_methods = set(cls.__dict__.keys()) - existing_methods

        for method_name in new_methods:
            enabled, reason = cls._should_run(
                method_name=method_name,
                base_test_name=name,
                generic_cls_name=generic_cls.__name__,
            )

            if not enabled:
                skip_reason = reason or "Skipped for Spyre"

                @wraps(test)
                def _skip(self, _reason=skip_reason):
                    raise unittest.SkipTest(_reason)

                setattr(cls, method_name, _skip)
                continue

            # xfail applied after skip so block_list tests are not also marked xfail
            xfail_entry = cls._get_xfail_entry(method_name, name, generic_cls.__name__)
            if xfail_entry is not None:
                (strict,) = xfail_entry
                existing_fn = cls.__dict__.get(method_name)
                if existing_fn is not None:
                    setattr(
                        cls,
                        method_name,
                        pytest.mark.xfail(strict=strict)(existing_fn),
                    )


TEST_CLASS = SpyreTestBase
