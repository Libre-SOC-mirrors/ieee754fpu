import unittest
from nmutil.formaltest import FHDLTestCase
from ieee754.fpadd.pipeline import FPADDBasePipe
from nmigen.hdl.dsl import Module
from nmigen.hdl.ast import AnySeq, Initial, Assert, AnyConst, Signal, Assume
from nmigen.hdl.smtlib2 import SmtFloatingPoint, SmtSortFloatingPoint, \
    SmtSortFloat16, SmtSortFloat32, SmtSortFloat64, \
    ROUND_NEAREST_TIES_TO_EVEN
from ieee754.pipeline import PipelineSpec


class TestFAddFormal(FHDLTestCase):
    def tst_fadd_rne_formal(self, sort):
        assert isinstance(sort, SmtSortFloatingPoint)
        width = sort.width
        dut = FPADDBasePipe(PipelineSpec(width, id_width=4))
        m = Module()
        m.submodules.dut = dut
        m.d.comb += dut.n.i_ready.eq(True)
        m.d.comb += dut.p.i_valid.eq(Initial())
        a = dut.p.i_data.a
        b = dut.p.i_data.b
        z = dut.n.o_data.z
        rm = ROUND_NEAREST_TIES_TO_EVEN
        a_fp = SmtFloatingPoint.from_bits(a, sort=sort)
        b_fp = SmtFloatingPoint.from_bits(b, sort=sort)
        z_fp = SmtFloatingPoint.from_bits(z, sort=sort)
        expected_fp = a_fp.add(b_fp, rm=rm)
        expected = Signal(width)
        m.d.comb += expected.eq(AnySeq(width))
        # Important Note: expected and z won't necessarily match bit-exactly
        # if it's a NaN, all this checks for is z is also any NaN
        m.d.comb += Assume((SmtFloatingPoint.from_bits(expected, sort=sort)
                            == expected_fp).as_value())
        # FIXME: check that it produces the correct NaNs
        m.d.comb += a.eq(AnyConst(width))
        m.d.comb += b.eq(AnyConst(width))
        with m.If(dut.n.trigger):
            m.d.sync += Assert((z_fp == expected_fp).as_value())
        self.assertFormal(m, depth=5, solver="z3")

    # FIXME: check other rounding modes
    # FIXME: check exception flags

    def test_fadd16_rne_formal(self):
        self.tst_fadd_rne_formal(SmtSortFloat16())

    @unittest.skip("too slow")
    def test_fadd32_rne_formal(self):
        self.tst_fadd_rne_formal(SmtSortFloat32())

    @unittest.skip("too slow")
    def test_fadd64_rne_formal(self):
        self.tst_fadd_rne_formal(SmtSortFloat64())



if __name__ == '__main__':
    unittest.main()
