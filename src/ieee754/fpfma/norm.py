from nmutil.pipemodbase import PipeModBaseChain, PipeModBase
from ieee754.fpcommon.fpbase import OverflowMod
from ieee754.fpcommon.postnormalise import FPNorm1Data
from ieee754.fpcommon.roundz import FPRoundMod
from ieee754.fpcommon.corrections import FPCorrectionsMod
from ieee754.fpcommon.pack import FPPackMod
from ieee754.fpfma.main_stage import FPFMAPostCalcData
from nmigen.hdl.dsl import Module
from nmigen.hdl.ast import Signal
from ieee754.fpfma.util import get_fpformat
from nmigen.lib.coding import PriorityEncoder


class FPFMANorm(PipeModBase):
    def __init__(self, pspec):
        super().__init__(pspec, "norm")

    def ispec(self):
        return FPFMAPostCalcData(self.pspec)

    def ospec(self):
        return FPNorm1Data(self.pspec)

    def elaborate(self, platform):
        m = Module()
        fpf = get_fpformat(self.pspec)
        assert fpf.has_sign
        inp: FPFMAPostCalcData = self.i
        out: FPNorm1Data = self.o
        m.submodules.pri_enc = pri_enc = PriorityEncoder(inp.mantissa.width)
        m.d.comb += pri_enc.i.eq(inp.mantissa[::-1])
        unrestricted_shift_amount = Signal(range(inp.mantissa.width))
        shift_amount = Signal(range(inp.mantissa.width))
        m.d.comb += unrestricted_shift_amount.eq(pri_enc.o)
        with m.If(inp.exponent - (1 + fpf.e_sub) < unrestricted_shift_amount):
            m.d.comb += shift_amount.eq(inp.exponent - (1 + fpf.e_sub))
        with m.Else():
            m.d.comb += shift_amount.eq(unrestricted_shift_amount)
        n_mantissa = Signal(inp.mantissa.width)
        m.d.comb += n_mantissa.eq(inp.mantissa << shift_amount)

        m.submodules.of = of = OverflowMod()
        m.d.comb += [
            pri_enc.i.eq(inp.mantissa[::-1]),
            of.guard.eq(n_mantissa[-(out.z.m.width + 1)]),
            of.round_bit.eq(n_mantissa[-(out.z.m.width + 2)]),
            of.sticky.eq(n_mantissa[:-(out.z.m.width + 2)].bool()),
            of.m0.eq(out.z.m[0]),
            of.fpflags.eq(0),
            of.sign.eq(inp.sign),
            of.rm.eq(inp.rm),
            out.roundz.eq(of.roundz_out),
            out.z.s.eq(inp.sign),
            out.z.e.eq(inp.exponent - shift_amount),
            out.z.m.eq(n_mantissa[-out.z.m.width:]),
            out.out_do_z.eq(inp.do_bypass),
            out.oz.eq(inp.bypassed_z),
            out.ctx.eq(inp.ctx),
            out.rm.eq(inp.rm),
        ]
        return m


class FPFMANormToPack(PipeModBaseChain):
    def __init__(self, pspec):
        super().__init__(pspec)

    def get_chain(self):
        """ gets chain of modules
        """
        nmod = FPFMANorm(self.pspec)
        rmod = FPRoundMod(self.pspec)
        cmod = FPCorrectionsMod(self.pspec)
        pmod = FPPackMod(self.pspec)
        return [nmod, rmod, cmod, pmod]
