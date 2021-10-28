#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

from nmigen import Signal, Module, Elaboratable, Mux, Cat, Shape, Repl
from nmigen.back.pysim import Simulator, Delay, Settle
from nmigen.cli import rtlil

from ieee754.part.partsig import SimdSignal, SimdShape
from ieee754.part.simd_scope import SimdScope

from random import randint
import unittest
import itertools
import math


def create_ilang(dut, traces, test_name):
    vl = rtlil.convert(dut, ports=traces)
    with open("%s.il" % test_name, "w") as f:
        f.write(vl)


def create_simulator(module, traces, test_name):
    create_ilang(module, traces, test_name)
    return Simulator(module)


class TestCatMod(Elaboratable):
    def __init__(self, width, elwid, vec_el_counts):
        self.m = Module()
        s = SimdScope(self.m, elwid, vec_el_counts)
        shape = SimdShape(s, fixed_width=width)
        shape2 = SimdShape(s, fixed_width=width*2)
        shape3 = SimdShape(s, fixed_width=width*3)
        self.a = s.Signal(shape)
        self.b = s.Signal(shape2)  # TODO: shape*2
        self.o = s.Signal(shape3)  # TODO: shape*3
        self.cat_out = self.o.sig

    def elaborate(self, platform):
        m = self.m
        comb = m.d.comb

        comb += self.o.eq(Cat(self.a, self.b))

        return m


class TestCat(unittest.TestCase):
    def test(self):
        width = 16
        elwid = Signal(2)  # elwid parameter
        vec_el_counts = {0b00: 1, 0b01: 2, 0b10: 4}
        module = TestCatMod(width, elwid, vec_el_counts)

        test_name = "part_sig_cat_scope"
        traces = [elwid,
                  module.a.sig,
                  module.b.sig,
                  module.cat_out]
        sim = create_simulator(module, traces, test_name)

        # annoying recursive import issue
        from ieee754.part_cat.cat import get_runlengths

        def async_process():

            def test_catop(msg_prefix):
                # define lengths of a/b test input
                alen, blen = 16, 32
                # pairs of test values a, b
                for a, b in [(0x0000, 0x00000000),
                             (0xDCBA, 0x12345678),
                             (0xABCD, 0x01234567),
                             (0xFFFF, 0x0000),
                             (0x0000, 0x0000),
                             (0x1F1F, 0xF1F1F1F1),
                             (0x0000, 0xFFFFFFFF)]:

                    # convert a and b to partitions
                    apart, bpart = [], []
                    ajump, bjump = alen // 4, blen // 4
                    for i in range(4):
                        apart.append((a >> (ajump*i) & ((1 << ajump)-1)))
                        bpart.append((b >> (bjump*i) & ((1 << bjump)-1)))

                    print("apart bpart", hex(a), hex(b),
                          list(map(hex, apart)), list(map(hex, bpart)))

                    yield module.a.lower().eq(a)
                    yield module.b.lower().eq(b)
                    yield Delay(0.1e-6)

                    y = 0
                    # work out the runlengths for this mask.
                    # 0b011 returns [1,1,2] (for a mask of length 3)
                    mval = yield elwid
                    runlengths = get_runlengths(mval, 3)
                    j = 0
                    ai = 0
                    bi = 0
                    for i in runlengths:
                        # a first
                        for _ in range(i):
                            print("runlength", i,
                                  "ai", ai,
                                  "apart", hex(apart[ai]),
                                  "j", j)
                            y |= apart[ai] << j
                            print("    y", hex(y))
                            j += ajump
                            ai += 1
                        # now b
                        for _ in range(i):
                            print("runlength", i,
                                  "bi", bi,
                                  "bpart", hex(bpart[bi]),
                                  "j", j)
                            y |= bpart[bi] << j
                            print("    y", hex(y))
                            j += bjump
                            bi += 1

                    # check the result
                    outval = (yield module.cat_out)
                    msg = f"{msg_prefix}: cat " + \
                        f"0x{mval:X} 0x{a:X} : 0x{b:X}" + \
                        f" => 0x{y:X} != 0x{outval:X}"
                    self.assertEqual(y, outval, msg)

            yield elwid.eq(0b00)
            yield from test_catop("16-bit")
            yield elwid.eq(0b01)
            yield from test_catop("8-bit")
            yield elwid.eq(0b10)
            yield from test_catop("4-bit")

        sim.add_process(async_process)
        with sim.write_vcd(
                vcd_file=open(test_name + ".vcd", "w"),
                gtkw_file=open(test_name + ".gtkw", "w"),
                traces=traces):
            sim.run()


if __name__ == '__main__':
    unittest.main()
