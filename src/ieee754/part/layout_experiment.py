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
from nmigen.sim import Simulator, Delay, Settle
from nmigen.cli import rtlil
from enum import Enum

from collections.abc import Mapping
from functools import reduce
import operator
from collections import defaultdict
import dataclasses

from ieee754.part_mul_add.partpoints import PartitionPoints


@dataclasses.dataclass
class LayoutResult:
    ppoints: PartitionPoints
    bitp: dict
    bmask: int
    width: int
    lane_shapes: dict
    part_wid: int
    full_part_count: int

    def __repr__(self):
        fields = []
        for field in dataclasses.fields(LayoutResult):
            field_v = getattr(self, field.name)
            if isinstance(field_v, PartitionPoints):
                field_v = ',\n        '.join(
                    f"{k}: {v}" for k, v in field_v.items())
                field_v = f"{{{field_v}}}"
            fields.append(f"{field.name}={field_v}")
        fields = ",\n    ".join(fields)
        return f"LayoutResult({fields})"


# main fn, which started out here in the bugtracker:
# https://bugs.libre-soc.org/show_bug.cgi?id=713#c20
def layout(elwid, signed, part_counts, lane_shapes=None, fixed_width=None):
    """calculate a SIMD layout.

    Glossary:
    * element: a single scalar value that is an element of a SIMD vector.
        it has a width in bits, and a signedness. Every element is made of 1 or
        more parts. An element optionally includes the padding associated with
        it.
    * lane: an element. An element optionally includes the padding associated
        with it.
    * ElWid: the element-width (really the element type) of an instruction.
        Either an integer or a FP type. Integer `ElWid`s are sign-agnostic.
        In Python, `ElWid` is either an enum type or is `int`.
        Example `ElWid` definition for integers:

        class ElWid(Enum):
            I8 = ...
            I16 = ...
            I32 = ...
            I64 = ...

        Example `ElWid` definition for floats:

        class ElWid(Enum):
            F16 = ...
            BF16 = ...
            F32 = ...
            F64 = ...
    * part: (not to be confused with a partition) A piece of a SIMD vector,
        every SIMD vector is made of a non-negative integer of parts. Elements
        are made of a power-of-two number of parts. A part is a fixed number
        of bits wide for each different SIMD layout, it doesn't vary when
        `elwid` changes. A part can have a bit width of any non-negative
        integer, it is not restricted to power-of-two. SIMD vectors should
        have as few parts as necessary, since some circuits have size
        proportional to the number of parts.


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
        part_counts = {ElWid.I8: 1, ElWid.I16: 2, ElWid.I32: 4, ElWid.I64: 8}

        Another Example:
        # here, an F16 element is 1 part wide
        part_counts = {ElWid.F16: 1, ElWid.BF16: 1, ElWid.F32: 2, ElWid.F64: 4}
    * lane_shapes: int or Mapping[ElWid, int] (optional)
        the bit-width of all elements in a SIMD layout.
    * fixed_width: int (optional)
        the total width of a SIMD vector. One of lane_shapes and fixed_width
        must be provided.
    """
    print(f"layout(elwid={elwid},\n"
          f"    signed={signed},\n"
          f"    part_counts={part_counts},\n"
          f"    lane_shapes={lane_shapes},\n"
          f"    fixed_width={fixed_width})")
    assert isinstance(part_counts, Mapping)
    # assert all part_counts are powers of two
    assert all(v != 0 and (v & (v - 1)) == 0 for v in part_counts.values()),\
        "part_counts values must all be powers of two"

    full_part_count = max(part_counts.values())

    # when there are no lane_shapes specified, this indicates a
    # desire to use the maximum available space based on the fixed width
    # https://bugs.libre-soc.org/show_bug.cgi?id=713#c67
    if lane_shapes is None:
        assert fixed_width is not None, \
            "both fixed_width and lane_shapes cannot be None"
        lane_shapes = {}
        for k, cur_part_count in part_counts.items():
            cur_element_count = full_part_count // cur_part_count
            assert fixed_width % cur_element_count == 0, (
                f"fixed_width ({fixed_width}) can't be split evenly into "
                f"{cur_element_count} elements")
            lane_shapes[k] = fixed_width // cur_element_count
        print("lane_shapes", fixed_width, lane_shapes)
    # identify if the lane_shapes is a mapping (dict, etc.)
    # if not, then assume that it is an integer (width) that
    # needs to be requested across all partitions
    if not isinstance(lane_shapes, Mapping):
        lane_shapes = {i: lane_shapes for i in part_counts}
    # calculate the minimum possible bit-width of a part.
    # we divide each element's width by the number of parts in an element,
    # giving the number of bits needed per part.
    # we use `-min(-a // b for ...)` to get `max(ceil(a / b) for ...)`,
    # but using integers.
    min_part_wid = -min(-lane_shapes[i] // c for i, c in part_counts.items())
    # calculate the minimum bit-width required
    min_width = min_part_wid * full_part_count
    print("width", min_width, min_part_wid, full_part_count)
    if fixed_width is not None:  # override the width and part_wid
        assert min_width <= fixed_width, "not enough space to fit partitions"
        part_wid = fixed_width // full_part_count
        assert fixed_width % full_part_count == 0, \
            "fixed_width must be a multiple of full_part_count"
        width = fixed_width
        print("part_wid", part_wid, "count", full_part_count)
    else:
        # go with computed width
        width = min_width
        part_wid = min_part_wid
    # create the breakpoints dictionary.
    # do multi-stage version https://bugs.libre-soc.org/show_bug.cgi?id=713#c34
    # https://stackoverflow.com/questions/26367812/
    # dpoints: dict from bit-index to dict[ElWid, None]
    # we use a dict from ElWid to None as the values of dpoints in order to
    # get an ordered set
    dpoints = defaultdict(dict)  # if empty key, create a (empty) dict
    for i, cur_part_count in part_counts.items():
        def add_p(bit_index):
            # auto-creates dict if key non-existent
            dpoints[bit_index][i] = None
        # go through all elements for elwid `i`, each element starts at
        # part index `start_part`, and goes for `cur_part_count` parts
        for start_part in range(0, full_part_count, cur_part_count):
            start_bit = start_part * part_wid
            add_p(start_bit)  # start of lane
            add_p(start_bit + lane_shapes[i])  # start of padding
    # do not need the breakpoints at the very start or the very end
    dpoints.pop(0, None)
    dpoints.pop(width, None)
    plist = list(dpoints.keys())
    plist.sort()
    print("dpoints")
    for k in plist:
        print(f"{k}: {list(dpoints[k].keys())}")
    # second stage, add (map to) the elwidth==i expressions.
    # TODO: use nmutil.treereduce?
    points = {}
    for p in plist:
        it = map(lambda i: elwid == i, dpoints[p])
        points[p] = reduce(operator.or_, it)
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
    bmask = (1 << len(plist)) - 1
    for p in bitp.values():
        bmask &= ~p
    return LayoutResult(PartitionPoints(points), bitp, bmask, width,
                        lane_shapes, part_wid, full_part_count)


if __name__ == '__main__':

    class FpElWid(Enum):
        F64 = 0
        F32 = 1
        F16 = 2
        BF16 = 3

        def __repr__(self):
            return super().__str__()

    class IntElWid(Enum):
        I64 = 0
        I32 = 1
        I16 = 2
        I8 = 3

        def __repr__(self):
            return super().__str__()

    # for each element-width (elwidth 0-3) the number of parts in an element
    # is given:
    #                                | part0 | part1 | part2 | part3 |
    # elwid=F64 4 parts per element: |<-------------F64------------->|
    # elwid=F32 2 parts per element: |<-----F32----->|<-----F32----->|
    # elwid=F16 1 part per element:  |<-F16->|<-F16->|<-F16->|<-F16->|
    # elwid=BF16 1 part per element: |<BF16->|<BF16->|<BF16->|<BF16->|
    # actual widths of Signals *within* those partitions is given separately
    part_counts = {
        FpElWid.F64: 4,
        FpElWid.F32: 2,
        FpElWid.F16: 1,
        FpElWid.BF16: 1,
    }

    # width=3 indicates "we want the same element bit-width (3) at all elwids"
    # elwid=F64 1x 3-bit     |<--------i3------->|
    # elwid=F32 2x 3-bit     |<---i3-->|<---i3-->|
    # elwid=F16 4x 3-bit     |<i3>|<i3>|<i3>|<i3>|
    # elwid=BF16 4x 3-bit    |<i3>|<i3>|<i3>|<i3>|
    width_for_all_els = 3

    for i in FpElWid:
        print(i, layout(i, True, part_counts, width_for_all_els))

    # fixed_width=32 and no lane_widths says "allocate maximum"
    # elwid=F64 1x 32-bit    |<-------i32------->|
    # elwid=F32 2x 16-bit    |<--i16-->|<--i16-->|
    # elwid=F16 4x 8-bit     |<i8>|<i8>|<i8>|<i8>|
    # elwid=BF16 4x 8-bit    |<i8>|<i8>|<i8>|<i8>|

    print("maximum allocation from fixed_width=32")
    for i in FpElWid:
        print(i, layout(i, True, part_counts, fixed_width=32))

    # specify that the length is to be *different* at each of the elwidths.
    # combined with part_counts we have:
    # elwid=F64 1x 24-bit    |<-------i24------->|
    # elwid=F32 2x 12-bit    |<--i12-->|<--i12-->|
    # elwid=F16 4x 6-bit     |<i6>|<i6>|<i6>|<i6>|
    # elwid=BF16 4x 5-bit    |<i5>|<i5>|<i5>|<i5>|
    widths_at_elwidth = {
        FpElWid.F64: 24,
        FpElWid.F32: 12,
        FpElWid.F16: 6,
        FpElWid.BF16: 5,
    }

    for i in FpElWid:
        print(i, layout(i, False, part_counts, widths_at_elwidth))

    # this tests elwidth as an actual Signal. layout is allowed to
    # determine arbitrarily the overall length
    # https://bugs.libre-soc.org/show_bug.cgi?id=713#c30

    elwid = Signal(FpElWid)
    lr = layout(elwid, False, part_counts, widths_at_elwidth)
    print(lr)
    for k, v in lr.bitp.items():
        print(f"bitp elwidth={k}", bin(v))
    print("bmask", bin(lr.bmask))

    m = Module()

    def process():
        for i in FpElWid:
            yield elwid.eq(i)
            yield Settle()
            ppt = []
            for pval in lr.ppoints.values():
                val = yield pval  # get nmigen to evaluate pp
                ppt.append(val)
            print(i, ppt)
            # check the results against bitp static-expected partition points
            # https://bugs.libre-soc.org/show_bug.cgi?id=713#c47
            # https://stackoverflow.com/a/27165694
            ival = int(''.join(map(str, ppt[::-1])), 2)
            assert ival == lr.bitp[i]

    sim = Simulator(m)
    sim.add_process(process)
    sim.run()

    # this tests elwidth as an actual Signal. layout is *not* allowed to
    # determine arbitrarily the overall length, it is fixed to 64
    # https://bugs.libre-soc.org/show_bug.cgi?id=713#c22

    elwid = Signal(FpElWid)
    lr = layout(elwid, False, part_counts, widths_at_elwidth, fixed_width=64)
    print(lr)
    for k, v in lr.bitp.items():
        print(f"bitp elwidth={k}", bin(v))
    print("bmask", bin(lr.bmask))

    m = Module()

    def process():
        for i in FpElWid:
            yield elwid.eq(i)
            yield Settle()
            ppt = []
            for pval in list(lr.ppoints.values()):
                val = yield pval  # get nmigen to evaluate pp
                ppt.append(val)
            print(f"test elwidth={i}")
            print(i, ppt)
            # check the results against bitp static-expected partition points
            # https://bugs.libre-soc.org/show_bug.cgi?id=713#c47
            # https://stackoverflow.com/a/27165694
            ival = int(''.join(map(str, ppt[::-1])), 2)
            assert ival == lr.bitp[i], \
                f"ival {bin(ival)} actual {bin(lr.bitp[i])}"

    sim = Simulator(m)
    sim.add_process(process)
    sim.run()
