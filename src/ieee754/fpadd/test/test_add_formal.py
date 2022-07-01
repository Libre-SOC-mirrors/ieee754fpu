import unittest
from nmutil.formaltest import FHDLTestCase
from ieee754.fpadd.pipeline import FPADDBasePipe
from nmigen.hdl.dsl import Module
from nmigen.hdl.ast import Initial, Assert, AnyConst, Signal, Assume, Mux
from nmigen.hdl.smtlib2 import SmtFloatingPoint, SmtSortFloatingPoint, \
    SmtSortFloat16, SmtSortFloat32, SmtSortFloat64, SmtBool, \
    SmtRoundingMode, ROUND_TOWARD_POSITIVE, ROUND_TOWARD_NEGATIVE
from ieee754.fpcommon.fpbase import FPRoundingMode
from ieee754.pipeline import PipelineSpec


class TestFAddFSubFormal(FHDLTestCase):
    def tst_fadd_fsub_formal(self, sort, rm, is_sub):
        assert isinstance(sort, SmtSortFloatingPoint)
        assert isinstance(rm, FPRoundingMode)
        assert isinstance(is_sub, bool)
        width = sort.width
        dut = FPADDBasePipe(PipelineSpec(width, id_width=4))
        m = Module()
        m.submodules.dut = dut
        m.d.comb += dut.n.i_ready.eq(True)
        m.d.comb += dut.p.i_valid.eq(Initial())
        m.d.comb += dut.p.i_data.rm.eq(Mux(Initial(), rm, 0))
        out = Signal(width)
        out_full = Signal(reset=False)
        with m.If(dut.n.trigger):
            # check we only got output for one cycle
            m.d.comb += Assert(~out_full)
            m.d.sync += out.eq(dut.n.o_data.z)
            m.d.sync += out_full.eq(True)
        a = Signal(width)
        b = Signal(width)
        m.d.comb += dut.p.i_data.a.eq(Mux(Initial(), a, 0))
        m.d.comb += dut.p.i_data.b.eq(Mux(Initial(), b, 0))
        m.d.comb += dut.p.i_data.is_sub.eq(Mux(Initial(), is_sub, 0))

        smt_add_sub = SmtFloatingPoint.sub if is_sub else SmtFloatingPoint.add
        a_fp = SmtFloatingPoint.from_bits(a, sort=sort)
        b_fp = SmtFloatingPoint.from_bits(b, sort=sort)
        out_fp = SmtFloatingPoint.from_bits(out, sort=sort)
        if rm in (FPRoundingMode.ROUND_TO_ODD_UNSIGNED_ZEROS_ARE_POSITIVE,
                  FPRoundingMode.ROUND_TO_ODD_UNSIGNED_ZEROS_ARE_NEGATIVE):
            rounded_up = Signal(width)
            m.d.comb += rounded_up.eq(AnyConst(width))
            rounded_up_fp = smt_add_sub(a_fp, b_fp, rm=ROUND_TOWARD_POSITIVE)
            rounded_down_fp = smt_add_sub(a_fp, b_fp, rm=ROUND_TOWARD_NEGATIVE)
            m.d.comb += Assume(SmtFloatingPoint.from_bits(
                rounded_up, sort=sort).same(rounded_up_fp).as_value())
            use_rounded_up = SmtBool.make(rounded_up[0])
            if rm is FPRoundingMode.ROUND_TO_ODD_UNSIGNED_ZEROS_ARE_POSITIVE:
                is_zero = rounded_up_fp.is_zero() & rounded_down_fp.is_zero()
                use_rounded_up |= is_zero
            expected_fp = use_rounded_up.ite(rounded_up_fp, rounded_down_fp)
        else:
            smt_rm = SmtRoundingMode.make(rm.to_smtlib2())
            expected_fp = smt_add_sub(a_fp, b_fp, rm=smt_rm)
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
        with m.If(out_full):
            m.d.comb += Assert(out_fp.same(expected_fp).as_value())
            m.d.comb += Assert(out == expected)
        self.assertFormal(m, depth=5, solver="bitwuzla")

    # FIXME: check exception flags

    def test_fadd_f16_rne_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RNE, False)

    def test_fadd_f32_rne_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RNE, False)

    @unittest.skip("too slow")
    def test_fadd_f64_rne_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RNE, False)

    def test_fadd_f16_rtz_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RTZ, False)

    def test_fadd_f32_rtz_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RTZ, False)

    @unittest.skip("too slow")
    def test_fadd_f64_rtz_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RTZ, False)

    def test_fadd_f16_rtp_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RTP, False)

    def test_fadd_f32_rtp_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RTP, False)

    @unittest.skip("too slow")
    def test_fadd_f64_rtp_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RTP, False)

    def test_fadd_f16_rtn_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RTN, False)

    def test_fadd_f32_rtn_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RTN, False)

    @unittest.skip("too slow")
    def test_fadd_f64_rtn_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RTN, False)

    def test_fadd_f16_rna_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RNA, False)

    def test_fadd_f32_rna_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RNA, False)

    @unittest.skip("too slow")
    def test_fadd_f64_rna_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RNA, False)

    def test_fadd_f16_rtop_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RTOP, False)

    def test_fadd_f32_rtop_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RTOP, False)

    @unittest.skip("too slow")
    def test_fadd_f64_rtop_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RTOP, False)

    def test_fadd_f16_rton_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RTON, False)

    def test_fadd_f32_rton_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RTON, False)

    @unittest.skip("too slow")
    def test_fadd_f64_rton_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RTON, False)

    def test_fsub_f16_rne_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RNE, True)

    def test_fsub_f32_rne_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RNE, True)

    @unittest.skip("too slow")
    def test_fsub_f64_rne_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RNE, True)

    def test_fsub_f16_rtz_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RTZ, True)

    def test_fsub_f32_rtz_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RTZ, True)

    @unittest.skip("too slow")
    def test_fsub_f64_rtz_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RTZ, True)

    def test_fsub_f16_rtp_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RTP, True)

    def test_fsub_f32_rtp_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RTP, True)

    @unittest.skip("too slow")
    def test_fsub_f64_rtp_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RTP, True)

    def test_fsub_f16_rtn_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RTN, True)

    def test_fsub_f32_rtn_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RTN, True)

    @unittest.skip("too slow")
    def test_fsub_f64_rtn_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RTN, True)

    def test_fsub_f16_rna_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RNA, True)

    def test_fsub_f32_rna_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RNA, True)

    @unittest.skip("too slow")
    def test_fsub_f64_rna_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RNA, True)

    def test_fsub_f16_rtop_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RTOP, True)

    def test_fsub_f32_rtop_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RTOP, True)

    @unittest.skip("too slow")
    def test_fsub_f64_rtop_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RTOP, True)

    def test_fsub_f16_rton_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat16(), FPRoundingMode.RTON, True)

    def test_fsub_f32_rton_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat32(), FPRoundingMode.RTON, True)

    @unittest.skip("too slow")
    def test_fsub_f64_rton_formal(self):
        self.tst_fadd_fsub_formal(SmtSortFloat64(), FPRoundingMode.RTON, True)

    def test_all_rounding_modes_covered(self):
        for width in 16, 32, 64:
            for rm in FPRoundingMode:
                rm_s = rm.name.lower()
                name = f"test_fadd_f{width}_{rm_s}_formal"
                assert callable(getattr(self, name))
                name = f"test_fsub_f{width}_{rm_s}_formal"
                assert callable(getattr(self, name))


if __name__ == '__main__':
    unittest.main()
