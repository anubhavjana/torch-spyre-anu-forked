"""
Constants for the Spyre PyTorch test framework.
All string literals, default values, and dtype maps are here.
"""

from typing import Dict, Set

import torch

# ----------------
# Precision
# ----------------

DEFAULT_FLOATING_PRECISION: float = 1e-3

# ---------------------------
# allow_list entry modes
# ---------------------------

MODE_MANDATORY_PASS = "mandatory_pass"
MODE_XFAIL = "xfail"
MODE_XFAIL_STRICT = "xfail_strict"

# ---------------------------------------------------------------------------
# Filter type modes  (SPYRE_PYTORCH_TEST_FILTER_TYPE)
# ---------------------------------------------------------------------------

MODE_ALLOW_LIST = "allow_list"
MODE_BLOCK_LIST = "block_list"

# --------------------
# Dtype defaults
# --------------------

DEFAULT_UNSUPPORTED_DTYPES: Set[torch.dtype] = {
    torch.complex32,
    torch.complex64,
    torch.complex128,
}

# ---------------------------------------------------------------------------
# Dtype string -> torch.dtype map
# Ordered longest-first so "complex128" is matched before "complex12", etc.
# ---------------------------------------------------------------------------

DTYPE_STR_MAP: Dict[str, torch.dtype] = {
    "float16": torch.float16,
    "float32": torch.float32,
    "float64": torch.float64,
    "bfloat16": torch.bfloat16,
    "int8": torch.int8,
    "int16": torch.int16,
    "int32": torch.int32,
    "int64": torch.int64,
    "uint8": torch.uint8,
    "uint16": torch.uint16,
    "uint32": torch.uint32,
    "uint64": torch.uint64,
    "complex32": torch.complex32,
    "complex64": torch.complex64,
    "complex128": torch.complex128,
    "bool": torch.bool,
}

DTYPE_NAMES_ORDERED = sorted(DTYPE_STR_MAP.keys(), key=len, reverse=True)

# ------------------------------
# Environment variables
# ------------------------------

ENV_TEST_CONFIG = "SPYRE_PYTORCH_TEST_CONFIG"
ENV_FILTER_TYPE = "SPYRE_PYTORCH_TEST_FILTER_TYPE"
ENV_PYTORCH_ROOT = "SPYRE_PYTORCH_ROOT"
ENV_TORCH_SPYRE_ROOT = "SPYRE_TORCH_SPYRE_ROOT"

# -------------------------------------
# rel_path tokens -> env var names
# -------------------------------------

REL_PATH_TOKENS = (
    ("${PYTORCH}", ENV_PYTORCH_ROOT),
    ("${TORCH_SPYRE}", ENV_TORCH_SPYRE_ROOT),
)

# -----------------------------------------
# op_db attribute names that need to be
# filtered when supported_ops is set
# ----------------------------------------

OP_DB_ATTRS = (
    "op_db",
    "ops_and_refs",
    "binary_ufuncs",
    "binary_ufuncs_and_refs",
    "unary_ufuncs",
    "reduction_ops",
    "spectral_funcs",
    "sparse_unary_ufuncs",
    "sparse_csr_unary_ufuncs",
    "sparse_reduction_ops",
    "shape_funcs",
    "reference_filtered_ops",
    "reference_masked_ops",
    "sparse_masked_reduction_ops",
    "python_ref_db",
)
