# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2021 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "repl" class, directly equivalent
to nmigen Repl

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/repl
* http://bugs.libre-riscv.org/show_bug.cgi?id=709

"""

from nmigen import Signal, Module, Elaboratable, Cat, Repl
from nmigen.back.pysim import Simulator, Settle
from nmigen.cli import rtlil

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part.partsig import PartitionedSignal


def get_runlengths(pbit, size):
    res = []
    count = 1
    # identify where the 1s are, which indicates "start of a new partition"
    # we want a list of the lengths of all partitions
    for i in range(size):
        if pbit & (1<<i): # it's a 1: ends old partition, starts new
            res.append(count) # add partition
            count = 1 # start again
        else:
            count += 1
    # end reached, add whatever is left. could have done this by creating
    # "fake" extra bit on the partitions, but hey
    res.append(count)

    print ("get_runlengths", bin(pbit), size, res)

    return res


class PartitionedRepl(Elaboratable):
    def __init__(self, repl, qty, mask):
        """Create a ``PartitionedRepl`` operator
        """
        # work out the length (total of all PartitionedSignals)
        self.repl = repl
        self.qty = qty
        width, signed = repl.shape()
        if isinstance(mask, dict):
            mask = list(mask.values())
        self.mask = mask
        self.shape = (width * qty), signed
        self.output = PartitionedSignal(mask, self.shape, reset_less=True)
        self.partition_points = self.output.partpoints
        self.mwidth = len(self.partition_points)+1

    def get_chunk(self, y, numparts):
        x = self.repl
        if not isinstance(x, PartitionedSignal):
            # assume Scalar. totally different rules
            end = numparts * (len(x) // self.mwidth)
            return x[:end]
        # PartitionedSignal: start at partition point
        keys = [0] + list(x.partpoints.keys()) + [len(x)]
        # get current index and increment it (for next Repl chunk)
        upto = y[0]
        y[0] += numparts
        print ("getting", upto, numparts, keys, len(x))
        # get the partition point as far as we are up to
        start = keys[upto]
        end = keys[upto+numparts]
        print ("start end", start, end, len(x))
        return x[start:end]

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        keys = list(self.partition_points.keys())
        print ("keys", keys, "values", self.partition_points.values())
        print ("mask", self.mask)
        outpartsize = len(self.output) // self.mwidth
        width, signed = self.output.shape()
        print ("width, signed", width, signed)

        with m.Switch(Cat(self.mask)):
            # for each partition possibility, create a Repl sequence
            for pbit in range(1<<len(keys)):
                # set up some indices pointing to where things have got
                # then when called below in the inner nested loop they give
                # the relevant sequential chunk
                output = []
                y = [0]
                # get a list of the length of each partition run
                runlengths = get_runlengths(pbit, len(keys))
                print ("pbit", bin(pbit), "runs", runlengths)
                for i in runlengths:                     # for each partition
                    thing = self.get_chunk(y, i)         # get sequential chunk
                    output.append(Repl(thing, self.qty)) # and replicate it
                with m.Case(pbit):
                    # direct access to the underlying Signal
                    comb += self.output.sig.eq(Cat(*output)) # cat all chunks

        return m

    def ports(self):
        if isinstance(self.repl, PartitionedSignal):
            return [self.repl.lower(), self.output.lower()]
        return [self.repl, self.output.lower()]


if __name__ == "__main__":
    from ieee754.part.test.test_partsig import create_simulator
    m = Module()
    mask = Signal(3)
    a = PartitionedSignal(mask, 32)
    m.submodules.repl = repl = PartitionedRepl(a, 2, mask)
    omask = (1<<len(repl.output))-1

    traces = repl.ports()
    vl = rtlil.convert(repl, ports=traces)
    with open("part_repl.il", "w") as f:
        f.write(vl)

    sim = create_simulator(m, traces, "partrepl")

    def process():
        yield mask.eq(0b000)
        yield a.sig.eq(0xa12345c7)
        yield Settle()
        out = yield repl.output.sig
        print("out 000", bin(out&omask), hex(out&omask))
        yield mask.eq(0b010)
        yield Settle()
        out = yield repl.output.sig
        print("out 010", bin(out&omask), hex(out&omask))
        yield mask.eq(0b110)
        yield Settle()
        out = yield repl.output.sig
        print("out 110", bin(out&omask), hex(out&omask))
        yield mask.eq(0b111)
        yield Settle()
        out = yield repl.output.sig
        print("out 111", bin(out&omask), hex(out&omask))

    sim.add_process(process)
    with sim.write_vcd("partition_repl.vcd", "partition_repl.gtkw",
                        traces=traces):
        sim.run()

    # Scalar
    m = Module()
    mask = Signal(3)
    a = Signal(32)
    m.submodules.ass = ass = PartitionedRepl(a, 2, mask)
    omask = (1<<len(ass.output))-1

    traces = ass.ports()
    sim = create_simulator(m, traces, "partass")

    def process():
        yield mask.eq(0b000)
        yield a.eq(0xa12345c7)
        yield Settle()
        out = yield ass.output.sig
        print("out 000", bin(out&omask), hex(out&omask))
        yield mask.eq(0b010)
        yield Settle()
        out = yield ass.output.sig
        print("out 010", bin(out&omask), hex(out&omask))
        yield mask.eq(0b110)
        yield Settle()
        out = yield ass.output.sig
        print("out 110", bin(out&omask), hex(out&omask))
        yield mask.eq(0b111)
        yield Settle()
        out = yield ass.output.sig
        print("out 111", bin(out&omask), hex(out&omask))

    sim.add_process(process)
    with sim.write_vcd("partition_repl_scalar.vcd",
                       "partition_repl_scalar.gtkw",
                        traces=traces):
        sim.run()
