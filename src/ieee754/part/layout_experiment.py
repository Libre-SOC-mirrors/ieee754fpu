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
# note that signed is **NOT** part of the layout, and will NOT
# be added (because it is not relevant or appropriate).
# sign belongs in ast.Shape and is the only appropriate location.
# there is absolutely nothing within this function that in any
# way requires a sign.  it is *purely* performing numerical width
# computations that have absolutely nothing to do with whether the
# actual data is signed or unsigned.
def layout(elwid, vec_el_counts, lane_shapes=None, fixed_width=None):
    """calculate a SIMD layout.

    Glossary:
    * element: a single scalar value that is an element of a SIMD vector.
        it has a width in bits. Every element is made of 1 or
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

    * elwid: ElWid or nmigen Value with ElWid as the shape
        the current element-width

    * vec_el_counts: dict[ElWid, int]
        a map from `ElWid` values `k` to the number of vector elements
        required within a partition when `elwid == k`.

        Example:
        vec_el_counts = {ElWid.I8(==0b11): 8, # 8 vector elements
                       ElWid.I16(==0b10): 4,  # 4 vector elements
                       ElWid.I32(==0b01): 2,  # 2 vector elements
                       ElWid.I64(==0b00): 1}  # 1 vector (aka scalar) element

        Another Example:
        vec_el_counts = {ElWid.BF16(==0b11): 4, # 4 vector elements
                         ElWid.F16(==0b10): 4,  # 4 vector elements
                         ElWid.F32(==0b01): 2,  # 2 vector elements
                         ElWid.F64(==0b00): 1}  # 1 (aka scalar) vector element

    * lane_shapes: int or Mapping[ElWid, int] (optional)
        the bit-width of all elements in a SIMD layout.
        if not provided, the lane_shapes are computed from fixed_width
        and vec_el_counts at each elwidth.

    * fixed_width: int (optional)
        the total width of a SIMD vector. One or both of lane_shapes or
        fixed_width may be provided.  Both may not be left out.
    """
    # when there are no lane_shapes specified, this indicates a
    # desire to use the maximum available space based on the fixed width
    # https://bugs.libre-soc.org/show_bug.cgi?id=713#c67
    if lane_shapes is None:
        assert fixed_width is not None, \
            "both fixed_width and lane_shapes cannot be None"
        lane_shapes = {i: fixed_width // vec_el_counts[i]
                       for i in vec_el_counts}
        print("lane_shapes", fixed_width, lane_shapes)

    # identify if the lane_shapes is a mapping (dict, etc.)
    # if not, then assume that it is an integer (width) that
    # needs to be requested across all partitions
    if not isinstance(lane_shapes, Mapping):
        lane_shapes = {i: lane_shapes for i in vec_el_counts}

    # compute a set of partition widths
    print("lane_shapes", lane_shapes, "vec_el_counts", vec_el_counts)
    cpart_wid = 0
    width = 0
    for i, lwid in lane_shapes.items():
        required_width = lwid * vec_el_counts[i]
        print("     required width", cpart_wid, i, lwid, required_width)
        if required_width > width:
            cpart_wid = lwid
            width = required_width

    # calculate the minumum width required if fixed_width specified
    part_count = max(vec_el_counts.values())
    print("width", width, cpart_wid, part_count)
    if fixed_width is not None:  # override the width and part_wid
        assert width <= fixed_width, "not enough space to fit partitions"
        part_wid = fixed_width // part_count
        assert part_wid * part_count == fixed_width, \
            "calculated width not aligned multiples"
        width = fixed_width
        print("part_wid", part_wid, "count", part_count, "width", width)

    # create the breakpoints dictionary.
    # do multi-stage version https://bugs.libre-soc.org/show_bug.cgi?id=713#c34
    # https://stackoverflow.com/questions/26367812/
    dpoints = defaultdict(list)  # if empty key, create a (empty) list
    for i, c in vec_el_counts.items():
        print("dpoints", i, "count", c)
        # calculate part_wid based on overall width divided by number
        # of elements.
        part_wid = width // c

        def add_p(msg, start, p):
            print("    adding dpoint", msg, start, part_wid, i, c, p)
            dpoints[p].append(i)  # auto-creates list if key non-existent
        # for each elwidth, create the required number of vector elements
        for start in range(c):
            start_bit = start * part_wid
            add_p("start", start, start_bit)  # start of lane
            add_p("end  ", start, start_bit + lane_shapes[i])  # end lane

    # deduplicate dpoints lists
    for k in dpoints.keys():
        dpoints[k] = list({i: None for i in dpoints[k]}.keys())

    # do not need the breakpoints at the very start or the very end
    dpoints.pop(0, None)
    dpoints.pop(width, None)

    # sort dpoints keys
    dpoints = dict(sorted(dpoints.items(), key=lambda i: i[0]))

    print("dpoints")
    pprint(dpoints)

    # second stage, add (map to) the elwidth==i expressions.
    # TODO: use nmutil.treereduce?
    points = {}
    for p in dpoints.keys():
        points[p] = map(lambda i: elwid == i, dpoints[p])
        points[p] = reduce(operator.or_, points[p])

    # third stage, create the binary values which *if* elwidth is set to i
    # *would* result in the mask at that elwidth being set to this value
    # these can easily be double-checked through Assertion
    bitp = {}
    for i in vec_el_counts.keys():
        bitp[i] = 0
        for bit_index, (p, elwidths) in enumerate(dpoints.items()):
            if i in elwidths:
                bitp[i] |= 1 << bit_index

    # fourth stage: determine which partitions are 100% unused.
    # these can then be "blanked out"
    bmask = (1 << len(dpoints)) - 1
    for p in bitp.values():
        bmask &= ~p
    return (PartitionPoints(points), bitp, bmask, width, lane_shapes,
            part_wid)


if __name__ == '__main__':

    # for each element-width (elwidth 0-3) the number of Vector Elements is:
    # elwidth=0b00 QTY 1 partitions:   |          ?          |
    # elwidth=0b01 QTY 1 partitions:   |          ?          |
    # elwidth=0b10 QTY 2 partitions:   |    ?     |     ?    |
    # elwidth=0b11 QTY 4 partitions:   | ?  |  ?  |  ?  | ?  |
    # actual widths of Signals *within* those partitions is given separately
    vec_el_counts = {
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
        pprint((i, layout(i, vec_el_counts, width_in_all_parts)))

    # specify that the Vector Element lengths are to be *different* at
    # each of the elwidths.
    # combined with vec_el_counts we have:
    # elwidth=0b00 1x 5-bit    |<----unused---------->....5|
    # elwidth=0b01 1x 6-bit    |<----unused--------->.....6|
    # elwidth=0b10 2x 6-bit    |unused>.....6|unused>.....6|
    # elwidth=0b11 4x 6-bit    |.....6|.....6|.....6|.....6|
    # expected partitions     (^)     ^      ^      ^^    (^)
    # to be at these points:  (|)     |      |      ||    (|)
    #                         (24)   18     12      65    (0)
    widths_at_elwidth = {
        0: 5,
        1: 6,
        2: 6,
        3: 6
    }

    print("5,6,6,6 elements", widths_at_elwidth)
    for i in range(4):
        pp, bitp, bm, b, c, d = \
            layout(i, vec_el_counts, widths_at_elwidth)
        pprint((i, (pp, bitp, bm, b, c, d)))
    # now check that the expected partition points occur
    print("5,6,6,6 ppt keys", pp.keys())
    assert list(pp.keys()) == [5, 6, 12, 18]

    # this example was probably what the 5,6,6,6 one was supposed to be.
    # combined with vec_el_counts {0:1, 1:1, 2:2, 3:4} we have:
    # elwidth=0b00 1x 24-bit    |.........................24|
    # elwidth=0b01 1x 12-bit    |<--unused--->|...........12|
    # elwidth=0b10 2x 5 -bit    |unused>|....5|unused>|....5|
    # elwidth=0b11 4x 6 -bit    |.....6|.....6|.....6|.....6|
    # expected partitions      (^)     ^^     ^       ^^    (^)
    # to be at these points:   (|)     ||     |       ||    (|)
    #                          (24)   1817   12       65    (0)
    widths_at_elwidth = {
        0: 24,  # QTY 1x 24
        1: 12,  # QTY 1x 12
        2: 5,   # QTY 2x 5
        3: 6    # QTY 4x 6
    }

    print("24,12,5,6 elements", widths_at_elwidth)
    for i in range(4):
        pp, bitp, bm, b, c, d = \
            layout(i, vec_el_counts, widths_at_elwidth)
        pprint((i, (pp, bitp, bm, b, c, d)))
    # now check that the expected partition points occur
    print("24,12,5,6 ppt keys", pp.keys())
    assert list(pp.keys()) == [5, 6, 12, 17, 18]

    # this tests elwidth as an actual Signal. layout is allowed to
    # determine arbitrarily the overall length
    # https://bugs.libre-soc.org/show_bug.cgi?id=713#c30

    elwid = Signal(2)
    pp, bitp, bm, b, c, d = layout(
        elwid, vec_el_counts, widths_at_elwidth)
    pprint((pp, b, c, d))
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
            pprint((i, (ppt, b, c, d)))
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
    pp, bitp, bm, b, c, d = layout(elwid, vec_el_counts,
                                   widths_at_elwidth,
                                   fixed_width=64)
    pprint((pp, b, c, d))
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
            pprint((i, (ppt, b, c, d)))
            # check the results against bitp static-expected partition points
            # https://bugs.libre-soc.org/show_bug.cgi?id=713#c47
            # https://stackoverflow.com/a/27165694
            ival = int(''.join(map(str, ppt[::-1])), 2)
            assert ival == bitp[i], "ival %s actual %s" % (bin(ival),
                                                           bin(bitp[i]))

    sim = Simulator(m)
    sim.add_process(process)
    sim.run()

    # fixed_width=32 and no lane_widths says "allocate maximum"
    # i.e. Vector Element Widths are auto-allocated
    # elwidth=0b00 1x 32-bit    | .................32 |
    # elwidth=0b01 1x 32-bit    | .................32 |
    # elwidth=0b10 2x 12-bit    | ......16 | ......16 |
    # elwidth=0b11 3x 24-bit    | ..8| ..8 | ..8 |..8 |
    # expected partitions      (^)   |     |     |   (^)
    # to be at these points:   (|)   |     |     |    |

    # TODO, fix this so that it is correct.  put it at the end so it
    # shows that things break and doesn't stop the other tests.
    print("maximum allocation from fixed_width=32")
    for i in range(4):
        pprint((i, layout(i, vec_el_counts, fixed_width=32)))

    # example "exponent"
    #  https://libre-soc.org/3d_gpu/architecture/dynamic_simd/shape/
    # 1xFP64: 11 bits, one exponent
    # 2xFP32: 8 bits, two exponents
    # 4xFP16: 5 bits, four exponents
    # 4xBF16: 8 bits, four exponents
    vec_el_counts = {
        0: 1,  # QTY 1x FP64
        1: 2,  # QTY 2x FP32
        2: 4,  # QTY 4x FP16
        3: 4,  # QTY 4x BF16
    }
    widths_at_elwidth = {
        0: 11,  # FP64 ew=0b00
        1: 8,  # FP32 ew=0b01
        2: 5,  # FP16 ew=0b10
        3: 8   # BF16 ew=0b11
    }

    # expected results:
    #
    #        |31|  |  |24|     16|15  |  |   8|7     0 |
    #        |31|28|26|24| |20|16|  12|  |10|8|5|4   0 |
    #  32bit | x| x| x|  |      x|   x| x|10 ....    0 |
    #  16bit | x| x|26    ... 16 |   x| x|10 ....    0 |
    #  8bit  | x|28 .. 24|  20.16|   x|11 .. 8|x|4.. 0 |
    #  unused  x                     x

    print("11,8,5,8 elements (FP64/32/16/BF exponents)", widths_at_elwidth)
    for i in range(4):
        pp, bitp, bm, b, c, d = \
            layout(i, vec_el_counts, widths_at_elwidth,
                   fixed_width=32)
        pprint((i, (pp, bitp, bin(bm), b, c, d)))
    # now check that the expected partition points occur
    print("11,8,5,8 pp keys", pp.keys())
    #assert list(pp.keys()) == [5,6,12,18]

    ######                                                           ######
    ###### 2nd test, different from the above, elwid=0b10 ==> 11 bit ######
    ######                                                           ######

    # example "exponent"
    vec_el_counts = {
        0: 1,  # QTY 1x FP64
        1: 2,  # QTY 2x FP32
        2: 4,  # QTY 4x FP16
        3: 4,  # QTY 4x BF16
    }
    widths_at_elwidth = {
        0: 11,  # FP64 ew=0b00
        1: 11,  # FP32 ew=0b01
        2: 5,  # FP16 ew=0b10
        3: 8   # BF16 ew=0b11
    }

    # expected results:
    #
    #        |31|  |  |24|     16|15  |  |   8|7     0 |
    #        |31|28|26|24| |20|16|  12|  |10|8|5|4   0 |
    #  32bit | x| x| x|  |      x|   x| x|10 ....    0 |
    #  16bit | x| x|26    ... 16 |   x| x|10 ....    0 |
    #  8bit  | x|28 .. 24|  20.16|   x|11 .. 8|x|4.. 0 |
    #  unused  x                     x

    print("11,8,5,8 elements (FP64/32/16/BF exponents)", widths_at_elwidth)
    for i in range(4):
        pp, bitp, bm, b, c, d = \
            layout(i, vec_el_counts, widths_at_elwidth,
                   fixed_width=32)
        pprint((i, (pp, bitp, bin(bm), b, c, d)))
    # now check that the expected partition points occur
    print("11,8,5,8 pp keys", pp.keys())
    #assert list(pp.keys()) == [5,6,12,18]
