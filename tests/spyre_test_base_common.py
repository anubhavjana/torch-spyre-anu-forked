"""
Shared class and methods for all Spyre PyTorch test overrides.

Each per-suite file (e.g. spyre_test_binaryfuncs.py) imports
SpyreTestBase from here and declares WHITELISTED_TESTS and/or BLACKLISTED_TESTS
as class attributes.  A single environment variable selects which dict
is active at runtime.

# New ENV VAR introduced
SPYRE_PYTORCH_TEST_FILTER_TYPE=whitelist --> use WHITELISTED_TESTS  (default when it exists)
SPYRE_PYTORCH_TEST_FILTER_TYPE=blacklist --> use BLACKLISTED_TESTS (default when only that exists)

If a suite file defines BOTH dicts, set SPYRE_PYTORCH_TEST_FILTER_TYPE explicitly to
choose which one governs the run.  When only one dict is defined the
mode is inferred automatically and SPYRE_PYTORCH_TEST_FILTER_TYPE need not be set.

Usage as we already had apart from a new environment variable that got added
    export PYTORCH_TESTING_DEVICE_ONLY_FOR="privateuse1"

    # Clone pytorch
    $DTI_PROJECT_ROOT/torch-spyre-docs/scripts/checkout-pytorch-src.sh

    export TORCH_TEST_DEVICES="$DTI_PROJECT_ROOT/torch-spyre/tests/spyre_test_base_common.py"
    export SPYRE_PYTORCH_TEST_FILTER_TYPE=whitelist  # or blacklist
    export SPYRE_PYTORCH_TEST_CONFIG=tests/test_binary_ufuncs.yaml

    cd $DTI_PROJECT_ROOT/pytorch/test/
    python3 -m pytest test_binary_ufuncs.py -v (Example upstream test)
"""

import os
import unittest
from functools import wraps
from typing import Dict, Optional, Set, List
import pytest
import torch
# from torch.testing._internal.common_device_type import ops as _ops_parametrizer
# common_device_type.py is the one running our suite file via runpy, so it's not fully initialized yet when we try to import from it.
# The fix is to do a lazy import inside the function, not at module level:


from spyre_test_constants import (
    DEFAULT_FLOATING_PRECISION,
    DEFAULT_UNSUPPORTED_DTYPES,
    ENV_FILTER_TYPE,
    ENV_TEST_CONFIG,
    MODE_BLACKLIST,
    MODE_WHITELIST,
)
from spyre_test_matching import (
    MatchSet,
    build_match_sets,
    extract_dtype_from_name,
    parse_dtype,
)
from spyre_test_parsing import (
    filter_op_db,
    load_yaml_config,
    parse_global_supported_ops,
    parse_global_unsupported_dtypes,
    parse_tests,
    resolve_current_file,
)


# ---------------------------------------------------------------------------
# PrivateUse1TestBase filter
#
# Called once at the top of each suite file, immediately after imports.
# Removes the built-in PrivateUse1TestBase so that SpyreTestBase is the sole
# handler for the privateuse1 device type, preventing nondeterministic
# overwrites when list(set(...)) randomises ordering.
#
# TODO: investigate whether this filter will still be needed once the upstream
#       PrivateUse1TestBase correctly defers to registered custom backends.
# ---------------------------------------------------------------------------

# Remove built-in PrivateUse1TestBase so only SpyreTestBase handles
# the privateuse1 device type.  This prevents the nondeterministic
# overwrite when list(set(...)) randomizes order.
# TODO: figure out why this filter is needed - expected to use default PrivateUse1TestBase
device_type_test_bases[:] = [  # type: ignore[name-defined] # noqa: F821
    b
    for b in device_type_test_bases  # type: ignore[name-defined] # noqa: F821
    if b is not PrivateUse1TestBase  # type: ignore[name-defined] # noqa: F821
]


class _SpyreDtypePatcher:
    """Patches @ops allowed_dtypes on a bound test method before instantiation.

    Needed because upstream @ops(..., allowed_dtypes=(...)) restricts which dtype
    variants are generated -- dtypes absent here are never instantiated, so they
    cannot be whitelisted. We inject extra dtypes before
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


# PrivateUse1TestBase injected via globals()
class SpyreTestBase(PrivateUse1TestBase):  # type: ignore[name-defined]  # noqa: F821
    """Base class for all Spyre PyTorch test overrides.

    All configuration is loaded lazily from the YAML file at
    SPYRE_PYTORCH_TEST_CONFIG.  See tests/spyre_test_config_schema.yaml for
    the full schema.
    """

    device_type: str = "privateuse1"
    precision: float = DEFAULT_FLOATING_PRECISION

    # Populated by _load_test_suite_config on first call
    WHITELISTED_TESTS: Dict[str, set] = {}
    BLACKLISTED_TESTS: Dict[str, set] = {}
    XFAIL_TESTS: Dict[str, set] = {}
    PRECISION_OVERRIDES: Dict[str, float] = {}
    EXTRA_ALLOWED_DTYPES: Dict[str, set] = {}
    PER_TEST_UNSUPPORTED_DTYPES: Dict[str, set] = {}
    TEST_TAGS: Dict[str, List] = {}
    unsupported_dtypes: Set[torch.dtype] = DEFAULT_UNSUPPORTED_DTYPES

    # ------------------------------------------------------------------
    # Config loading  (called once per test run)
    # ------------------------------------------------------------------

    @classmethod
    def _load_test_suite_config(cls) -> None:
        path = os.environ.get(ENV_TEST_CONFIG)
        if not path or getattr(cls, "_yaml_loaded", False):
            return

        data = load_yaml_config(path)

        # ── op_db filtering (must happen before @ops sees the lists) ──
        supported_ops = parse_global_supported_ops(data)
        if supported_ops is not None:
            filter_op_db(supported_ops)

        # ── resolve which file entry applies ──────────────────────────
        # pytest is always invoked from pytorch/test/, so we match by cwd.
        current_file = resolve_current_file(data, path)

        # ── parse allow_list / block_list ─────────────────────────────
        (
            cls.WHITELISTED_TESTS,
            cls.BLACKLISTED_TESTS,
            cls.XFAIL_TESTS,
            cls.EXTRA_ALLOWED_DTYPES,
            cls.PRECISION_OVERRIDES,
            cls.PER_TEST_UNSUPPORTED_DTYPES,
            cls.TEST_TAGS,
        ) = parse_tests(data, current_file)

        cls.unsupported_dtypes = parse_global_unsupported_dtypes(data)
        cls._yaml_loaded = True

    # ------------------------------------------------------------------
    # Mode resolution
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_mode(cls) -> str:
        """Return the active filter mode: 'whitelist' or 'blacklist'.

        Priority:
          1. SPYRE_PYTORCH_TEST_FILTER_TYPE env var (explicit)
          2. Inferred: whitelist if WHITELISTED_TESTS is populated, else blacklist
          3. Default: blacklist (run everything)
        """
        env = os.environ.get(ENV_FILTER_TYPE, "").strip().lower()
        if env in (MODE_WHITELIST, MODE_BLACKLIST):
            return env
        if env:
            raise ValueError(
                f"{ENV_FILTER_TYPE}={env!r} is invalid. "
                f"Use {MODE_WHITELIST!r} or {MODE_BLACKLIST!r}."
            )
        if cls.WHITELISTED_TESTS:
            return MODE_WHITELIST
        if cls.BLACKLISTED_TESTS:
            return MODE_BLACKLIST
        return MODE_BLACKLIST  # default: run everything

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
                cls.WHITELISTED_TESTS
                if mode == MODE_WHITELIST
                else cls.BLACKLISTED_TESTS
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

        Whitelist mode
          - name in WHITELISTED_TESTS  -> RUN  (subject to dtype filter)
          - otherwise                  -> SKIP

        Blacklist mode
          - name in BLACKLISTED_TESTS  -> SKIP
          - otherwise                  -> RUN  (subject to dtype filter)

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

        if mode == MODE_WHITELIST:
            if _name_matches(mset):
                reason = cls._is_dtype_unsupported(method_name, base_test_name)
                return (False, reason) if reason else (True, None)
            return False, "Not in ALLOWED_TESTS"

        else:  # blacklist
            if _name_matches(mset):
                return False, "BLOCKED TEST - DISABLED FOR SPYRE"
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

            # xfail is applied after skip so blocked tests are not also marked xfail
            xfail_entry = cls._get_xfail_entry(method_name, name, generic_cls.__name__)
            if xfail_entry is not None:
                (strict,) = xfail_entry
                existing_fn = cls.__dict__.get(method_name)
                if existing_fn is not None:
                    setattr(
                        cls, method_name, pytest.mark.xfail(strict=strict)(existing_fn)
                    )


TEST_CLASS = SpyreTestBase
