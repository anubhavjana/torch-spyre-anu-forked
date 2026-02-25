# import torch
# import re
# import unittest
# from functools import wraps

# DEFAULT_FLOATING_PRECISION = 1e-3

# ENABLED_TESTS = {
#     "TestBinaryUfuncs": {
#         # "test_add", #  NotImplementedError: as_strided not implemented for Spyre tensors, implement the caller using as_strided_with_layout with the proper semantics
#         # "test_mul", test_muldiv_scalar_spyre_bfloat16  ERRR 24.02.2026 09:27:30.344514 [ memory_allocator.cpp: 152] Trying to free invalid block: 0x80
#         # "test_div",
#         # "test_logaddexp",
#         # "test_bitwise_ops",
#         # "test_pow",
#         "test_add_broadcast_empty",                 
#         # "test_reference_numerics",
#         # "test_lcm", # lcm.out not supported in spyre
#         # "test_cdiv", # only for CPU
#     }
# }

# OP_LIST = {
#     "add",
#     "sub", 
#     "div",
#     "mul",
#     "pow"
# }

# PRECISION_OVERRIDES = {
#     "test_sum": 1e-2,
#     "test_softmax": 1e-3,
#     "test_batch_norm": 1e-1,
# }

# # Remove built-in PrivateUse1TestBase so only SpyreTestBase handles
# # the privateuse1 device type.
# device_type_test_bases[:] = [  # type: ignore[name-defined] # noqa: F821
#     b
#     for b in device_type_test_bases  # type: ignore[name-defined] # noqa: F821
#     if b is not PrivateUse1TestBase  # type: ignore[name-defined] # noqa: F821
# ]


# class SpyreTestBase(PrivateUse1TestBase):  # type: ignore[name-defined] # noqa: F821
#     device_type = "privateuse1"
#     precision = DEFAULT_FLOATING_PRECISION
    
#     # Unsupported dtypes 
#     unsupported_dtypes = {
#         torch.complex32,
#         torch.complex64,
#         torch.complex128,
        
#         torch.bfloat16,

#         torch.int16,
#         torch.int32,

#         torch.float16,
#         torch.float32,
#         torch.float64,

#     }

#     @classmethod
#     def instantiate_test(cls, name, test, *, generic_cls):
#         # Resolve the actual device name (privateuse1 -> spyre)
#         cls_device_type = (
#             cls.device_type
#             if cls.device_type != "privateuse1"
#             else torch._C._get_privateuse1_backend_name()
#         )
        
#         print(f"Checking validity of test: {name}")
        
#         # Check if base test is enabled
#         base_is_enabled = False
#         if generic_cls.__name__ in ENABLED_TESTS.keys():
#             if name in ENABLED_TESTS[generic_cls.__name__]:
#                 base_is_enabled = True
        
#         # Per-test precision override
#         cls.precision = PRECISION_OVERRIDES.get(name, DEFAULT_FLOATING_PRECISION)
        
#         # Snapshot existing methods, let parent do all the work
#         existing_methods = set(cls.__dict__.keys())
#         super().instantiate_test(name, test, generic_cls=generic_cls)
#         new_methods = set(cls.__dict__.keys()) - existing_methods
        
#         @wraps(test)
#         def skip_test(self, test=test):
#             raise unittest.SkipTest("Skipped for Spyre")
        
#         for method_name in new_methods:
#             test_enabled = False
#             skip_reason = "Not in ENABLED_TESTS"
            
#             if base_is_enabled:
#                 # Check for tests without op names
#                 if method_name.startswith(name + "_" + cls_device_type):
#                     test_enabled = True
#                     skip_reason = None
                
#                 # Check for tests with op names
#                 if not test_enabled:
#                     for op in OP_LIST:
#                         if f"_{op}_" in method_name:
#                             test_enabled = True
#                             skip_reason = None
#                             break
                
#                 # Dtype filtering - skip unsupported dtypes
#                 if test_enabled:
#                     dtype_str = cls._extract_dtype_from_name(method_name)
#                     if dtype_str:
#                         try:
#                             dtype = cls._parse_dtype(dtype_str)
#                             if dtype in cls.unsupported_dtypes:
#                                 test_enabled = False
#                                 skip_reason = f"Unsupported dtype: {dtype_str}"
#                         except ValueError:
#                             pass  # Unknown dtype, let it through
            
#             if not test_enabled:
#                 @wraps(test)
#                 def skip_with_reason(self, test=test, reason=skip_reason):
#                     raise unittest.SkipTest(f"Skipped for Spyre: {reason}")
                
#                 setattr(cls, method_name, skip_with_reason)
#             else:
#                 print(f"✓ Enabling: {generic_cls.__name__}::{method_name}")
    
#     @staticmethod
#     def _extract_dtype_from_name(method_name):
#         """Extract dtype string from test method name"""
#         dtypes = [
#             'complex128', 'complex64', 'complex32',
#             'bfloat16', 'float64', 'float32', 'float16',
#             'uint64', 'uint32', 'uint16', 'uint8',
#             'int64', 'int32', 'int16', 'int8',
#             'bool'
#         ]
        
#         for dtype in dtypes:
#             if f"_{dtype}_" in method_name or method_name.endswith(f"_{dtype}"):
#                 return dtype
        
#         return None
    
#     @staticmethod
#     def _parse_dtype(dtype_str):
#         """Convert dtype string to torch.dtype"""
#         dtype_map = {
#             'float16': torch.float16,
#             'float32': torch.float32, 
#             'float64': torch.float64,
#             'bfloat16': torch.bfloat16,
#             'int8': torch.int8,
#             'int16': torch.int16,
#             'int32': torch.int32,
#             'int64': torch.int64,
#             'uint8': torch.uint8,
#             'uint16': torch.uint16,
#             'uint32': torch.uint32,
#             'uint64': torch.uint64,
#             'complex32': torch.complex32,
#             'complex64': torch.complex64,
#             'complex128': torch.complex128,
#             'bool': torch.bool,
#         }
        
#         if dtype_str not in dtype_map:
#             raise ValueError(f"Unknown dtype: {dtype_str}")
        
#         return dtype_map[dtype_str]


# TEST_CLASS = SpyreTestBase

"""
Spyre test override for test_binary_ufuncs.py
Usage
-----
    export PYTORCH_TESTING_DEVICE_ONLY_FOR="privateuse1"
    export TORCH_TEST_DEVICES=".../spyre_test_binaryfuncs.py"
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
    # Populate when switching to blacklist mode
        "test_add_broadcast_empty", # Signal Received: 11 (Segmentation fault)
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