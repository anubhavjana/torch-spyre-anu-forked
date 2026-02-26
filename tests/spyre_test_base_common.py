"""
Shared class and methods for all Spyre PyTorch test overrides.

Each per-suite file (e.g. spyre_test_binaryfuncs.py) imports
SpyreTestBase from here and declares WHITELISTED_TESTS and/or BLACKLISTED_TESTS
as class attributes.  A single environment variable selects which dict
is active at runtime.

# New ENV VAR introduced 
SPYRE_TEST_MODE=whitelist --> use WHITELISTED_TESTS  (default when it exists)
SPYRE_TEST_MODE=blacklist --> use BLACKLISTED_TESTS (default when only that exists)

If a suite file defines BOTH dicts, set SPYRE_TEST_MODE explicitly to
choose which one governs the run.  When only one dict is defined the
mode is inferred automatically and SPYRE_TEST_MODE need not be set.

Usage as we already had apart from a new environment variable that got added 
    export PYTORCH_TESTING_DEVICE_ONLY_FOR="privateuse1"
    export TORCH_TEST_DEVICES=".../spyre_test_binaryfuncs.py"
    export SPYRE_TEST_MODE=whitelist          # or blacklist
    python3 -m pytest test_binary_ufuncs.py -v
"""
import os
import re
import unittest
from functools import wraps
from typing import Dict, Optional, Set

import torch

# ------------
# Constants
# -----------

DEFAULT_FLOATING_PRECISION: float = 1e-3

# Default set of unsupported dtypes on spyre (Per-suite subclasses may extend this set)
DEFAULT_UNSUPPORTED_DTYPES: Set[torch.dtype] = {
    torch.complex32,
    torch.complex64,
    torch.complex128,
}

# Valid values for SPYRE_TEST_MODE
_MODE_WHITELIST = "whitelist"
_MODE_BLACKLIST = "blacklist"

# ----------------------------
# Dtype helper data structures
# ----------------------------

_DTYPE_STR_MAP: Dict[str, torch.dtype] = {
    "float16":    torch.float16,
    "float32":    torch.float32,
    "float64":    torch.float64,
    "bfloat16":   torch.bfloat16,
    "int8":       torch.int8,
    "int16":      torch.int16,
    "int32":      torch.int32,
    "int64":      torch.int64,
    "uint8":      torch.uint8,
    "uint16":     torch.uint16,
    "uint32":     torch.uint32,
    "uint64":     torch.uint64,
    "complex32":  torch.complex32,
    "complex64":  torch.complex64,
    "complex128": torch.complex128,
    "bool":       torch.bool,
}

# Ordered longest-first so "complex128" matches before "complex12"
_DTYPE_NAMES_ORDERED = sorted(_DTYPE_STR_MAP.keys(), key=len, reverse=True)


def extract_dtype_from_name(method_name: str) -> Optional[str]:
    """Return the dtype suffix embedded in *method_name*, or None."""
    for dtype in _DTYPE_NAMES_ORDERED:
        if f"_{dtype}_" in method_name or method_name.endswith(f"_{dtype}"):
            return dtype
    return None


def parse_dtype(dtype_str: str) -> torch.dtype:
    if dtype_str not in _DTYPE_STR_MAP:
        raise ValueError(f"Unknown dtype string: {dtype_str!r}")
    return _DTYPE_STR_MAP[dtype_str]


# -------------------
# Match-set helpers 
# -------------------

class MatchSet:
    """Holds exact names and regex patterns for fast membership tests."""

    def __init__(self):
        self.exact: Set[str] = set()
        self.regex: Set[str] = set()

    @classmethod
    def from_iterable(cls, items):
        ms = cls()
        for m in items:
            if re.match(r"\w+$", m):
                ms.exact.add(m)
            else:
                ms.regex.add(m)
        return ms

    def matches(self, name: str) -> bool:
        if name in self.exact:
            return True
        return any(re.match(pattern, name) for pattern in self.regex)


def _build_match_sets(d: Dict[str, list]) -> Dict[str, MatchSet]:
    return {k: MatchSet.from_iterable(v) for k, v in d.items()}

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

def remove_privateuse1_test_base(device_type_test_bases, PrivateUse1TestBase) -> None:
    """Remove the built-in PrivateUse1TestBase from the global list.

    PyTorch injects both arguments into each suite file's namespace via
    runpy.run_path().  They are not available in this module's own namespace,
    so the suite file must forward them here explicitly:

        remove_privateuse1_test_base(device_type_test_bases, PrivateUse1TestBase)
                                     # type: ignore[name-defined] # noqa: F821
    """
    device_type_test_bases[:] = [
        b for b in device_type_test_bases
        if b is not PrivateUse1TestBase
    ]



class SpyreTestBase:
    """
    Base class for Spyre device-type tests.

    You will need to inherit this class + PrivateUse1TestBase in each per-suite
    file.  Declare WHITELISTED_TESTS, BLACKLISTED_TESTS, or both as class
    attributes (which will be controlled by SPYRE_TEST_MODE env variable).
    """

    device_type: str = "privateuse1"
    precision: float = DEFAULT_FLOATING_PRECISION

    # Override in per-suite subclasses.
    WHITELISTED_TESTS:   Dict[str, set] = {}
    BLACKLISTED_TESTS:   Dict[str, set] = {}
    PRECISION_OVERRIDES: Dict[str, float] = {}

    # Extend in per-suite subclasses for backend-specific dtype gaps.
    unsupported_dtypes: Set[torch.dtype] = DEFAULT_UNSUPPORTED_DTYPES

    

    @classmethod
    def _resolve_mode(cls) -> str:
        """
        Return the active mode: 'whitelist' or 'blacklist'.
        Priority:
          1. SPYRE_TEST_MODE env var 
          2. Inferred from which dicts are populated on the class
        """
        env = os.environ.get("SPYRE_TEST_MODE", "").strip().lower()
        if env in (_MODE_WHITELIST, _MODE_BLACKLIST):
            return env
        if env:
            raise ValueError(
                f"SPYRE_TEST_MODE={env!r} is invalid. "
                f"Use 'whitelist' or 'blacklist'."
            )

        # Prefer whitelist if WHITELISTED_TESTS is populated (priority)
        if cls.WHITELISTED_TESTS:
            return _MODE_WHITELIST
        
        # Prefer blacklist if BLACKLISTED_TESTS is populated
        if cls.BLACKLISTED_TESTS:
            return _MODE_BLACKLIST

        # Nothing is defined ->  blacklist mode (run everything by default)
        return _MODE_BLACKLIST

    # ----------------------------
    # Compiled match-set cache
    # ----------------------------
    @classmethod
    def _get_active_match_sets(cls) -> Dict[str, MatchSet]:
        """Return compiled MatchSets for whichever dict is active."""
        mode = cls._resolve_mode()
        cache_attr = f"_cached_msets_{mode}"
        if cache_attr not in cls.__dict__ or cls.__dict__[cache_attr] is None:
            source = cls.WHITELISTED_TESTS if mode == _MODE_WHITELIST else cls.BLACKLISTED_TESTS
            setattr(cls, cache_attr, _build_match_sets(source))
        return cls.__dict__[cache_attr]

   
    # Decide whether an instantiated test method should run
    @classmethod
    def _should_run(
        cls,
        method_name: str,
        base_test_name: str,
        generic_cls_name: str,
    ) -> tuple[bool, Optional[str]]:
        """
        
        Whitelist mode
        -> Test is in WHITELISTED_TESTS for this class then RUN
        -> Otherwise SKIP

        Blacklist mode
        -> Test is in BLACKLISTED_TESTS for this class then SKIP
        -> Otherwise RUN with dtype filter applied

        Dtype filtering (blacklist mode only)
          Tests with unsupported dtype are skipped even if
          not explicitly listed in BLACKLISTED_TESTS.  
          In whitelist mode, we assume that the 
          user is aware of the supported dtype.
        """
        mode = cls._resolve_mode()
        match_sets = cls._get_active_match_sets()
        mset = match_sets.get(generic_cls_name)

        def _name_matches(ms: Optional[MatchSet]) -> bool:
            if ms is None:
                return False
            return ms.matches(method_name) or ms.matches(base_test_name)

        if mode == _MODE_WHITELIST:
            if _name_matches(mset):
                return True, None
            return False, "Not in WHITELISTED_TESTS"

        else:  # blacklist
            if _name_matches(mset):
                return False, "DISABLED FOR SPYRE"

            # Dtype filter
            dtype_str = extract_dtype_from_name(method_name)
            if dtype_str:
                try:
                    dtype = parse_dtype(dtype_str)
                    if dtype in cls.unsupported_dtypes:
                        return False, f"Unsupported dtype: {dtype_str}"
                except ValueError:
                    pass

            return True, None

    # ---------------------------
    # instantiate_test override
    # ---------------------------
    @classmethod
    def instantiate_test(cls, name, test, *, generic_cls):
        # Per-test precision override
        cls.precision = cls.PRECISION_OVERRIDES.get(name, DEFAULT_FLOATING_PRECISION)

        # Let the parent class generate all variant methods first
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