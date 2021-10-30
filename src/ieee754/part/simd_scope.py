# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information
"""
SimdScope class - provides context for SIMD signals to make them useable
under the exact same API as scalar nmigen Signals.

Copyright (C) 2021 Jacob Lifshay
Copyright (C) 2021 Luke Kenneth Casson Leighton

use as:

    m = Module()
    s = SimdScope(m, elwid)
    a = s.Signal(width=64, ....)

    m.d.comb += a.eq(...)

"""

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
        the current elwid (simd element type).  example: Signal(2)
        or Signal(IntElWid)
    """

    def __init__(self, module, elwid, vec_el_counts, scalar=False):

        self.elwid = elwid
        self.vec_el_counts = vec_el_counts
        self.scalar = scalar
        self.set_module(module)

    def set_module(self, module):
        # in SIMD mode, must establish module as part of context and inform
        # the module to operate under "SIMD" Type 1 (AST) casting rules,
        # not the # default "Value.cast" rules.
        if self.scalar:
            return
        self.module = module
        from ieee754.part.partsig import SimdSignal
        if module is not None:
            module._setAstTypeCastFn(SimdSignal.cast)

    def __repr__(self):
        return (f"SimdScope(\n"
                f"        elwid={self.elwid},\n"
                f"        vec_el_counts={self.vec_el_counts},\n")

    ##################
    # from here, the functions are context-aware variants of standard
    # nmigen API (Signal, Signal.like, Shape) which are to be redirected
    # to either their standard scalar nmigen equivalents (verbatim)
    # or to the SimdSignal equivalents.  each one is to be documented
    # CAREFULLY and CLEARLY.
    ##################

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
            # recursive module import resolution
            from ieee754.part.partsig import SimdSignal
            # SIMD mode.  shape here can be either a SimdShape,
            # a Shape, or anything else that Signal can take (int or
            # a tuple (int,bool) for (width,sign)
            s = SimdSignal(mask=self,  # should contain *all* context needed,
                           # which goes all the way through to
                           # the layout() function, passing
                           # 1) elwid 2) vec_el_counts
                           shape=shape,  # should contain the *secondary*
                                       # part of the context needed for
                                       # the layout() function:
                                       # 3) lane_shapes 4) fixed_width
                           name=name, reset=reset,
                           reset_less=reset_less, attrs=attrs,
                           decoder=decoder, src_loc_at=src_loc_at)
            # set the module context so that the SimdSignal can create
            # its own submodules during AST creation
            s.set_module(self.module)
            return s

    # XXX TODO
    def Signal_like(self):
        # if self.scalar:
        #     scalar mode, just return nmigen Signal.like.  THIS IS IMPORTANT.
        # else
        #     simd mode.
        pass

    # XXX TODO
    def Shape(self, width=1, signed=False):
        if self.scalar:
            # scalar mode, just return nmigen Shape.  THIS IS IMPORTANT.
            return Shape(width, signed)
        else:
            # SIMD mode. NOTE: for compatibility with Shape, the width
            # is assumed to be the widths_at_elwid parameter NOT the
            # fixed width.  this ensures that code that is converted
            # straight from scalar to SIMD will have the exact same
            # width at all elwidths, because layout() detects the integer
            # case and converts it, preserving the width at all elwidths
            # the names are preserved to ensure parameter-compatibility
            # with Shape()
            return SimdShape(self, width=width,   # actually widths_at_elwid
                             signed=signed,
                             fixed_width=None)
