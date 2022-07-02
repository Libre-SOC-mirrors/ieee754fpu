""" floating-point fused-multiply-add

computes `z = (a * c) + b` but only rounds once at the end
"""

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.fpbase import FPRoundingMode
from ieee754.fpfma.special_cases import FPFMASpecialCasesDeNormOutData
from nmigen.hdl.dsl import Module
from nmigen.hdl.ast import Signal, signed, unsigned, Mux
from ieee754.fpfma.util import expanded_exponent_shape, \
    expanded_mantissa_shape, get_fpformat
from ieee754.fpcommon.getop import FPPipeContext


class FPFMAPostCalcData:
    def __init__(self, pspec):
        fpf = get_fpformat(pspec)

        self.sign = Signal()
        """sign"""

        self.exponent = Signal(expanded_exponent_shape(fpf))
        """exponent -- unbiased"""

        self.mantissa = Signal(expanded_mantissa_shape(fpf))
        """unnormalized mantissa"""

        self.bypassed_z = Signal(fpf.width)
        """final output value of the fma when `do_bypass` is set"""

        self.do_bypass = Signal()
        """set if `bypassed_z` is the final output value of the fma"""

        self.ctx = FPPipeContext(pspec)
        """pipe context"""

        self.rm = Signal(FPRoundingMode, reset=FPRoundingMode.DEFAULT)
        """rounding mode"""


class FPFMAMainStage(PipeModBase):
    def __init__(self, pspec):
        super().__init__(pspec, "main")

    def ispec(self):
        return FPFMASpecialCasesDeNormOutData(self.pspec)

    def ospec(self):
        return FPFMAPostCalcData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        fpf = get_fpformat(self.pspec)
        assert fpf.has_sign
        inp = self.i
        out = self.o

        product_v = inp.a_mantissa * inp.c_mantissa
        product = Signal(product_v.shape())
        m.d.comb += product.eq(product_v)
        negate_b_s = Signal(signed(1))
        negate_b_u = Signal(unsigned(1))
        m.d.comb += [
            negate_b_s.eq(inp.do_sub),
            negate_b_u.eq(inp.do_sub),
        ]
        sum_v = product_v + (inp.b_mantissa ^ negate_b_s) + negate_b_u
        sum = Signal(sum_v.shape())
        m.d.comb += sum.eq(sum_v)

        sum_neg = Signal()
        sum_zero = Signal()
        m.d.comb += [
            sum_neg.eq(sum < 0),  # just sign bit
            sum_zero.eq(sum == 0),
        ]

        zero_sign_array = FPRoundingMode.make_array(FPRoundingMode.zero_sign)

        with m.If(sum_zero & ~inp.do_bypass):
            m.d.comb += [
                out.bypassed_z.eq(fpf.zero(zero_sign_array[inp.rm])),
                out.do_bypass.eq(True),
            ]
        with m.Else():
            m.d.comb += [
                out.bypassed_z.eq(inp.bypassed_z),
                out.do_bypass.eq(inp.do_bypass),
            ]

        m.d.comb += [
            out.sign.eq(sum_neg ^ inp.sign),
            out.exponent.eq(inp.exponent),
            out.mantissa.eq(Mux(sum_neg, -sum, sum)),
            out.ctx.eq(inp.ctx),
            out.rm.eq(inp.rm),
        ]
        return m
