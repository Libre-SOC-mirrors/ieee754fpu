# IEEE Floating Point Divider

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import (StageChain, SimpleHandshake)

from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.postcalc import FPAddStage1Data

# TODO: write these
from .div0 import FPDivStage0Mod
from .div1 import FPDivStage1Mod


class FPDivStages(FPState, SimpleHandshake):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "align")
        self.width = width
        self.id_wid = id_wid
        SimpleHandshake.__init__(self, self) # pipeline is its own stage
        self.m1o = self.ospec()

    def ispec(self):
        return FPSCData(self.width, self.id_wid, False)

    def ospec(self):
        return FPAddStage1Data(self.width, self.id_wid) # AddStage1 ospec

    def setup(self, m, i):
        """ links module to inputs and outputs
        """

        # chain DivStage0 and DivStage1
        m0mod = FPDivStage0Mod(self.width, self.id_wid)
        m1mod = FPDivStage1Mod(self.width, self.id_wid)

        chain = StageChain([m0mod, m1mod])
        chain.setup(m, i)

        self.o = m1mod.o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.m1o.eq(self.process(None))
        m.next = "normalise_1"


