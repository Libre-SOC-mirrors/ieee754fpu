# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information

from ieee754.part.util import (DEFAULT_FP_VEC_EL_COUNTS,
                               DEFAULT_INT_VEC_EL_COUNTS,
                               FpElWid, IntElWid, SimdMap)
from nmigen.hdl.ast import Signal


class SimdScope:
    """The global scope object for SimdSignal and friends

    Members:
    * vec_el_counts: SimdMap
        a map from `ElWid` values `k` to the number of elements in a vector
        when `self.elwid == k`.

        Example:
        vec_el_counts = SimdMap({
            IntElWid.I64: 1,
            IntElWid.I32: 2,
            IntElWid.I16: 4,
            IntElWid.I8: 8,
        })

        Another Example:
        vec_el_counts = SimdMap({
            FpElWid.F64: 1,
            FpElWid.F32: 2,
            FpElWid.F16: 4,
            FpElWid.BF16: 4,
        })
    * elwid: ElWid or nmigen Value with a shape of some ElWid class
        the current elwid (simd element type)
    """

    __SCOPE_STACK = []

    @classmethod
    def get(cls):
        """get the current SimdScope. raises a ValueError outside of any
        SimdScope.

        Example:
        with SimdScope(...) as s:
            assert SimdScope.get() is s
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

    def __init__(self, *, module, elwid=None,
                 vec_el_counts=None, elwid_type=IntElWid, scalar=False):

        # must establish module as part of context and inform
        # the module to operate under "SIMD" Type 1 (AST) casting rules,
        # not the # default "Value.cast" rules.
        self.module = module
        from ieee754.part.partsig import SimdSignal
        module._setAstTypeCastFn(SimdSignal.cast)

        if isinstance(elwid, (IntElWid, FpElWid)):
            elwid_type = type(elwid)
            if vec_el_counts is None:
                vec_el_counts = SimdMap({elwid: 1})
        assert issubclass(elwid_type, (IntElWid, FpElWid))
        self.elwid_type = elwid_type
        scalar_elwid = elwid_type(0)
        if vec_el_counts is None:
            if scalar:
                vec_el_counts = SimdMap({scalar_elwid: 1})
            elif issubclass(elwid_type, FpElWid):
                vec_el_counts = DEFAULT_FP_VEC_EL_COUNTS
            else:
                vec_el_counts = DEFAULT_INT_VEC_EL_COUNTS

        def check(elwid, vec_el_count):
            assert type(elwid) == elwid_type, "inconsistent ElWid types"
            vec_el_count = int(vec_el_count)
            assert vec_el_count != 0 \
                and (vec_el_count & (vec_el_count - 1)) == 0,\
                "vec_el_counts values must all be powers of two"
            return vec_el_count

        self.vec_el_counts = SimdMap.map_with_elwid(check, vec_el_counts)
        self.full_el_count = max(self.vec_el_counts.values())

        if elwid is not None:
            self.elwid = elwid
        elif scalar:
            self.elwid = scalar_elwid
        else:
            self.elwid = Signal(elwid_type)

    def __repr__(self):
        return (f"SimdScope(\n"
                f"        elwid={self.elwid},\n"
                f"        elwid_type={self.elwid_type},\n"
                f"        vec_el_counts={self.vec_el_counts},\n"
                f"        full_el_count={self.full_el_count})")

