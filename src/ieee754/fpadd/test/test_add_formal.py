import unittest
from nmutil.formaltest import FHDLTestCase
from ieee754.fpadd.pipeline import FPADDBasePipe
from nmigen.hdl.dsl import Module
from nmigen.hdl.ast import AnySeq, Assert, AnyConst, Signal, Assume
from nmigen.hdl.smtlib2 import (SmtFloatingPoint, SmtSortFloat16,
                                ROUND_NEAREST_TIES_TO_EVEN)
from ieee754.pipeline import PipelineSpec


class TestFAdd16Formal(FHDLTestCase):
    def test_fadd16_rne_formal(self):
        dut = FPADDBasePipe(PipelineSpec(width=16, id_width=4))
        m = Module()
        m.submodules.dut = dut
        m.d.comb += dut.n.i_ready.eq(AnySeq(1))
        m.d.comb += dut.p.i_valid.eq(AnySeq(1))
        a = dut.p.i_data.a
        b = dut.p.i_data.b
        z = dut.n.o_data.z
        f16 = SmtSortFloat16()
        rm = ROUND_NEAREST_TIES_TO_EVEN
        a_fp = SmtFloatingPoint.from_bits(a, sort=f16)
        b_fp = SmtFloatingPoint.from_bits(b, sort=f16)
        z_fp = SmtFloatingPoint.from_bits(z, sort=f16)
        expected_fp = a_fp.add(b_fp, rm=rm)
        expected = Signal(16)
        m.d.comb += expected.eq(AnySeq(16))
        # Important Note: expected and z won't necessarily match bit-exactly
        # if it's a NaN, all this checks for is z is also any NaN
        m.d.comb += Assume((SmtFloatingPoint.from_bits(expected, sort=f16)
                            == expected_fp).as_value())
        # FIXME: check that it produces the correct NaNs
        m.d.comb += a.eq(AnyConst(16))
        m.d.comb += b.eq(AnyConst(16))
        with m.If(dut.n.trigger):
            m.d.sync += Assert((z_fp == expected_fp).as_value())
        self.assertFormal(m, depth=5, solver="z3")

    # FIXME: check other rounding modes
    # FIXME: check exception flags


if __name__ == '__main__':
    unittest.main()
