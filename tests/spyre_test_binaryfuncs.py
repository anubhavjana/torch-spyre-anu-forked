
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
from spyre_test_base_common import SpyreTestBase, remove_privateuse1_test_base

_BLACKLISTED: dict = {
    "TestBinaryUfuncs": {
        # will be used when explicitely set to blacklist mode
        "test_add_broadcast_empty", # Signal Received: 11 (Segmentation fault)
        "test_add", # Failed
        "test_addcmul_scalars_as_floats", # Failed
        "test_atan2_edgecases", # Failed
        "test_atan2", # Signal Received: 8 (Floating point exception)
        "test_float_power_exceptions", # Signal Received: 8 (Floating point exception)

        "test_gcd", #(test_gcd_spyre_uint8) ERRR 25.02.2026 09:25:16.914306 ras_base.hpp:  95] 
        # {"BufAlgnBoundary":"128B","action":"information","category":"software",
        # "code":"0x161e","description":"The buffer is not aligned to the given boundary.",
        # "message":"Buffer not aligned","name":"RAS::SCHEDULER::BufferNotAligned","severity":"ERROR",
        # "step":"Open ticket","type":"runtime_error"}

        "test_int_tensor_pow_neg_ints", # DtException: Unsupported data format types, file /project_src/deeptools/util/sen_data_convert.cpp line 2623
                                        # Signal Received: 6 (Aborted)
        "test_idiv_and_ifloordiv_vs_python", # free(): invalid next size (fast) Signal Received: 6 (Aborted)

        "test_logical_and", # test_logical_and_spyre_bool_uint8  ERRR 27.02.2026 05:23:52.583737 
        # [ras_base.hpp:  95] {"BufAlgnBoundary":"128B","action":"information","category":"software","code":"0x161e",
        # "description":"The buffer is not aligned to the given boundary.","message":"Buffer not aligned",
        # "name":"RAS::SCHEDULER::BufferNotAligned","severity":"ERROR","step":"Open ticket","type":"runtime_error"}

        "test_logical_or", # same error as above

        "test_logical", # test_logical_spyre_bool  ERRR 27.02.2026 06:06:42.564890 
        # [ras_base.hpp:  95] {"action":"information","category":"software","cb_cmpt_bootaddr":"0x38000000",
        # "cb_ctrl_contextid":0,"cb_ctrl_edep":1,"cb_name":"sdsc_fused_lt_1","code":"0x1274",
        # "description":"A software error was detected in the card while executing a control block",
        # "message":"Control block software failure","name":"RAS::CBRB::ControlBlockSoftFail",
        # "rb_qgierr_addr":"0x0","rb_qgierr_definitions":["job header with zero flit count"],
        # "rb_qgierr_jobcount":0,"rb_qgierr_signals":["prep_zero_flit_cnt"],
        # "rb_ret_locator":2,"rb_ret_status":"ERROR","rb_timestamps":["0x00487177","0x00487177",
        # "0xcf7c31bc","0x004872c8","0x004872d1","0xc895c57e","0x00000000","0x00000000"],
        # "severity":"ERROR","step":"Monitor card for additional messages","type":"runtime_error"}
    }

}

# Remove the built-in PrivateUse1TestBase so SpyreTestBase is the sole handler.
# device_type_test_bases and PrivateUse1TestBase are injected into this file's
# namespace by PyTorch via runpy.run_path() and must be forwarded explicitly.
remove_privateuse1_test_base(device_type_test_bases, PrivateUse1TestBase)  # type: ignore[name-defined] # noqa: F821


class SpyreBinaryUfuncsTestBase(SpyreTestBase, PrivateUse1TestBase):  # type: ignore[name-defined] # noqa: F821

    BLACKLISTED_TESTS = _BLACKLISTED
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
