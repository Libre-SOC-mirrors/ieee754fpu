# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2021 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "cat" class, directly equivalent
to nmigen Cat

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/cat
* http://bugs.libre-riscv.org/show_bug.cgi?id=707

m.Switch()
for pbits cases: 0b000 to 0b111
  output = []
  # set up some yielders which will retain where they each got to
  # then when called below in the inner nested loop they give
  # the relevant sequential chunk
  yielders = [Yielder(a), Yielder(b), ....]
  runlist = split pbits into runs of zeros
  for y in yielders: # for each signal a b c d ...
     for i in runlist: # for each partition
        for _ in range(i)+1: # for the length of each partition
            thing = yield from y # grab sequential chunks
            output.append(thing)
  with m.Case(pbits):
     comb += out.eq(Cat(*output)

"""

from nmigen import Signal, Module, Elaboratable, Cat, C
from nmigen.back.pysim import Simulator, Settle

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part.partsig import SimdSignal
from ieee754.part.test.test_partsig import create_simulator


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


class PartitionedCat(Elaboratable):
    def __init__(self, catlist, ctx):
        """Create a ``PartitionedCat`` operator
        """
        # work out the length (total of all SimdSignals)
        self.catlist = catlist
        self.ptype = ctx
        width = 0
        for p in catlist:
            width += len(p.sig)
        self.width = width
        mask = ctx.get_mask()
        self.output = SimdSignal(mask, self.width, reset_less=True)
        self.partition_points = self.output.partpoints
        self.mwidth = len(self.partition_points)+1

    def get_chunk(self, y, idx, numparts):
        x = self.catlist[idx]
        keys = [0] + list(x.partpoints.keys()) + [len(x.sig)]
        # get current index and increment it (for next Cat chunk)
        upto = y[idx]
        y[idx] += numparts
        print ("getting", idx, upto, numparts, keys, len(x.sig))
        # get the partition point as far as we are up to
        start = keys[upto]
        end = keys[upto+numparts]
        print ("start end", start, end, len(x.sig))
        return x.sig[start:end]

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        keys = list(self.partition_points.keys())
        print ("keys", keys, "values", self.partition_points.values())
        print ("ptype", self.ptype)
        with m.Switch(self.ptype.get_switch()):
            # for each partition possibility, create a Cat sequence
            for pbit in self.ptype.get_cases():
                # set up some indices pointing to where things have got
                # then when called below in the inner nested loop they give
                # the relevant sequential chunk
                output = []
                y = [0] * len(self.catlist)
                # get a list of the length of each partition run
                runlengths = get_runlengths(pbit, len(keys))
                print ("pbit", bin(pbit), "runs", runlengths)
                for i in runlengths: # for each partition
                    for yidx in range(len(y)):
                        thing = self.get_chunk(y, yidx, i) # sequential chunks
                        output.append(thing)
                with m.Case(pbit):
                    # direct access to the underlying Signal
                    comb += self.output.sig.eq(Cat(*output))

        return m

    def ports(self):
        res = []
        for p in self.catlist + [self.output]:
            res.append(p.sig)
        return res


if __name__ == "__main__":
    m = Module()
    mask = Signal(3)
    a = SimdSignal(mask, 32)
    b = SimdSignal(mask, 16)
    catlist = [a, b]
    m.submodules.cat = cat = PartitionedCat(catlist, a.ptype)

    traces = cat.ports()
    sim = create_simulator(m, traces, "partcat")

    def process():
        yield mask.eq(0b000)
        yield a.sig.eq(0x01234567)
        yield b.sig.eq(0xfdbc)
        yield Settle()
        out = yield cat.output.sig
        print("out 000", bin(out), hex(out))
        yield mask.eq(0b010)
        yield a.sig.eq(0x01234567)
        yield b.sig.eq(0xfdbc)
        yield Settle()
        out = yield cat.output.sig
        print("out 010", bin(out), hex(out))
        yield mask.eq(0b110)
        yield a.sig.eq(0x01234567)
        yield b.sig.eq(0xfdbc)
        yield Settle()
        out = yield cat.output.sig
        print("out 110", bin(out), hex(out))
        yield mask.eq(0b111)
        yield a.sig.eq(0x01234567)
        yield b.sig.eq(0xfdbc)
        yield Settle()
        out = yield cat.output.sig
        print("out 111", bin(out), hex(out))

    sim.add_process(process)
    with sim.write_vcd("partition_cat.vcd", "partition_cat.gtkw",
                        traces=traces):
        sim.run()
