#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information
"""
Links: https://bugs.libre-soc.org/show_bug.cgi?id=713#c20
"""

from collections.abc import Mapping
from pprint import pprint
# stuff to let it run as stand-alone script
class Shape:
    @staticmethod
    def cast(v):
        if isinstance(v, Shape):
            return v
        assert isinstance(v, int)
        return Shape(v, False)

    def __init__(self, width=1, signed=False):
        self.width = width
        self.signed = signed

    def __repr__(self):
        if self.signed:
            return f"signed({self.width})"
        return f"unsigned({self.width})"

def signed(w):
    return Shape(w, True)

def unsigned(w):
    return Shape(w, False)

def PartitionPoints(pp):
    return pp

# main fn
def layout(elwid, part_counts, lane_shapes):
    if not isinstance(lane_shapes, Mapping):
        lane_shapes = {i: lane_shapes for i in part_counts}
    lane_shapes = {i: Shape.cast(lane_shapes[i]) for i in part_counts}
    signed = lane_shapes[0].signed
    assert all(i.signed == signed for i in lane_shapes.values())
    part_wid = -min(-lane_shapes[i].width // c for i, c in part_counts.items())
    part_count = max(part_counts.values())
    width = part_wid * part_count
    points = {}
    for i, c in part_counts.items():
        def add_p(p):
            points[p] = points.get(p, False) | (elwid == i)
        for start in range(0, part_count, c):
            add_p(start * part_wid) # start of lane
            add_p(start * part_wid + lane_shapes[i].width) # start of padding
    points.pop(0, None)
    points.pop(width, None)
    return (PartitionPoints(points), Shape(width, signed), lane_shapes,
        part_wid, part_count)

if __name__ == '__main__':
    part_counts = {
        0: 1,
        1: 1,
        2: 2,
        3: 4,
    }

    for i in range(4):
        pprint((i, layout(i, part_counts, unsigned(3))))

    for i in range(4):
        l = {0: signed(5), 1: signed(6), 2: signed(12), 3: signed(24)}
        pprint((i, layout(i, part_counts, l)))
