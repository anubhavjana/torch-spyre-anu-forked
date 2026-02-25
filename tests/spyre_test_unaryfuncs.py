"""
Spyre test override for test_unary_ufuncs.py

Usage
-----
    export PYTORCH_TESTING_DEVICE_ONLY_FOR="privateuse1"
    export TORCH_TEST_DEVICES="$DTI_PROJECT_ROOT/torch-spyre/tests/spyre_test_unaryufuncs.py"
    export PYTHONPATH="$DTI_PROJECT_ROOT/torch-spyre/tests:$PYTHONPATH"
    export SPYRE_TEST_MODE=whitelist    # or: blacklist
    cd $DTI_PROJECT_ROOT/pytorch/test/
    python3 -m pytest test_unary_ufuncs.py -v
"""

import torch
from spyre_test_base_common import SpyreTestBase

_ENABLED: dict = {
    "TestUnaryUfuncs": {
        "test_float_domains",
    }
}

_DISABLED: dict = {
    # Populate when switching to blacklist mode
}

# Remove the built-in PrivateUse1TestBase so SpyreTestBase is the sole handler.
device_type_test_bases[:] = [  # type: ignore[name-defined] # noqa: F821
    b for b in device_type_test_bases  # type: ignore[name-defined] # noqa: F821
    if b is not PrivateUse1TestBase  # type: ignore[name-defined] # noqa: F821
]


class SpyreUnaryUfuncsTestBase(SpyreTestBase, PrivateUse1TestBase):  # type: ignore[name-defined] # noqa: F821

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


TEST_CLASS = SpyreUnaryUfuncsTestBase