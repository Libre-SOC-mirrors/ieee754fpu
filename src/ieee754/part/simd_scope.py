# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information


from ieee754.part.util import (DEFAULT_FP_PART_COUNTS,
                               DEFAULT_INT_PART_COUNTS,
                               FpElWid, IntElWid, SimdMap)
from nmigen.hdl.ast import Signal


class SimdScope:
    """The global scope object for SimdSignal and friends

    Members:
    * part_counts: SimdMap
        a map from `ElWid` values `k` to the number of parts in an element
        when `self.elwid == k`. Values should be minimized, since higher values
        often create bigger circuits.

        Example:
        # here, an I8 element is 1 part wide
        part_counts = {ElWid.I8: 1, ElWid.I16: 2, ElWid.I32: 4, ElWid.I64: 8}

        Another Example:
        # here, an F16 element is 1 part wide
        part_counts = {ElWid.F16: 1, ElWid.BF16: 1, ElWid.F32: 2, ElWid.F64: 4}
    * simd_full_width_hint: int
        the default value for SimdLayout's full_width argument, the full number
        of bits in a SIMD value.
    * elwid: ElWid or nmigen Value with a shape of some ElWid class
        the current elwid (simd element type)
    """

    __SCOPE_STACK = []

    @classmethod
    def get(cls):
        """get the current SimdScope.

        Example:
        SimdScope.get(None) is None
        SimdScope.get() raises ValueError
        with SimdScope(...) as s:
            SimdScope.get() is s
        """
        if len(cls.__SCOPE_STACK) > 0:
            retval = cls.__SCOPE_STACK[-1]
            assert isinstance(retval, SimdScope), "inconsistent scope stack"
            return retval
        raise ValueError("not in a `with SimdScope()` statement")

    def __enter__(self):
        self.__SCOPE_STACK.append(self)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        assert self.__SCOPE_STACK.pop() is self, "inconsistent scope stack"
        return False

    def __init__(self, *, simd_full_width_hint=64, elwid=None,
                 part_counts=None, elwid_type=IntElWid, scalar=False):
        # TODO: add more arguments/members and processing for integration with
        self.simd_full_width_hint = simd_full_width_hint
        if isinstance(elwid, (IntElWid, FpElWid)):
            elwid_type = type(elwid)
            if part_counts is None:
                part_counts = SimdMap({elwid: 1})
        assert issubclass(elwid_type, (IntElWid, FpElWid))
        self.elwid_type = elwid_type
        scalar_elwid = elwid_type(0)
        if part_counts is None:
            if scalar:
                part_counts = SimdMap({scalar_elwid: 1})
            elif issubclass(elwid_type, FpElWid):
                part_counts = DEFAULT_FP_PART_COUNTS
            else:
                part_counts = DEFAULT_INT_PART_COUNTS

        def check(elwid, part_count):
            assert type(elwid) == elwid_type, "inconsistent ElWid types"
            part_count = int(part_count)
            assert part_count != 0 and (part_count & (part_count - 1)) == 0,\
                "part_counts values must all be powers of two"
            return part_count

        self.part_counts = SimdMap.map_with_elwid(check, part_counts)
        self.full_part_count = max(part_counts.values())
        assert self.simd_full_width_hint % self.full_part_count == 0,\
            "simd_full_width_hint must be a multiple of full_part_count"
        if elwid is not None:
            self.elwid = elwid
        elif scalar:
            self.elwid = scalar_elwid
        else:
            self.elwid = Signal(elwid_type)

    def __repr__(self):
        return (f"SimdScope(\n"
                f"        simd_full_width_hint={self.simd_full_width_hint},\n"
                f"        elwid={self.elwid},\n"
                f"        elwid_type={self.elwid_type},\n"
                f"        part_counts={self.part_counts},\n"
                f"        full_part_count={self.full_part_count})")
