import torch
import re
import unittest
from functools import wraps

DEFAULT_FLOATING_PRECISION = 1e-3

ENABLED_TESTS = {
    "TestReductions": {
        # "test_var_mean", # NotImplementedError: Could not run 'aten::uniform_' with arguments from the 'spyre' backend
        # # Even after hack around the above ->  NotImplementedError: Could not run 'aten::var_mean.correction' 
        
        
        # "test_dim_default_keepdim",
        # "test_dim_none",
        # "test_dim_none_keepdim",
        # "test_dim_single",
        # "test_dim_single_keepdim",
        # "test_dim_empty",
        # "test_dim_empty_keepdim",
        # "test_dim_multi",
        # "test_dim_multi_keepdim",
        # "test_dim_multi_unsorted",             
        
    }
}

ENABLED_TESTS = {
    "TestReductions": {

        # NotImplementedError: Could not run 'aten::uniform_' with arguments from the 'spyre' backend
        # # Even after hack around the above ->  NotImplementedError: Could not run 'aten::var_mean.correction' 
        # "test_var_mean", 
        # "test_var_mean_correction",

        
        "test_dim_default_keepdim",
        "test_dim_none",
        "test_dim_none_keepdim",
        "test_dim_single",
        "test_dim_single_keepdim",
        "test_dim_empty",
        "test_dim_empty_keepdim",
        "test_dim_multi",
        "test_dim_multi_keepdim",
        "test_dim_multi_unsorted",
        "test_dim_multi_unsorted_keepdim",
        "test_dim_multi_duplicate",
        "test_dim_offbounds",
        "test_dim_repeated",
        "test_dim_reduction",
        "test_dim_reduction_lastdim",
        "test_dim_reduction_less_than_64",
        "test_dim_reduction_fns",
        "test_dim_arg_reduction_scalar",
        "test_dim_ndim_limit",
        "test_dim_default",
        "test_dim_none",
        "test_dim_multi_unsupported",

        
        "test_sum_all",
        "test_sum_dim",
        "test_sum_out",
        "test_sum_vs_numpy",
        "test_sum_parallel",
        "test_sum_noncontig",
        "test_sum_noncontig_lowp",
        "test_sum_integer_upcast",
        "test_sum_dim_reduction_uint8_overflow",

        "test_mean_dim",
        "test_mean_int_with_optdtype",

        "test_std",
        "test_std_dim",
        "test_std_vs_numpy",
        "test_std_mean",
        "test_std_mean_some_dims",
        "test_std_mean_all_dims",
        "test_std_mean_correction",
        "test_std_correction_vs_numpy",

        "test_var",
        "test_var_dim",
        "test_var_unbiased",
        "test_var_vs_numpy",
        "test_var_stability",
        "test_var_stability2",
        "test_var_large_input",
        "test_var_mean_all_dims",
        "test_var_mean_some_dims",
        "test_var_correction_vs_numpy",

        "test_prod",
        "test_prod_lowp",
        "test_prod_integer_upcast",
        "test_prod_gpu",

        "test_cumsum_integer_upcast",
        "test_cumprod_integer_upcast",

        
        "test_min",
        "test_max",
        "test_min_with_inf",
        "test_max_with_inf",
        "test_min_max_nan",
        "test_min_elementwise",
        "test_max_elementwise",
        "test_min_mixed_devices",
        "test_max_mixed_devices",
        "test_minmax_illegal_dtype",
        "test_amin",
        "test_amax",
        "test_aminmax",
        "test_amin_amax_some_dims",
        "test_invalid_0dim_aminmax",

        
        "test_argminmax_multiple",
        "test_argminmax_large_axis",
        "test_argminmax_axis_with_dim_one",
        "test_tensor_compare_ops_argmax_argmix_kthvalue_dim_empty",

        
        "test_all_any",
        # "test_all_any_empty", # Signal Received: 11 (Segmentation fault)
        "test_all_any_vs_numpy",
        "test_all_any_with_dim",
        "test_all_issue117215",
        "test_reduction_empty_any_all",

        
        "test_nansum",
        "test_nansum_complex",
        "test_nansum_vs_numpy",
        "test_nansum_out_dtype",
        "test_nanmean_integral_types",
        "test_nan_policy_omit",
        "test_nan_policy_propagate",

        
        "test_logsumexp",
        "test_logsumexp_dim",
        "test_logsumexp_integral_promotion",
        "test_logcumsumexp_complex",

        
        "test_quantile",
        "test_quantile_backward",
        "test_quantile_error",

        
        "test_histc",
        "test_histc_lowp",
        "test_histc_min_max_corner_cases",
        "test_histc_min_max_corner_cases_cuda",
        "test_histc_min_max_errors",
        "test_histogram",
        "test_histogramdd",
        "test_histogram_error_handling",
        "test_bucketization",
        "test_bincount",

        
        "test_mode",
        "test_mode_large",
        "test_mode_boolean",
        "test_mode_wrong_device",
        "test_mode_wrong_dtype",

        
        "test_ref_small_input",
        "test_ref_large_input_1D",
        "test_ref_large_input_2D",
        "test_ref_large_input_64bit_indexing",
        "test_ref_duplicate_values",
        "test_ref_extremal_values",
        "test_ref_scalar_input",
        "test_reference_masked",

        
        "test_reduce_dtype",
        "test_result_dtype",
        # "test_accreal_type", # Only runs on cpu
        "test_numpy_named_args",
        "test_identity",
        "test_tensor_reduce_ops_empty",
        "test_tensor_compare_ops_empty",
        "test_empty_tensor_empty_slice",
        "test_empty_tensor_nonempty_slice",
        "test_noncontiguous_all",
        "test_noncontiguous_outermost",
        "test_noncontiguous_innermost",
        "test_noncontiguous_transposed",
        "test_noncontiguous_expanded",
        "test_noncontiguous_all",
        "test_reduction_split",
        "test_reduction_vectorize_along_input_corner",
        "test_reduction_vectorize_along_output",
        "test_reductions_large_half_tensors",
        "test_warn_invalid_degrees_of_freedom",
    }
}

OP_LIST = {
    "add",
    "sub", 
    "div",
    "mul",
    "pow"
}

PRECISION_OVERRIDES = {
    "test_sum": 1e-2,
    "test_softmax": 1e-3,
    "test_batch_norm": 1e-1,
}

# Remove built-in PrivateUse1TestBase so only SpyreTestBase handles
# the privateuse1 device type.
device_type_test_bases[:] = [  # type: ignore[name-defined] # noqa: F821
    b
    for b in device_type_test_bases  # type: ignore[name-defined] # noqa: F821
    if b is not PrivateUse1TestBase  # type: ignore[name-defined] # noqa: F821
]


class SpyreTestBase(PrivateUse1TestBase):  # type: ignore[name-defined] # noqa: F821
    device_type = "privateuse1"
    precision = DEFAULT_FLOATING_PRECISION
    
    # Unsupported dtypes 
    unsupported_dtypes = {
        torch.complex32,
        torch.complex64,
        torch.complex128,
        
        torch.bfloat16,

        torch.int16,
        torch.int32,

        torch.float16,
        torch.float32,
        torch.float64,

    }

    @classmethod
    def instantiate_test(cls, name, test, *, generic_cls):
        # Resolve the actual device name (privateuse1 -> spyre)
        cls_device_type = (
            cls.device_type
            if cls.device_type != "privateuse1"
            else torch._C._get_privateuse1_backend_name()
        )
        
        print(f"Checking validity of test: {name}")
        
        # Check if base test is enabled
        base_is_enabled = False
        if generic_cls.__name__ in ENABLED_TESTS.keys():
            if name in ENABLED_TESTS[generic_cls.__name__]:
                base_is_enabled = True
        
        # Per-test precision override
        cls.precision = PRECISION_OVERRIDES.get(name, DEFAULT_FLOATING_PRECISION)
        
        # Snapshot existing methods, let parent do all the work
        existing_methods = set(cls.__dict__.keys())
        super().instantiate_test(name, test, generic_cls=generic_cls)
        new_methods = set(cls.__dict__.keys()) - existing_methods
        
        @wraps(test)
        def skip_test(self, test=test):
            raise unittest.SkipTest("Skipped for Spyre")
        
        for method_name in new_methods:
            test_enabled = False
            skip_reason = "Not in ENABLED_TESTS"
            
            if base_is_enabled:
                # Check for tests without op names
                if method_name.startswith(name + "_" + cls_device_type):
                    test_enabled = True
                    skip_reason = None
                
                # Check for tests with op names
                if not test_enabled:
                    for op in OP_LIST:
                        if f"_{op}_" in method_name:
                            test_enabled = True
                            skip_reason = None
                            break
                
                # Dtype filtering - skip unsupported dtypes
                if test_enabled:
                    dtype_str = cls._extract_dtype_from_name(method_name)
                    if dtype_str:
                        try:
                            dtype = cls._parse_dtype(dtype_str)
                            if dtype in cls.unsupported_dtypes:
                                test_enabled = False
                                skip_reason = f"Unsupported dtype: {dtype_str}"
                        except ValueError:
                            pass  # Unknown dtype, let it through
            
            if not test_enabled:
                @wraps(test)
                def skip_with_reason(self, test=test, reason=skip_reason):
                    raise unittest.SkipTest(f"Skipped for Spyre: {reason}")
                
                setattr(cls, method_name, skip_with_reason)
            else:
                print(f"✓ Enabling: {generic_cls.__name__}::{method_name}")
    
    @staticmethod
    def _extract_dtype_from_name(method_name):
        """Extract dtype string from test method name"""
        dtypes = [
            'complex128', 'complex64', 'complex32',
            'bfloat16', 'float64', 'float32', 'float16',
            'uint64', 'uint32', 'uint16', 'uint8',
            'int64', 'int32', 'int16', 'int8',
            'bool'
        ]
        
        for dtype in dtypes:
            if f"_{dtype}_" in method_name or method_name.endswith(f"_{dtype}"):
                return dtype
        
        return None
    
    @staticmethod
    def _parse_dtype(dtype_str):
        """Convert dtype string to torch.dtype"""
        dtype_map = {
            'float16': torch.float16,
            'float32': torch.float32, 
            'float64': torch.float64,
            'bfloat16': torch.bfloat16,
            'int8': torch.int8,
            'int16': torch.int16,
            'int32': torch.int32,
            'int64': torch.int64,
            'uint8': torch.uint8,
            'uint16': torch.uint16,
            'uint32': torch.uint32,
            'uint64': torch.uint64,
            'complex32': torch.complex32,
            'complex64': torch.complex64,
            'complex128': torch.complex128,
            'bool': torch.bool,
        }
        
        if dtype_str not in dtype_map:
            raise ValueError(f"Unknown dtype: {dtype_str}")
        
        return dtype_map[dtype_str]


TEST_CLASS = SpyreTestBase