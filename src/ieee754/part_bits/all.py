# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "all" class, directly equivalent
to Signal.allb() except SIMD-partitionable

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/logicops
* http://bugs.libre-riscv.org/show_bug.cgi?id=176
"""

from nmigen import Signal, Module, Elaboratable, Cat, C
from nmigen.back.pysim import Simulator, Settle
from nmigen.cli import rtlil
from nmutil.ripple import RippleLSB

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part_cmp.experiments.eq_combiner import AllCombiner
from ieee754.part_bits.base import PartitionedBase



class PartitionedAll(PartitionedBase):

    def __init__(self, width, partition_points):
        """Create a ``PartitionedAll`` operator
        """
        super().__init__(width, partition_points, AllCombiner, "all")


if __name__ == "__main__":

    from ieee754.part_mul_add.partpoints import make_partition
    m = Module()
    mask = Signal(4)
    m.submodules.allb = allb = PartitionedAll(16, make_partition(mask, 16))

    vl = rtlil.convert(allb, ports=allb.ports())
    with open("part_allb.il", "w") as f:
        f.write(vl)

    sim = Simulator(m)

    def process():
        yield mask.eq(0b010)
        yield allb.a.eq(0x8c14)
        yield Settle()
        out = yield allb.output
        m = yield mask
        print("out", bin(out), "mask", bin(m))
        yield mask.eq(0b111)
        yield Settle()
        out = yield allb.output
        m = yield mask
        print("out", bin(out), "mask", bin(m))
        yield mask.eq(0b010)
        yield Settle()
        out = yield allb.output
        m = yield mask
        print("out", bin(out), "mask", bin(m))

    sim.add_process(process)
    with sim.write_vcd("part_allb.vcd", "part_allb.gtkw", traces=allb.ports()):
        sim.run()

