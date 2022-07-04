# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.fpbase import FPFormat, FPNumBaseRecord, FPNumBase, \
    FPRoundingMode
from ieee754.fpcommon.roundz import FPRoundData
from ieee754.fpcommon.packdata import FPPackData


class FPPackMod(PipeModBase):

    def __init__(self, pspec):
        super().__init__(pspec, "pack")

    def ispec(self):
        return FPRoundData(self.pspec)

    def ospec(self):
        return FPPackData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        z = FPNumBaseRecord(m_extra=False, name="z",
                            fpformat=FPFormat.from_pspec(self.pspec))
        m.submodules.pack_in_z = in_z = FPNumBase(self.i.z)
        overflow_array = FPRoundingMode.make_array(
            lambda rm: rm.overflow_rounds_to_inf(self.i.z.s))
        overflow_rounds_to_inf = Signal()
        m.d.comb += overflow_rounds_to_inf.eq(overflow_array[self.i.rm])

        with m.If(~self.i.out_do_z):
            with m.If(in_z.is_overflowed):
                with m.If(overflow_rounds_to_inf):
                    comb += z.inf(self.i.z.s)
                with m.Else():
                    comb += z.max_normal(self.i.z.s)
            with m.Else():
                comb += z.create(self.i.z.s, self.i.z.e, self.i.z.m)
        with m.Else():
            comb += z.v.eq(self.i.oz)

        comb += self.o.ctx.eq(self.i.ctx)
        comb += self.o.z.eq(z.v)

        return m
