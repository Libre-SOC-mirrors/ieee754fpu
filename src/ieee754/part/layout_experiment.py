#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information
"""
Links:
* https://libre-soc.org/3d_gpu/architecture/dynamic_simd/shape/
* https://bugs.libre-soc.org/show_bug.cgi?id=713#c20
* https://bugs.libre-soc.org/show_bug.cgi?id=713#c30
"""

from nmigen import Signal, Module, Elaboratable, Mux, Cat, Shape, Repl
from nmigen.back.pysim import Simulator, Delay, Settle
from nmigen.cli import rtlil

from collections.abc import Mapping
from functools import reduce
import operator
from collections import defaultdict
from pprint import pprint

from ieee754.part_mul_add.partpoints import PartitionPoints


# main fn
def layout(elwid, signed, part_counts, lane_shapes, fixed_width=None):
    # identify if the lane_shapes is a mapping (dict, etc.)
    # if not, then assume that it is an integer (width) that
    # needs to be requested across all partitions
    if not isinstance(lane_shapes, Mapping):
        lane_shapes = {i: lane_shapes for i in part_counts}
    # compute a set of partition widths
    cpart_wid = -min(-lane_shapes[i] // c for i, c in part_counts.items())
    part_count = max(part_counts.values())
    # calculate the minumum width required
    width = cpart_wid * part_count
    if fixed_width is not None: # override the width and part_wid
        assert width < fixed_width, "not enough space to fit partitions"
        part_wid = fixed_width // part_count
        assert part_wid * part_count == fixed_width, \
                    "calculated width not aligned multiples"
        width = fixed_width
        print ("part_wid", part_wid, "count", part_count)
    else:
        # go with computed width
        part_wid = cpart_wid
    # create the breakpoints dictionary.
    # do multi-stage version https://bugs.libre-soc.org/show_bug.cgi?id=713#c34
    # https://stackoverflow.com/questions/26367812/
    dpoints = defaultdict(list) # if empty key, create a (empty) list
    for i, c in part_counts.items():
        def add_p(p):
            dpoints[p].append(i) # auto-creates list if key non-existent
        for start in range(0, part_count, c):
            add_p(start * part_wid) # start of lane
            add_p(start * part_wid + lane_shapes[i]) # start of padding
    # do not need the breakpoints at the very start or the very end
    dpoints.pop(0, None)
    dpoints.pop(width, None)
    plist = list(dpoints.keys())
    plist.sort()
    print ("dpoints")
    pprint(dict(dpoints))
    # second stage, add (map to) the elwidth==i expressions
    points = {}
    for p in plist:
        points[p] = map(lambda i: elwid == i, dpoints[p])
        points[p] = reduce(operator.or_, points[p])
    # third stage, create the binary values which *if* elwidth is set to i
    # *would* result in the mask at that elwidth being set to this value
    # these can easily be double-checked through Assertion
    bitp = {}
    for i in part_counts.keys():
        bitp[i] = 0
        for p, elwidths in dpoints.items():
            if i in elwidths:
               bitpos = plist.index(p)
               bitp[i] |= 1<< bitpos
    return (PartitionPoints(points), bitp, width, lane_shapes,
        part_wid, part_count)

if __name__ == '__main__':
    part_counts = {
        0: 1,
        1: 1,
        2: 2,
        3: 4,
    }

    for i in range(4):
        pprint((i, layout(i, True, part_counts, 3)))

    l = {0: 5, 1: 6, 2: 12, 3: 24}
    for i in range(4):
        pprint((i, layout(i, False, part_counts, l)))

    # https://bugs.libre-soc.org/show_bug.cgi?id=713#c30
    elwid = Signal(2)
    pp,bitp,b,c,d,e = layout(elwid, False, part_counts, l)
    pprint ((pp,b,c,d,e))
    for k, v in bitp.items():
        print ("bitp elwidth=%d" % k, bin(v))

    m = Module()
    def process():
        for i in range(4):
            yield elwid.eq(i)
            yield Settle()
            ppt = []
            for pval in list(pp.values()):
                val = yield pval # get nmigen to evaluate pp
                ppt.append(val)
            pprint((i, (ppt,b,c,d,e)))
            # check the results against bitp static-expected partition points
            # https://bugs.libre-soc.org/show_bug.cgi?id=713#c47
            # https://stackoverflow.com/a/27165694
            ival = int(''.join(map(str, map(int, ppt))), 2)
            assert ival == bitp[i]

    sim = Simulator(m)
    sim.add_process(process)
    sim.run()

    # set the width fixed
    # https://bugs.libre-soc.org/show_bug.cgi?id=713#c22
    elwid = Signal(2)
    pp,bitp,b,c,d,e = layout(elwid, False, part_counts, l, fixed_width=64)
    pprint ((pp,b,c,d,e))
    for k, v in bitp.items():
        print ("bitp elwidth=%d" % k, bin(v))

    m = Module()
    def process():
        for i in range(4):
            yield elwid.eq(i)
            yield Settle()
            ppt = []
            for pval in list(pp.values()):
                val = yield pval # get nmigen to evaluate pp
                ppt.append(val)
            print ("test elwidth=%d" % i)
            pprint((i, (ppt,b,c,d,e)))
            # check the results against bitp static-expected partition points
            # https://bugs.libre-soc.org/show_bug.cgi?id=713#c47
            # https://stackoverflow.com/a/27165694
            ival = int(''.join(map(str, map(int, ppt))), 2)
            assert ival == bitp[i], "ival %s actual %s" % (bin(ival),
                                                bin(bitp[i]))

    sim = Simulator(m)
    sim.add_process(process)
    sim.run()
