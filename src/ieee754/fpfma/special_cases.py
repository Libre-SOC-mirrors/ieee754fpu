""" floating-point fused-multiply-add

computes `z = (a * c) + b` but only rounds once at the end
"""

from nmutil.pipemodbase import PipeModBase, PipeModBaseChain
from ieee754.fpcommon.basedata import FPBaseData
from nmigen.hdl.ast import Signal
from nmigen.hdl.dsl import Module
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.fpcommon.fpbase import FPRoundingMode, MultiShiftRMerge, FPFormat
from ieee754.fpfma.util import expanded_exponent_shape, \
    expanded_mantissa_shape, multiplicand_mantissa_shape, \
    EXPANDED_MANTISSA_EXTRA_MSBS, EXPANDED_MANTISSA_EXTRA_LSBS, \
    product_mantissa_shape


class FPFMAInputData(FPBaseData):
    def __init__(self, pspec):
        assert pspec.n_ops == 3
        super().__init__(pspec)

        self.negate_addend = Signal()
        """if the addend should be negated"""

        self.negate_product = Signal()
        """if the product should be negated"""

    def eq(self, i):
        ret = super().eq(i)
        ret.append(self.negate_addend.eq(i.negate_addend))
        ret.append(self.negate_product.eq(i.negate_product))
        return ret

    def __iter__(self):
        yield from super().__iter__()
        yield self.negate_addend
        yield self.negate_product

    def ports(self):
        return list(self)


class FPFMASpecialCasesDeNormOutData:
    def __init__(self, pspec):
        fpf = FPFormat.from_pspec(pspec)

        self.sign = Signal()
        """sign"""

        self.exponent = Signal(expanded_exponent_shape(fpf))
        """exponent of intermediate -- unbiased"""

        self.a_mantissa = Signal(multiplicand_mantissa_shape(fpf))
        """mantissa of a input -- un-normalized and with implicit bit added"""

        self.b_mantissa = Signal(expanded_mantissa_shape(fpf))
        """mantissa of b input

        shifted to appropriate location for add and with implicit bit added
        """

        self.c_mantissa = Signal(multiplicand_mantissa_shape(fpf))
        """mantissa of c input -- un-normalized and with implicit bit added"""

        self.do_sub = Signal()
        """true if `b_mantissa` should be subtracted from
        `a_mantissa * c_mantissa` rather than added
        """

        self.bypassed_z = Signal(fpf.width)
        """final output value of the fma when `do_bypass` is set"""

        self.do_bypass = Signal()
        """set if `bypassed_z` is the final output value of the fma"""

        self.ctx = FPPipeContext(pspec)
        """pipe context"""

        self.rm = Signal(FPRoundingMode, reset=FPRoundingMode.DEFAULT)
        """rounding mode"""

    def __iter__(self):
        yield self.sign
        yield self.exponent
        yield self.a_mantissa
        yield self.b_mantissa
        yield self.c_mantissa
        yield self.do_sub
        yield self.bypassed_z
        yield self.do_bypass
        yield from self.ctx
        yield self.rm

    def eq(self, i):
        return [
            self.sign.eq(i.sign),
            self.exponent.eq(i.exponent),
            self.a_mantissa.eq(i.a_mantissa),
            self.b_mantissa.eq(i.b_mantissa),
            self.c_mantissa.eq(i.c_mantissa),
            self.do_sub.eq(i.do_sub),
            self.bypassed_z.eq(i.bypassed_z),
            self.do_bypass.eq(i.do_bypass),
            self.ctx.eq(i.ctx),
            self.rm.eq(i.rm),
        ]


class FPFMASpecialCasesDeNorm(PipeModBase):
    def __init__(self, pspec):
        super().__init__(pspec, "sc_denorm")

    def ispec(self):
        return FPFMAInputData(self.pspec)

    def ospec(self):
        return FPFMASpecialCasesDeNormOutData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        fpf = FPFormat.from_pspec(self.pspec)
        assert fpf.has_sign
        inp = self.i
        out = self.o

        a_exponent = Signal(expanded_exponent_shape(fpf))
        m.d.comb += a_exponent.eq(fpf.get_exponent_value(inp.a))
        b_exponent_in = Signal(expanded_exponent_shape(fpf))
        m.d.comb += b_exponent_in.eq(fpf.get_exponent_value(inp.b))
        c_exponent = Signal(expanded_exponent_shape(fpf))
        m.d.comb += c_exponent.eq(fpf.get_exponent_value(inp.c))
        b_exponent = Signal(expanded_exponent_shape(fpf))
        m.d.comb += b_exponent.eq(b_exponent_in + EXPANDED_MANTISSA_EXTRA_MSBS)
        prod_exponent = Signal(expanded_exponent_shape(fpf))

        # number of bits that the product of two normalized signals needs to
        # be shifted left to be normalized, e.g. the product of 2 8-bit
        # numbers `0x80 * 0x80 == 0x4000` and `0x4000` needs to be shifted
        # left by `PROD_STAY_NORM_SHIFT` bits to be normalized again:
        # `0x4000 << 1 == 0x8000`
        PROD_STAY_NORM_SHIFT = 1

        extra_prod_exponent = (expanded_mantissa_shape(fpf).width
                               - product_mantissa_shape(fpf).width
                               + PROD_STAY_NORM_SHIFT
                               - EXPANDED_MANTISSA_EXTRA_LSBS)
        m.d.comb += prod_exponent.eq(a_exponent + c_exponent
                                     + extra_prod_exponent)
        prod_exp_minus_b_exp = Signal(expanded_exponent_shape(fpf))
        m.d.comb += prod_exp_minus_b_exp.eq(prod_exponent - b_exponent)
        b_mantissa_in = Signal(fpf.fraction_width + 1)
        m.d.comb += b_mantissa_in.eq(fpf.get_mantissa_value(inp.b))
        p_sign = Signal()
        m.d.comb += p_sign.eq(fpf.get_sign_field(inp.a) ^
                              fpf.get_sign_field(inp.c) ^ inp.negate_product)
        b_sign = Signal()
        m.d.comb += b_sign.eq(fpf.get_sign_field(inp.b) ^ inp.negate_addend)

        exponent = Signal(expanded_exponent_shape(fpf))
        b_shift = Signal(expanded_exponent_shape(fpf))
        # use >= since that's just checking the sign bit
        with m.If(prod_exp_minus_b_exp >= 0):
            m.d.comb += [
                exponent.eq(prod_exponent),
                b_shift.eq(prod_exp_minus_b_exp),
            ]
        with m.Else():
            m.d.comb += [
                exponent.eq(b_exponent),
                b_shift.eq(0),
            ]

        m.submodules.rshiftm = rshiftm = MultiShiftRMerge(
            out.b_mantissa.width - EXPANDED_MANTISSA_EXTRA_MSBS,
            s_max=expanded_exponent_shape(fpf).width - 1)
        m.d.comb += [
            rshiftm.inp.eq(0),
            rshiftm.inp[-b_mantissa_in.width:].eq(b_mantissa_in),
            rshiftm.diff.eq(b_shift),
        ]

        keep = {"keep": True}

        # handle special cases
        with m.If(fpf.is_nan(inp.a)):
            m.d.comb += [
                Signal(name="case_nan_a", attrs=keep).eq(True),
                out.bypassed_z.eq(fpf.to_quiet_nan(inp.a)),
                out.do_bypass.eq(True),
            ]
        with m.Elif(fpf.is_nan(inp.b)):
            m.d.comb += [
                Signal(name="case_nan_b", attrs=keep).eq(True),
                out.bypassed_z.eq(fpf.to_quiet_nan(inp.b)),
                out.do_bypass.eq(True),
            ]
        with m.Elif(fpf.is_nan(inp.c)):
            m.d.comb += [
                Signal(name="case_nan_c", attrs=keep).eq(True),
                out.bypassed_z.eq(fpf.to_quiet_nan(inp.c)),
                out.do_bypass.eq(True),
            ]
        with m.Elif((fpf.is_zero(inp.a) & fpf.is_inf(inp.c))
                    | (fpf.is_inf(inp.a) & fpf.is_zero(inp.c))):
            # infinity * 0
            m.d.comb += [
                Signal(name="case_inf_times_zero", attrs=keep).eq(True),
                out.bypassed_z.eq(fpf.quiet_nan()),
                out.do_bypass.eq(True),
            ]
        with m.Elif((fpf.is_inf(inp.a) | fpf.is_inf(inp.c))
                    & fpf.is_inf(inp.b) & (p_sign != b_sign)):
            # inf - inf
            m.d.comb += [
                Signal(name="case_inf_minus_inf", attrs=keep).eq(True),
                out.bypassed_z.eq(fpf.quiet_nan()),
                out.do_bypass.eq(True),
            ]
        with m.Elif(fpf.is_inf(inp.a) | fpf.is_inf(inp.c)):
            # inf + x
            m.d.comb += [
                Signal(name="case_inf_plus_x", attrs=keep).eq(True),
                out.bypassed_z.eq(fpf.inf(p_sign)),
                out.do_bypass.eq(True),
            ]
        with m.Elif(fpf.is_inf(inp.b)):
            # x + inf
            m.d.comb += [
                Signal(name="case_x_plus_inf", attrs=keep).eq(True),
                out.bypassed_z.eq(fpf.inf(b_sign)),
                out.do_bypass.eq(True),
            ]
        with m.Elif((fpf.is_zero(inp.a) | fpf.is_zero(inp.c))
                    & fpf.is_zero(inp.b) & (p_sign == b_sign)):
            # zero + zero
            m.d.comb += [
                Signal(name="case_zero_plus_zero", attrs=keep).eq(True),
                out.bypassed_z.eq(fpf.zero(p_sign)),
                out.do_bypass.eq(True),
            ]
        with m.Elif((fpf.is_zero(inp.a) | fpf.is_zero(inp.c))
                    & ~fpf.is_zero(inp.b)):
            # zero + x
            m.d.comb += [
                Signal(name="case_zero_plus_x", attrs=keep).eq(True),
                out.bypassed_z.eq(inp.b ^ fpf.zero(inp.negate_addend)),
                out.do_bypass.eq(True),
            ]
        with m.Else():
            # zero - zero handled by FPFMAMainStage
            m.d.comb += [
                out.bypassed_z.eq(0),
                out.do_bypass.eq(False),
            ]

        m.d.comb += [
            out.sign.eq(p_sign),
            out.exponent.eq(exponent),
            out.a_mantissa.eq(fpf.get_mantissa_value(inp.a)),
            out.b_mantissa.eq(rshiftm.m),
            out.c_mantissa.eq(fpf.get_mantissa_value(inp.c)),
            out.do_sub.eq(p_sign != b_sign),
            out.ctx.eq(inp.ctx),
            out.rm.eq(inp.rm),
        ]

        return m


class FPFMASpecialCasesDeNormStage(PipeModBaseChain):
    def __init__(self, pspec):
        super().__init__(pspec)

    def get_chain(self):
        """ gets chain of modules
        """
        return [FPFMASpecialCasesDeNorm(self.pspec)]
