import unittest
from nmutil.formaltest import FHDLTestCase
from ieee754.fpfma.pipeline import FPFMABasePipe
from nmigen.hdl.dsl import Module
from nmigen.hdl.ast import Initial, Assert, AnyConst, Signal, Assume, Mux
from nmigen.hdl.smtlib2 import SmtFloatingPoint, SmtSortFloatingPoint, \
    SmtSortFloat16, SmtSortFloat32, SmtSortFloat64, SmtBool, \
    SmtRoundingMode, ROUND_TOWARD_POSITIVE, ROUND_TOWARD_NEGATIVE, SmtBitVec
from ieee754.fpcommon.fpbase import FPFormat, FPRoundingMode
from ieee754.pipeline import PipelineSpec
import os

ENABLE_FMA_F32_FORMAL = os.getenv("ENABLE_FMA_F32_FORMAL") is not None


class TestFMAFormal(FHDLTestCase):
    @unittest.skip("not finished implementing")  # FIXME: remove skip
    def tst_fma_formal(self, sort, rm, negate_addend, negate_product):
        assert isinstance(sort, SmtSortFloatingPoint)
        assert isinstance(rm, FPRoundingMode)
        assert isinstance(negate_addend, bool)
        assert isinstance(negate_product, bool)
        width = sort.width
        pspec = PipelineSpec(width, id_width=4, n_ops=3)
        pspec.fpformat = FPFormat(e_width=sort.eb,
                                  m_width=sort.mantissa_field_width)
        dut = FPFMABasePipe(pspec)
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
        c = Signal(width)
        with m.If(Initial() | True):  # FIXME: remove | True
            m.d.comb += [
                dut.p.i_data.a.eq(a),
                dut.p.i_data.b.eq(b),
                dut.p.i_data.c.eq(c),
                dut.p.i_data.negate_addend.eq(negate_addend),
                dut.p.i_data.negate_product.eq(negate_product),
            ]

        def smt_op(a_fp, b_fp, c_fp, rm):
            assert isinstance(a_fp, SmtFloatingPoint)
            assert isinstance(b_fp, SmtFloatingPoint)
            assert isinstance(c_fp, SmtFloatingPoint)
            assert isinstance(rm, SmtRoundingMode)
            if negate_addend:
                b_fp = -b_fp
            if negate_product:
                a_fp = -a_fp
            return a_fp.fma(c_fp, b_fp, rm=rm)
        a_fp = SmtFloatingPoint.from_bits(a, sort=sort)
        b_fp = SmtFloatingPoint.from_bits(b, sort=sort)
        c_fp = SmtFloatingPoint.from_bits(c, sort=sort)
        out_fp = SmtFloatingPoint.from_bits(out, sort=sort)
        if rm in (FPRoundingMode.ROUND_TO_ODD_UNSIGNED_ZEROS_ARE_POSITIVE,
                  FPRoundingMode.ROUND_TO_ODD_UNSIGNED_ZEROS_ARE_NEGATIVE):
            rounded_up = Signal(width)
            m.d.comb += rounded_up.eq(AnyConst(width))
            rounded_up_fp = smt_op(a_fp, b_fp, c_fp, rm=ROUND_TOWARD_POSITIVE)
            rounded_down_fp = smt_op(a_fp, b_fp, c_fp,
                                     rm=ROUND_TOWARD_NEGATIVE)
            m.d.comb += Assume(SmtFloatingPoint.from_bits(
                rounded_up, sort=sort).same(rounded_up_fp).as_value())
            use_rounded_up = SmtBool.make(rounded_up[0])
            if rm is FPRoundingMode.ROUND_TO_ODD_UNSIGNED_ZEROS_ARE_POSITIVE:
                is_zero = rounded_up_fp.is_zero() & rounded_down_fp.is_zero()
                use_rounded_up |= is_zero
            expected_fp = use_rounded_up.ite(rounded_up_fp, rounded_down_fp)
        else:
            smt_rm = SmtRoundingMode.make(rm.to_smtlib2())
            expected_fp = smt_op(a_fp, b_fp, c_fp, rm=smt_rm)
        expected = Signal(width)
        m.d.comb += expected.eq(AnyConst(width))
        quiet_bit = 1 << (sort.mantissa_field_width - 1)
        nan_exponent = ((1 << sort.eb) - 1) << sort.mantissa_field_width
        with m.If(expected_fp.is_nan().as_value()):
            with m.If(a_fp.is_nan().as_value()):
                m.d.comb += Assume(expected == (a | quiet_bit))
            with m.Elif(b_fp.is_nan().as_value()):
                m.d.comb += Assume(expected == (b | quiet_bit))
            with m.Elif(c_fp.is_nan().as_value()):
                m.d.comb += Assume(expected == (c | quiet_bit))
            with m.Else():
                m.d.comb += Assume(expected == (nan_exponent | quiet_bit))
        with m.Else():
            m.d.comb += Assume(SmtFloatingPoint.from_bits(expected, sort=sort)
                               .same(expected_fp).as_value())
        m.d.comb += a.eq(AnyConst(width))
        m.d.comb += b.eq(AnyConst(width))
        m.d.comb += c.eq(AnyConst(width))
        with m.If(out_full):
            m.d.comb += Assert(out_fp.same(expected_fp).as_value())
            m.d.comb += Assert(out == expected)

        def fp_from_int(v):
            return SmtFloatingPoint.from_signed_bv(
                SmtBitVec.make(v, width=128),
                rm=ROUND_TOWARD_POSITIVE, sort=sort)

        # FIXME: remove:
        if False:
            m.d.comb += Assume(a == 0x05C1)
            m.d.comb += Assume(b == 0x877F)
            m.d.comb += Assume(c == 0x7437)
            with m.If(out_full):
                m.d.comb += Assert(out == 0x0000)
                m.d.comb += Assert(out == 0x0001)

        self.assertFormal(m, depth=5, solver="bitwuzla")

    # FIXME: check exception flags

    def test_fmadd_f16_rne_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RNE,
                            negate_addend=False, negate_product=False)

    def test_fmsub_f16_rne_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RNE,
                            negate_addend=True, negate_product=False)

    def test_fnmadd_f16_rne_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RNE,
                            negate_addend=True, negate_product=True)

    def test_fnmsub_f16_rne_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RNE,
                            negate_addend=False, negate_product=True)

    def test_fmadd_f16_rtz_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTZ,
                            negate_addend=False, negate_product=False)

    def test_fmsub_f16_rtz_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTZ,
                            negate_addend=True, negate_product=False)

    def test_fnmadd_f16_rtz_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTZ,
                            negate_addend=True, negate_product=True)

    def test_fnmsub_f16_rtz_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTZ,
                            negate_addend=False, negate_product=True)

    def test_fmadd_f16_rtp_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTP,
                            negate_addend=False, negate_product=False)

    def test_fmsub_f16_rtp_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTP,
                            negate_addend=True, negate_product=False)

    def test_fnmadd_f16_rtp_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTP,
                            negate_addend=True, negate_product=True)

    def test_fnmsub_f16_rtp_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTP,
                            negate_addend=False, negate_product=True)

    def test_fmadd_f16_rtn_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTN,
                            negate_addend=False, negate_product=False)

    def test_fmsub_f16_rtn_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTN,
                            negate_addend=True, negate_product=False)

    def test_fnmadd_f16_rtn_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTN,
                            negate_addend=True, negate_product=True)

    def test_fnmsub_f16_rtn_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTN,
                            negate_addend=False, negate_product=True)

    def test_fmadd_f16_rna_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RNA,
                            negate_addend=False, negate_product=False)

    def test_fmsub_f16_rna_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RNA,
                            negate_addend=True, negate_product=False)

    def test_fnmadd_f16_rna_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RNA,
                            negate_addend=True, negate_product=True)

    def test_fnmsub_f16_rna_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RNA,
                            negate_addend=False, negate_product=True)

    def test_fmadd_f16_rtop_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTOP,
                            negate_addend=False, negate_product=False)

    def test_fmsub_f16_rtop_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTOP,
                            negate_addend=True, negate_product=False)

    def test_fnmadd_f16_rtop_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTOP,
                            negate_addend=True, negate_product=True)

    def test_fnmsub_f16_rtop_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTOP,
                            negate_addend=False, negate_product=True)

    def test_fmadd_f16_rton_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTON,
                            negate_addend=False, negate_product=False)

    def test_fmsub_f16_rton_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTON,
                            negate_addend=True, negate_product=False)

    def test_fnmadd_f16_rton_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTON,
                            negate_addend=True, negate_product=True)

    def test_fnmsub_f16_rton_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat16(), rm=FPRoundingMode.RTON,
                            negate_addend=False, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmadd_f32_rne_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RNE,
                            negate_addend=False, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmsub_f32_rne_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RNE,
                            negate_addend=True, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmadd_f32_rne_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RNE,
                            negate_addend=True, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmsub_f32_rne_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RNE,
                            negate_addend=False, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmadd_f32_rtz_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTZ,
                            negate_addend=False, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmsub_f32_rtz_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTZ,
                            negate_addend=True, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmadd_f32_rtz_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTZ,
                            negate_addend=True, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmsub_f32_rtz_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTZ,
                            negate_addend=False, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmadd_f32_rtp_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTP,
                            negate_addend=False, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmsub_f32_rtp_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTP,
                            negate_addend=True, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmadd_f32_rtp_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTP,
                            negate_addend=True, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmsub_f32_rtp_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTP,
                            negate_addend=False, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmadd_f32_rtn_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTN,
                            negate_addend=False, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmsub_f32_rtn_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTN,
                            negate_addend=True, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmadd_f32_rtn_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTN,
                            negate_addend=True, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmsub_f32_rtn_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTN,
                            negate_addend=False, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmadd_f32_rna_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RNA,
                            negate_addend=False, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmsub_f32_rna_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RNA,
                            negate_addend=True, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmadd_f32_rna_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RNA,
                            negate_addend=True, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmsub_f32_rna_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RNA,
                            negate_addend=False, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmadd_f32_rtop_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTOP,
                            negate_addend=False, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmsub_f32_rtop_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTOP,
                            negate_addend=True, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmadd_f32_rtop_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTOP,
                            negate_addend=True, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmsub_f32_rtop_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTOP,
                            negate_addend=False, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmadd_f32_rton_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTON,
                            negate_addend=False, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fmsub_f32_rton_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTON,
                            negate_addend=True, negate_product=False)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmadd_f32_rton_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTON,
                            negate_addend=True, negate_product=True)

    @unittest.skipUnless(ENABLE_FMA_F32_FORMAL,
                         "ENABLE_FMA_F32_FORMAL not in environ")
    def test_fnmsub_f32_rton_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat32(), rm=FPRoundingMode.RTON,
                            negate_addend=False, negate_product=True)

    @unittest.skip("too slow")
    def test_fmadd_f64_rne_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RNE,
                            negate_addend=False, negate_product=False)

    @unittest.skip("too slow")
    def test_fmsub_f64_rne_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RNE,
                            negate_addend=True, negate_product=False)

    @unittest.skip("too slow")
    def test_fnmadd_f64_rne_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RNE,
                            negate_addend=True, negate_product=True)

    @unittest.skip("too slow")
    def test_fnmsub_f64_rne_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RNE,
                            negate_addend=False, negate_product=True)

    @unittest.skip("too slow")
    def test_fmadd_f64_rtz_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTZ,
                            negate_addend=False, negate_product=False)

    @unittest.skip("too slow")
    def test_fmsub_f64_rtz_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTZ,
                            negate_addend=True, negate_product=False)

    @unittest.skip("too slow")
    def test_fnmadd_f64_rtz_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTZ,
                            negate_addend=True, negate_product=True)

    @unittest.skip("too slow")
    def test_fnmsub_f64_rtz_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTZ,
                            negate_addend=False, negate_product=True)

    @unittest.skip("too slow")
    def test_fmadd_f64_rtp_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTP,
                            negate_addend=False, negate_product=False)

    @unittest.skip("too slow")
    def test_fmsub_f64_rtp_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTP,
                            negate_addend=True, negate_product=False)

    @unittest.skip("too slow")
    def test_fnmadd_f64_rtp_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTP,
                            negate_addend=True, negate_product=True)

    @unittest.skip("too slow")
    def test_fnmsub_f64_rtp_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTP,
                            negate_addend=False, negate_product=True)

    @unittest.skip("too slow")
    def test_fmadd_f64_rtn_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTN,
                            negate_addend=False, negate_product=False)

    @unittest.skip("too slow")
    def test_fmsub_f64_rtn_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTN,
                            negate_addend=True, negate_product=False)

    @unittest.skip("too slow")
    def test_fnmadd_f64_rtn_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTN,
                            negate_addend=True, negate_product=True)

    @unittest.skip("too slow")
    def test_fnmsub_f64_rtn_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTN,
                            negate_addend=False, negate_product=True)

    @unittest.skip("too slow")
    def test_fmadd_f64_rna_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RNA,
                            negate_addend=False, negate_product=False)

    @unittest.skip("too slow")
    def test_fmsub_f64_rna_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RNA,
                            negate_addend=True, negate_product=False)

    @unittest.skip("too slow")
    def test_fnmadd_f64_rna_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RNA,
                            negate_addend=True, negate_product=True)

    @unittest.skip("too slow")
    def test_fnmsub_f64_rna_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RNA,
                            negate_addend=False, negate_product=True)

    @unittest.skip("too slow")
    def test_fmadd_f64_rtop_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTOP,
                            negate_addend=False, negate_product=False)

    @unittest.skip("too slow")
    def test_fmsub_f64_rtop_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTOP,
                            negate_addend=True, negate_product=False)

    @unittest.skip("too slow")
    def test_fnmadd_f64_rtop_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTOP,
                            negate_addend=True, negate_product=True)

    @unittest.skip("too slow")
    def test_fnmsub_f64_rtop_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTOP,
                            negate_addend=False, negate_product=True)

    @unittest.skip("too slow")
    def test_fmadd_f64_rton_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTON,
                            negate_addend=False, negate_product=False)

    @unittest.skip("too slow")
    def test_fmsub_f64_rton_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTON,
                            negate_addend=True, negate_product=False)

    @unittest.skip("too slow")
    def test_fnmadd_f64_rton_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTON,
                            negate_addend=True, negate_product=True)

    @unittest.skip("too slow")
    def test_fnmsub_f64_rton_formal(self):
        self.tst_fma_formal(sort=SmtSortFloat64(), rm=FPRoundingMode.RTON,
                            negate_addend=False, negate_product=True)

    def test_all_rounding_modes_covered(self):
        for width in 16, 32, 64:
            for rm in FPRoundingMode:
                rm_s = rm.name.lower()
                name = f"test_fmadd_f{width}_{rm_s}_formal"
                assert callable(getattr(self, name))
                name = f"test_fmsub_f{width}_{rm_s}_formal"
                assert callable(getattr(self, name))
                name = f"test_fnmadd_f{width}_{rm_s}_formal"
                assert callable(getattr(self, name))
                name = f"test_fnmsub_f{width}_{rm_s}_formal"
                assert callable(getattr(self, name))


if __name__ == '__main__':
    unittest.main()
