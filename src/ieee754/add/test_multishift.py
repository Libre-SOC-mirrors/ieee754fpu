from nmigen import Module, Signal, Elaboratable
from nmutil.formaltest import FHDLTestCase
from nmutil.sim_util import do_sim, hash_256
import unittest
from ieee754.fpcommon.fpbase import MultiShift, MultiShiftR, MultiShiftRMerge


class MultiShiftModL(Elaboratable):
    def __init__(self, width):
        self.ms = MultiShift(width)
        self.a = Signal(width)
        self.b = Signal(self.ms.smax)
        self.x = Signal(width)

    def elaborate(self, platform=None):

        m = Module()
        m.d.comb += self.x.eq(self.ms.lshift(self.a, self.b))

        return m


class MultiShiftModR(Elaboratable):
    def __init__(self, width):
        self.ms = MultiShift(width)
        self.a = Signal(width)
        self.b = Signal(self.ms.smax)
        self.x = Signal(width)

    def elaborate(self, platform=None):

        m = Module()
        m.d.comb += self.x.eq(self.ms.rshift(self.a, self.b))

        return m


class MultiShiftModRMod(Elaboratable):
    def __init__(self, width):
        self.ms = MultiShiftR(width)
        self.a = Signal(width)
        self.b = Signal(self.ms.smax)
        self.x = Signal(width)

    def elaborate(self, platform=None):

        m = Module()
        m.submodules += self.ms
        m.d.comb += self.ms.i.eq(self.a)
        m.d.comb += self.ms.s.eq(self.b)
        m.d.comb += self.x.eq(self.ms.o)

        return m


class MultiShiftRMergeMod(Elaboratable):
    def __init__(self, width):
        self.ms = MultiShiftRMerge(width)
        self.a = Signal(width)
        self.b = Signal(self.ms.smax)
        self.x = Signal(width)

    def elaborate(self, platform=None):

        m = Module()
        m.submodules += self.ms
        m.d.comb += self.ms.inp.eq(self.a)
        m.d.comb += self.ms.diff.eq(self.b)
        m.d.comb += self.x.eq(self.ms.m)

        return m


class TestMultiShift(FHDLTestCase):
    def check_case(self, dut, width, a, b):
        yield dut.a.eq(a)
        yield dut.b.eq(b)
        yield

        x = (a << b) & ((1 << width) - 1)

        out_x = yield dut.x
        self.assertEqual(
            out_x, x, "Output x 0x%x not equal to expected 0x%x" % (out_x, x))

    def check_caser(self, dut, width, a, b):
        yield dut.a.eq(a)
        yield dut.b.eq(b)
        yield

        x = (a >> b) & ((1 << width) - 1)

        out_x = yield dut.x
        self.assertEqual(
            out_x, x, "Output x 0x%x not equal to expected 0x%x" % (out_x, x))

    def check_case_merge(self, dut, width, a, b):
        yield dut.a.eq(a)
        yield dut.b.eq(b)
        yield

        x = (a >> b) & ((1 << width) - 1)  # actual shift
        if (a & ((2 << b) - 1)) != 0:  # mask for sticky bit
            x |= 1  # set LSB

        out_x = yield dut.x
        self.assertEqual(
            out_x, x, "\nshift %d\nInput\n%+32s\nOutput x\n%+32s != \n%+32s" %
            (b, bin(a), bin(out_x), bin(x)))

    def tst_multi_shift_r_merge(self, width):
        dut = MultiShiftRMergeMod(width=width)

        def process():
            for i in range(width):
                for j in range(1000):
                    a = hash_256(f"MultiShiftRMerge {i} {j}") % (1 << width)
                    yield from self.check_case_merge(dut, width, a, i)

        with do_sim(self, dut, [dut.a, dut.b, dut.x]) as sim:
            sim.add_sync_process(process)
            sim.add_clock(1e-6)
            sim.run()

    def test_multi_shift_r_merge_32(self):
        self.tst_multi_shift_r_merge(32)

    def test_multi_shift_r_merge_24(self):
        self.tst_multi_shift_r_merge(24)

    def tst_multi_shift_r_mod(self, width):
        dut = MultiShiftModRMod(width=width)

        def process():
            for i in range(width):
                for j in range(1000):
                    a = hash_256(f"MultiShiftRMod {i} {j}") % (1 << width)
                    yield from self.check_caser(dut, width, a, i)

        with do_sim(self, dut, [dut.a, dut.b, dut.x]) as sim:
            sim.add_sync_process(process)
            sim.add_clock(1e-6)
            sim.run()

    def test_multi_shift_r_mod_32(self):
        self.tst_multi_shift_r_mod(32)

    def test_multi_shift_r_mod_24(self):
        self.tst_multi_shift_r_mod(24)

    def tst_multi_shift_r(self, width):
        dut = MultiShiftModR(width=width)

        def process():
            for i in range(width):
                for j in range(1000):
                    a = hash_256(f"MultiShiftModR {i} {j}") % (1 << width)
                    yield from self.check_caser(dut, width, a, i)

        with do_sim(self, dut, [dut.a, dut.b, dut.x]) as sim:
            sim.add_sync_process(process)
            sim.add_clock(1e-6)
            sim.run()

    def test_multi_shift_r_32(self):
        self.tst_multi_shift_r(32)

    def test_multi_shift_r_24(self):
        self.tst_multi_shift_r(24)

    def tst_multi_shift_l(self, width):
        dut = MultiShiftModL(width=width)

        def process():
            for i in range(width):
                for j in range(1000):
                    a = hash_256(f"MultiShiftModL {i} {j}") % (1 << width)
                    yield from self.check_case(dut, width, a, i)

        with do_sim(self, dut, [dut.a, dut.b, dut.x]) as sim:
            sim.add_sync_process(process)
            sim.add_clock(1e-6)
            sim.run()

    def test_multi_shift_l_32(self):
        self.tst_multi_shift_l(32)

    def test_multi_shift_l_24(self):
        self.tst_multi_shift_l(24)


if __name__ == '__main__':
    unittest.main()
