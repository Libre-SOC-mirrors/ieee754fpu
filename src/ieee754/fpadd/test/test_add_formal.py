import unittest
from nmutil.formaltest import FHDLTestCase
from ieee754.fpadd.pipeline import FPADDBasePipe
from nmigen.hdl.dsl import Module
from nmigen.hdl.ast import Initial, Assert, AnyConst, Signal, Assume
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
        m.d.comb += expected.eq(AnyConst(width))
        quiet_bit = 1 << (sort.mantissa_field_width - 1)
        nan_exponent = ((1 << sort.eb) - 1) << sort.mantissa_field_width
        with m.If(expected_fp.is_nan().as_value()):
            with m.If(a_fp.is_nan().as_value()):
                m.d.comb += Assume(expected == (a | quiet_bit))
            with m.Elif(b_fp.is_nan().as_value()):
                m.d.comb += Assume(expected == (b | quiet_bit))
            with m.Else():
                m.d.comb += Assume(expected == (nan_exponent | quiet_bit))
        with m.Else():
            m.d.comb += Assume(SmtFloatingPoint.from_bits(expected, sort=sort)
                               .same(expected_fp).as_value())
        m.d.comb += a.eq(AnyConst(width))
        m.d.comb += b.eq(AnyConst(width))
        with m.If(dut.n.trigger):
            m.d.sync += Assert(z_fp.same(expected_fp).as_value())
            m.d.sync += Assert(z == expected)
        self.assertFormal(m, depth=5, solver="bitwuzla")

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
