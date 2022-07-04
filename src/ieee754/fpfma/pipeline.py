""" floating-point fused-multiply-add

computes `z = (a * c) + b` but only rounds once at the end
"""

from nmutil.singlepipe import ControlBase
from ieee754.fpfma.special_cases import FPFMASpecialCasesDeNormStage
from ieee754.fpfma.main_stage import FPFMAMainStage
from ieee754.fpfma.norm import FPFMANormToPack


class FPFMABasePipe(ControlBase):
    def __init__(self, pspec):
        super().__init__()
        self.sc_denorm = FPFMASpecialCasesDeNormStage(pspec)
        self.main = FPFMAMainStage(pspec)
        self.normpack = FPFMANormToPack(pspec)
        self._eqs = self.connect([self.sc_denorm, self.main, self.normpack])

    def elaborate(self, platform):
        m = super().elaborate(platform)
        m.submodules.sc_denorm = self.sc_denorm
        m.submodules.main = self.main
        m.submodules.normpack = self.normpack
        m.d.comb += self._eqs
        return m
