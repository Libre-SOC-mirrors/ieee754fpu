""" test of FPCVTMuxInOut
"""

from ieee754.fcvt.pipeline import (FPCVTMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_single
from ieee754.fcvt.test.fcvt_data_64_32 import regressions

from sfpy import Float64, Float32

def fcvt_32(x):
    return Float32(x)

def test_pipe_fp64_32():
    dut = FPCVTMuxInOut(64, 32, 4)
    run_pipe_fp(dut, 64, "fcvt", unit_test_single, Float64,
                regressions, fcvt_32, 10, True)

if __name__ == '__main__':
    test_pipe_fp64_32()

