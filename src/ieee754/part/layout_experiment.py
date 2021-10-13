#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information
"""
Links:
* https://libre-soc.org/3d_gpu/architecture/dynamic_simd/shape/
* https://bugs.libre-soc.org/show_bug.cgi?id=713#c20
* https://bugs.libre-soc.org/show_bug.cgi?id=713#c30
* https://bugs.libre-soc.org/show_bug.cgi?id=713#c34
* https://bugs.libre-soc.org/show_bug.cgi?id=713#c47
* https://bugs.libre-soc.org/show_bug.cgi?id=713#c22
* https://bugs.libre-soc.org/show_bug.cgi?id=713#c67
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


# main fn, which started out here in the bugtracker:
# https://bugs.libre-soc.org/show_bug.cgi?id=713#c20
def layout(elwid, signed, part_counts, lane_shapes=None, fixed_width=None):
    """calculate a SIMD layout.

    Glossary:
    * element: a single scalar value that is an element of a SIMD vector.
        it has a width in bits, and a signedness. Every element is made of 1 or
        more parts.
    * ElWid: the element-width (really the element type) of an instruction.
        Either an integer or a FP type. Integer `ElWid`s are sign-agnostic.
        In Python, `ElWid` is either an enum type or is `int`.
        Example `ElWid` definition for integers:

        class ElWid(Enum):
            I64 = ...       # SVP64 value 0b00
            I32 = ...       # SVP64 value 0b01
            I16 = ...       # SVP64 value 0b10
            I8 = ...        # SVP64 value 0b11

        Example `ElWid` definition for floats:

        class ElWid(Enum):
            F64 = ...    # SVP64 value 0b00
            F32 = ...    # SVP64 value 0b01
            F16 = ...    # SVP64 value 0b10
            BF16 = ...   # SVP64 value 0b11

    * part: A piece of a SIMD vector, every SIMD vector is made of a
        non-negative integer of parts. Elements are made of a power-of-two
        number of parts. A part is a fixed number of bits wide for each
        different SIMD layout, it doesn't vary when `elwid` changes. A part
        can have a bit width of any non-negative integer, it is not restricted
        to power-of-two. SIMD vectors should have as few parts as necessary,
        since some circuits have size proportional to the number of parts.


    * elwid: ElWid or nmigen Value with ElWid as the shape
        the current element-width
    * signed: bool
        the signedness of all elements in a SIMD layout
    * part_counts: dict[ElWid, int]
        a map from `ElWid` values `k` to the number of parts in an element
        when `elwid == k`. Values should be minimized, since higher values
        often create bigger circuits.

        Example:
        # here, an I8 element is 1 part wide
        part_counts = {ElWid.I8: 1,
                       ElWid.I16: 2,
                       ElWid.I32: 4,
                       ElWid.I64: 8}

        Another Example:
        # here, an F16 element is 1 part wide
        part_counts = {ElWid.F16: 1, ElWid.BF16: 1, ElWid.F32: 2, ElWid.F64: 4}
    * lane_shapes: int or Mapping[ElWid, int] (optional)
        the bit-width of all elements in a SIMD layout.
    * fixed_width: int (optional)
        the total width of a SIMD vector. One of lane_shapes and fixed_width
        must be provided.
    """
    # when there are no lane_shapes specified, this indicates a
    # desire to use the maximum available space based on the fixed width
    # https://bugs.libre-soc.org/show_bug.cgi?id=713#c67
    if lane_shapes is None:
        assert fixed_width is not None, \
            "both fixed_width and lane_shapes cannot be None"
        lane_shapes = {i: fixed_width // part_counts[i] for i in part_counts}
        print("lane_shapes", fixed_width, lane_shapes)
    # identify if the lane_shapes is a mapping (dict, etc.)
    # if not, then assume that it is an integer (width) that
    # needs to be requested across all partitions
    if not isinstance(lane_shapes, Mapping):
        lane_shapes = {i: lane_shapes for i in part_counts}
    # compute a set of partition widths
    cpart_wid = [-lane_shapes[i] // c for i, c in part_counts.items()]
    print("cpart_wid", cpart_wid, "part_counts", part_counts)
    cpart_wid = -min(cpart_wid)
    part_count = max(part_counts.values())
    # calculate the minumum width required
    width = cpart_wid * part_count
    print("width", width, cpart_wid, part_count)
    if fixed_width is not None:  # override the width and part_wid
        assert width < fixed_width, "not enough space to fit partitions"
        part_wid = fixed_width // part_count
        assert part_wid * part_count == fixed_width, \
            "calculated width not aligned multiples"
        width = fixed_width
        print("part_wid", part_wid, "count", part_count)
    else:
        # go with computed width
        part_wid = cpart_wid
    # create the breakpoints dictionary.
    # do multi-stage version https://bugs.libre-soc.org/show_bug.cgi?id=713#c34
    # https://stackoverflow.com/questions/26367812/
    dpoints = defaultdict(list)  # if empty key, create a (empty) list
    for i, c in part_counts.items():
        def add_p(p):
            dpoints[p].append(i)  # auto-creates list if key non-existent
        for start in range(0, part_count, c):
            add_p(start * part_wid)  # start of lane
            add_p(start * part_wid + lane_shapes[i])  # start of padding
    # do not need the breakpoints at the very start or the very end
    dpoints.pop(0, None)
    dpoints.pop(width, None)
    plist = list(dpoints.keys())
    plist.sort()
    print("dpoints")
    pprint(dict(dpoints))
    # second stage, add (map to) the elwidth==i expressions.
    # TODO: use nmutil.treereduce?
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
                bitp[i] |= 1 << bitpos
    # fourth stage: determine which partitions are 100% unused.
    # these can then be "blanked out"
    bmask = (1 << len(plist))-1
    for p in bitp.values():
        bmask &= ~p
    return (PartitionPoints(points), bitp, bmask, width, lane_shapes,
            part_wid, part_count)


if __name__ == '__main__':

    # for each element-width (elwidth 0-3) the number of Vector Elements is:
    # elwidth=0b00 QTY 1 partitions:   |          ?          |
    # elwidth=0b01 QTY 1 partitions:   |          ?          |
    # elwidth=0b10 QTY 2 partitions:   |    ?     |     ?    |
    # elwidth=0b11 QTY 4 partitions:   | ?  |  ?  |  ?  | ?  |
    # actual widths of Signals *within* those partitions is given separately
    part_counts = {
        0: 1,
        1: 1,
        2: 2,
        3: 4,
    }

    # width=3 indicates "same width Vector Elements (3) at all elwidths"
    # elwidth=0b00 1x 5-bit     |  unused xx      ..3 |
    # elwidth=0b01 1x 6-bit     |  unused xx      ..3 |
    # elwidth=0b10 2x 12-bit    | xxx  ..3 | xxx  ..3 |
    # elwidth=0b11 3x 24-bit    | ..3| ..3 | ..3 |..3 |
    # expected partitions      (^)   |     |     |   (^)
    # to be at these points:   (|)   |     |     |    |
    width_in_all_parts = 3

    for i in range(4):
        pprint((i, layout(i, True, part_counts, width_in_all_parts)))

    # fixed_width=32 and no lane_widths says "allocate maximum"
    # i.e. Vector Element Widths are auto-allocated
    # elwidth=0b00 1x 32-bit    | .................32 |
    # elwidth=0b01 1x 32-bit    | .................32 |
    # elwidth=0b10 2x 12-bit    | ......16 | ......16 |
    # elwidth=0b11 3x 24-bit    | ..8| ..8 | ..8 |..8 |
    # expected partitions      (^)   |     |     |   (^)
    # to be at these points:   (|)   |     |     |    |

    # TODO, fix this so that it is correct
    #print ("maximum allocation from fixed_width=32")
    # for i in range(4):
    #    pprint((i, layout(i, True, part_counts, fixed_width=32)))

    # specify that the Vector Element lengths are to be *different* at
    # each of the elwidths.
    # combined with part_counts we have:
    # elwidth=0b00 1x 5-bit     | <--  unused               -->....5 |
    # elwidth=0b01 1x 6-bit     | <--  unused              -->.....6 |
    # elwidth=0b10 2x 12-bit    | unused   .....6 | unused    .....6 |
    # elwidth=0b11 3x 24-bit    | .....6 | .....6 |  .....6 | .....6 |
    # expected partitions      (^)       ^        ^         ^^      (^)
    # to be at these points:   (|)       |        |         ||      (|)
    widths_at_elwidth = {
        0: 5,
        1: 6,
        2: 6,
        3: 6
    }

    print ("5,6,6,6 elements", widths_at_elwidth)
    for i in range(4):
        pprint((i, layout(i, False, part_counts, widths_at_elwidth)))

    # this tests elwidth as an actual Signal. layout is allowed to
    # determine arbitrarily the overall length
    # https://bugs.libre-soc.org/show_bug.cgi?id=713#c30

    elwid = Signal(2)
    pp, bitp, bm, b, c, d, e = layout(
        elwid, False, part_counts, widths_at_elwidth)
    pprint((pp, b, c, d, e))
    for k, v in bitp.items():
        print("bitp elwidth=%d" % k, bin(v))
    print("bmask", bin(bm))

    m = Module()

    def process():
        for i in range(4):
            yield elwid.eq(i)
            yield Settle()
            ppt = []
            for pval in list(pp.values()):
                val = yield pval  # get nmigen to evaluate pp
                ppt.append(val)
            pprint((i, (ppt, b, c, d, e)))
            # check the results against bitp static-expected partition points
            # https://bugs.libre-soc.org/show_bug.cgi?id=713#c47
            # https://stackoverflow.com/a/27165694
            ival = int(''.join(map(str, ppt[::-1])), 2)
            assert ival == bitp[i]

    sim = Simulator(m)
    sim.add_process(process)
    sim.run()

    # this tests elwidth as an actual Signal. layout is *not* allowed to
    # determine arbitrarily the overall length, it is fixed to 64
    # https://bugs.libre-soc.org/show_bug.cgi?id=713#c22

    elwid = Signal(2)
    pp, bitp, bm, b, c, d, e = layout(elwid, False, part_counts,
                                      widths_at_elwidth,
                                      fixed_width=64)
    pprint((pp, b, c, d, e))
    for k, v in bitp.items():
        print("bitp elwidth=%d" % k, bin(v))
    print("bmask", bin(bm))

    m = Module()

    def process():
        for i in range(4):
            yield elwid.eq(i)
            yield Settle()
            ppt = []
            for pval in list(pp.values()):
                val = yield pval  # get nmigen to evaluate pp
                ppt.append(val)
            print("test elwidth=%d" % i)
            pprint((i, (ppt, b, c, d, e)))
            # check the results against bitp static-expected partition points
            # https://bugs.libre-soc.org/show_bug.cgi?id=713#c47
            # https://stackoverflow.com/a/27165694
            ival = int(''.join(map(str, ppt[::-1])), 2)
            assert ival == bitp[i], "ival %s actual %s" % (bin(ival),
                                                           bin(bitp[i]))

    sim = Simulator(m)
    sim.add_process(process)
    sim.run()
