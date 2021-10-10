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
from pprint import pprint

from ieee754.part_mul_add.partpoints import PartitionPoints


# main fn
def layout(elwid, signed, part_counts, lane_shapes):
    # identify if the lane_shapes is a mapping (dict, etc.)
    # if not, then assume that it is an integer (width) that
    # needs to be requested across all partitions
    if not isinstance(lane_shapes, Mapping):
        lane_shapes = {i: lane_shapes for i in part_counts}
    # compute a set of partition widths
    part_wid = -min(-lane_shapes[i] // c for i, c in part_counts.items())
    part_count = max(part_counts.values())
    # calculate the minumum width required
    width = part_wid * part_count
    # create the breakpoints dictionary
    points = {}
    for i, c in part_counts.items():
        def add_p(p):
            points[p] = points.get(p, False) | (elwid == i)
        for start in range(0, part_count, c):
            add_p(start * part_wid) # start of lane
            add_p(start * part_wid + lane_shapes[i]) # start of padding
    # do not need the breakpoints at the very start or the very end
    points.pop(0, None)
    points.pop(width, None)
    return (PartitionPoints(points), width, lane_shapes,
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
    pp,b,c,d,e = layout(elwid, False, part_counts, l)
    pprint ((pp,b,c,d,e))

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
    sim = Simulator(m)
    sim.add_process(process)
    sim.run()
