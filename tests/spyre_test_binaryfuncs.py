
"""
Spyre test override for test_binary_ufuncs.py
Usage
-----
    export PYTORCH_TESTING_DEVICE_ONLY_FOR="privateuse1"
    export TORCH_TEST_DEVICES="$DTI_PROJECT_ROOT/torch-spyre/tests/spyre_test_binaryfuncs.py"
    export SPYRE_TEST_MODE=whitelist    # or: blacklist
    export PYTHONPATH="$DTI_PROJECT_ROOT/torch-spyre/tests:$PYTHONPATH"
    cd $DTI_PROJECT_ROOT/pytorch/test/
    python3 -m pytest test_binary_ufuncs.py -v
"""

import torch
from spyre_test_base_common import SpyreTestBase

_ENABLED: dict = {
    "TestBinaryUfuncs": {
        # "test_add",          # NotImplementedError: as_strided not implemented for Spyre tensors, implement the caller using as_strided_with_layout with the proper semantics
        # "test_mul",          # test_muldiv_scalar_spyre_bfloat16  ERRR 24.02.2026 09:27:30.344514 [ memory_allocator.cpp: 152] Trying to free invalid block: 0x80
        # "test_div",
        # "test_logaddexp",
        # "test_bitwise_ops",
        # "test_pow",
        # "test_add_broadcast_empty",
        # "test_reference_numerics",
        # "test_lcm",          # lcm.out not supported in spyre
        # "test_cdiv",         # only for CPU

    }
}

_DISABLED: dict = {
    "TestBinaryUfuncs": {
        # will be used when explicitely set to blacklist mode
        "test_add_broadcast_empty", # Signal Received: 11 (Segmentation fault)
        "test_add", # Failed
        "test_addcmul_scalars_as_floats", # Failed
        "test_atan2_edgecases", # Failed
        "test_atan2", # Signal Received: 8 (Floating point exception)
        "test_float_power_exceptions", # Signal Received: 8 (Floating point exception)
    }

}

# Remove the built-in PrivateUse1TestBase so SpyreTestBase is the sole handler.
device_type_test_bases[:] = [  # type: ignore[name-defined] # noqa: F821
    b for b in device_type_test_bases  # type: ignore[name-defined] # noqa: F821
    if b is not PrivateUse1TestBase  # type: ignore[name-defined] # noqa: F821
]


class SpyreBinaryUfuncsTestBase(SpyreTestBase, PrivateUse1TestBase):  # type: ignore[name-defined] # noqa: F821

    ENABLED_TESTS  = _ENABLED
    DISABLED_TESTS = _DISABLED

    PRECISION_OVERRIDES = {
        "test_sum":        1e-2,
        "test_softmax":    1e-3,
        "test_batch_norm": 1e-1,
    }

    unsupported_dtypes = SpyreTestBase.unsupported_dtypes | {
        torch.bfloat16,
        torch.int16,
        torch.int32,
        torch.float16,
        torch.float32,
        torch.float64,
    }


TEST_CLASS = SpyreBinaryUfuncsTestBase