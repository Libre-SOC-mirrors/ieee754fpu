# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2021 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

mini demo test of Cat and Assign
"""

from nmigen import Signal, Module, Elaboratable, Cat, Const, signed
from nmigen.back.pysim import Simulator, Settle
from nmutil.extend import ext

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part.partsig import SimdSignal


if __name__ == "__main__":
    from ieee754.part.test.test_partsig import create_simulator
    m = Module()
    mask = Signal(3)
    a = SimdSignal(mask, 16)
    b = SimdSignal(mask, 16)
    o = SimdSignal(mask, 32)
    a.set_module(m)
    b.set_module(m)
    o.set_module(m)

    omask = (1<<len(o)) - 1
    m.d.comb += o.eq(Cat(a, b))

    sim = create_simulator(m, [], "minitest")

    def process():
        yield mask.eq(0b000)
        yield a.sig.eq(0x0123)
        yield b.sig.eq(0x4567)
        yield Settle()
        out = yield o.sig
        print("out 000", bin(out&omask), hex(out&omask))
        yield mask.eq(0b010)
        yield Settle()
        out = yield o.sig
        print("out 010", bin(out&omask), hex(out&omask))
        yield mask.eq(0b110)
        yield Settle()
        out = yield o.sig
        print("out 110", bin(out&omask), hex(out&omask))
        yield mask.eq(0b111)
        yield Settle()
        out = yield o.sig
        print("out 111", bin(out&omask), hex(out&omask))

    sim.add_process(process)
    with sim.write_vcd("partition_minitest.vcd", "partition_partition_ass.gtkw",
                        traces=[]):
        sim.run()

