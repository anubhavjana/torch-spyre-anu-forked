"""
Spyre test override for test_reductions.py
Usage
-----
    export PYTORCH_TESTING_DEVICE_ONLY_FOR="privateuse1"
    export TORCH_TEST_DEVICES=".../spyre_test_reductions.py"
    export SPYRE_TEST_MODE=whitelist    # or: blacklist
    cd $PYTORCH_ROOT/test/
    python3 -m pytest test_reductions.py -v
"""

import torch
from spyre_test_base_common import SpyreTestBase

_ENABLED: dict = {
    "TestReductions": {

        # NotImplementedError: Could not run 'aten::uniform_' with arguments from the 'spyre' backend
        # Even after hack around the above -> NotImplementedError: Could not run 'aten::var_mean.correction'
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
        # "test_dim_reduction",              # Failed
        "test_dim_reduction_lastdim",
        # "test_dim_reduction_less_than_64", # Failed
        "test_dim_reduction_fns",

        # "test_dim_arg_reduction_scalar",
        #
        # ERRR 24.02.2026 14:16:01.484632 [ras_base.hpp:  95] {
        # "BufAlgnBoundary":"128B","action":"information","category":"software","code":"0x161e",
        # "description":"The buffer is not aligned to the given boundary.","message":"Buffer not aligned",
        # "name":"RAS::SCHEDULER::BufferNotAligned","severity":"ERROR","step":"Open ticket","type":"runtime_error"}

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

        # "test_minmax_illegal_dtype",       # Signal Received: 8 (Floating point exception)

        "test_amin",
        "test_amax",
        "test_aminmax",
        # "test_amin_amax_some_dims",        # Failed
        "test_invalid_0dim_aminmax",

        # "test_argminmax_multiple",         # Failed
        "test_argminmax_large_axis",
        "test_argminmax_axis_with_dim_one",
        "test_tensor_compare_ops_argmax_argmix_kthvalue_dim_empty",

        # "test_all_any",          # test_reductions.py::TestReductionsPRIVATEUSE1::test_all_any_with_dim_spyre
        #                          # terminate called after throwing an instance of 'DtException'
        #                          # what(): DtException: Unsupported data format types,
        #                          # file /project_src/deeptools/util/sen_data_convert.cpp line 2623
        # "test_all_any_empty",    # Signal Received: 11 (Segmentation fault)
        # "test_all_any_vs_numpy", # test_all_any_vs_numpy_spyre_bool Signal Received: 11 (Segmentation fault)
        # "test_all_any_with_dim", # terminate called after throwing an instance of 'DtException'
        #                          # what(): DtException: Unsupported data format types,
        #                          # file /project_src/deeptools/util/sen_data_convert.cpp line 2623

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

        # "test_histc",                      # Failed
        "test_histc_lowp",
        "test_histc_min_max_corner_cases",
        "test_histc_min_max_corner_cases_cuda",
        # "test_histc_min_max_errors",       # Failed - int64, int8
        #
        # spyre_uint8  ERRR 24.02.2026 14:25:36.525007 [ ras_base.hpp:  95]
        # {"BufAlgnBoundary":"128B","action":"information","category":"software","code":"0x161e",
        # "description":"The buffer is not aligned to the given boundary.",
        # "message":"Buffer not aligned","name":"RAS::SCHEDULER::BufferNotAligned",
        # "severity":"ERROR","step":"Open ticket","type":"runtime_error"}

        "test_histogram",
        "test_histogramdd",
        "test_histogram_error_handling",
        # "test_bucketization",              # Failed
        # "test_bincount",                   # Failed

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
        # "test_accreal_type",               # Only runs on cpu
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

_DISABLED: dict = {
    # Populate when switching to blacklist mode
}

# Remove built-in PrivateUse1TestBase so only SpyreTestBase handles
# the privateuse1 device type.  This prevents the nondeterministic
# overwrite when list(set(...)) randomizes order.
# TODO: figure out why this filter is needed - expected to use default PrivateUse1TestBase
device_type_test_bases[:] = [  # type: ignore[name-defined] # noqa: F821
    b for b in device_type_test_bases  # type: ignore[name-defined] # noqa: F821
    if b is not PrivateUse1TestBase  # type: ignore[name-defined] # noqa: F821
]


class SpyreReductionsTestBase(SpyreTestBase, PrivateUse1TestBase):  # type: ignore[name-defined] # noqa: F821

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


TEST_CLASS = SpyreReductionsTestBase