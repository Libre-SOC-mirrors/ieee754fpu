#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information
"""
Links: https://bugs.libre-soc.org/show_bug.cgi?id=713#c20
"""

from collections.abc import Mapping
from pprint import pprint

# stuff to let it run as stand-alone script
def PartitionPoints(pp):
    return pp

# main fn
def layout(elwid, signed, part_counts, lane_shapes):
    if not isinstance(lane_shapes, Mapping):
        lane_shapes = {i: lane_shapes for i in part_counts}
    part_wid = -min(-lane_shapes[i] // c for i, c in part_counts.items())
    part_count = max(part_counts.values())
    width = part_wid * part_count
    points = {}
    for i, c in part_counts.items():
        def add_p(p):
            points[p] = points.get(p, False) | (elwid == i)
        for start in range(0, part_count, c):
            add_p(start * part_wid) # start of lane
            add_p(start * part_wid + lane_shapes[i]) # start of padding
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

    for i in range(4):
        l = {0: 5, 1: 6, 2: 12, 3: 24}
        pprint((i, layout(i, False, part_counts, l)))
