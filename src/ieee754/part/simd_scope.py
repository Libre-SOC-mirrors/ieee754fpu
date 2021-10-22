# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information
"""
SimdScope class - provides context for SIMD signals to make them useable
under the exact same API as scalar nmigen Signals.

Copyright (C) 2021 Jacob Lifshay
Copyright (C) 2021 Luke Kenneth Casson Leighton

use as:

    m = Module()
    with SimdScope(m, elwid) as s:
        a = s.Signal(width=64, ....)

    m.d.comb += a.eq(...)

"""


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

        # in SIMD mode, must establish module as part of context and inform
        # the module to operate under "SIMD" Type 1 (AST) casting rules,
        # not the # default "Value.cast" rules.
        if not scalar:
            self.module = module
            from ieee754.part.partsig import SimdSignal
            module._setAstTypeCastFn(SimdSignal.cast)

        # TODO, explain what this is about
        if isinstance(elwid, (IntElWid, FpElWid)):
            elwid_type = type(elwid)
            if vec_el_counts is None:
                vec_el_counts = SimdMap({elwid: 1})
        assert issubclass(elwid_type, (IntElWid, FpElWid))
        self.elwid_type = elwid_type
        scalar_elwid = elwid_type(0)

        # TODO, explain why this is needed.  Scalar should *NOT*
        # be doing anything other than *DIRECTLY* passing the
        # Signal() arguments *DIRECTLY* to nmigen.Signal.
        # UNDER NO CIRCUMSTANCES should ANY attempt be made to
        # treat SimdSignal as a "scalar Signal".  fuller explanation:
        # https://bugs.libre-soc.org/show_bug.cgi?id=734#c3
        if vec_el_counts is None:
            if scalar:
                vec_el_counts = SimdMap({scalar_elwid: 1})
            elif issubclass(elwid_type, FpElWid):
                vec_el_counts = DEFAULT_FP_VEC_EL_COUNTS
            else:
                vec_el_counts = DEFAULT_INT_VEC_EL_COUNTS

        # TODO, explain this function's purpose
        def check(elwid, vec_el_count):
            assert type(elwid) == elwid_type, "inconsistent ElWid types"
            vec_el_count = int(vec_el_count)
            assert vec_el_count != 0 \
                and (vec_el_count & (vec_el_count - 1)) == 0,\
                "vec_el_counts values must all be powers of two"
            return vec_el_count

        # TODO, explain this
        self.vec_el_counts = SimdMap.map_with_elwid(check, vec_el_counts)
        self.full_el_count = max(self.vec_el_counts.values())

        # TODO, explain this
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

    def Signal(self, shape=None, *, name=None, reset=0, reset_less=False,
                 attrs=None, decoder=None, src_loc_at=0):
        if self.scalar:
            # scalar mode, just return a nmigen Signal.  THIS IS IMPORTANT.
            # when passing in SimdShape it should go "oh, this is
            # an isinstance Shape, i will just use its width and sign"
            # which is the entire reason why SimdShape had to derive
            # from Shape
            return Signal(shape=shape, name=name, reset=reset,
                          reset_less=reset_less, attrs=attrs,
                          decoder=decoder, src_loc_at=src_loc_at)
        else:
            # SIMD mode.  shape here can be either a SimdShape,
            # a Shape, or anything else that Signal can take (int or
            # a tuple (int,bool) for (width,sign)
            s = SimdSignal(mask=self, # should contain *all* context needed,
                                      # which goes all the way through to
                                      # the layout() function, passing
                                      # 1) elwid 2) vec_el_counts
                          shape=shape, # should contain the *secondary*
                                       # part of the context needed for
                                       # the layout() function:
                                       # 3) lane_shapes 4) fixed_width
                          name=name, reset=reset,
                          reset_less=reset_less, attrs=attrs,
                          decoder=decoder, src_loc_at=src_loc_at)
            # set the module context so that the SimdSignal can create
            # its own submodules during AST creation
            s.set_module(self.module)
