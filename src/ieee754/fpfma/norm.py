from nmutil.pipemodbase import PipeModBaseChain, PipeModBase
from ieee754.fpcommon.postnormalise import FPNorm1Data
from ieee754.fpcommon.roundz import FPRoundMod
from ieee754.fpcommon.corrections import FPCorrectionsMod
from ieee754.fpcommon.pack import FPPackMod
from ieee754.fpfma.main_stage import FPFMAPostCalcData
from nmigen.hdl.dsl import Module

from ieee754.fpfma.util import get_fpformat


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
        inp = self.i
        out = self.o
        raise NotImplementedError  # FIXME: finish
        m.d.comb += [
            out.roundz.eq(),
            out.z.eq(),
            out.out_do_z.eq(),
            out.oz.eq(),
            out.ctx.eq(),
            out.rm.eq(),
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
