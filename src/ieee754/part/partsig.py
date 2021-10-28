# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamic-partitionable class similar to Signal, which, when the partition
is fully open will be identical to Signal.  when partitions are closed,
the class turns into a SIMD variant of Signal.  *this is dynamic*.

the basic fundamental idea is: write code once, and if you want a SIMD
version of it, use SimdSignal in place of Signal.  job done.
this however requires the code to *not* be designed to use nmigen.If,
nmigen.Case, or other constructs: only Mux and other logic.

* http://bugs.libre-riscv.org/show_bug.cgi?id=132
"""

from ieee754.part_mul_add.adder import PartitionedAdder
from ieee754.part_cmp.eq_gt_ge import PartitionedEqGtGe
from ieee754.part_bits.xor import PartitionedXOR
from ieee754.part_bits.bool import PartitionedBool
from ieee754.part_bits.all import PartitionedAll
from ieee754.part_shift.part_shift_dynamic import PartitionedDynamicShift
from ieee754.part_shift.part_shift_scalar import PartitionedScalarShift
from ieee754.part_mul_add.partpoints import make_partition2, PartitionPoints
from ieee754.part_mux.part_mux import PMux
from ieee754.part_ass.passign import PAssign
from ieee754.part_cat.pcat import PCat
from ieee754.part_repl.prepl import PRepl
from ieee754.part.simd_scope import SimdScope
from ieee754.part.layout_experiment import layout
from operator import or_, xor, and_, not_

from nmigen import (Signal, Const, Cat)
from nmigen.hdl.ast import UserValue, Shape


def getsig(op1):
    if isinstance(op1, SimdSignal):
        op1 = op1.sig
    return op1


def applyop(op1, op2, op):
    if isinstance(op1, SimdSignal):
        result = SimdSignal.like(op1)
    else:
        result = SimdSignal.like(op2)
    result.m.d.comb += result.sig.eq(op(getsig(op1), getsig(op2)))
    return result


global modnames
modnames = {}
# for sub-modules to be created on-demand. Mux is done slightly
# differently (has its own global)
for name in ['add', 'eq', 'gt', 'ge', 'ls', 'xor', 'bool', 'all']:
    modnames[name] = 0


def get_runlengths(pbit, size):
    res = []
    count = 1
    # identify where the 1s are, which indicates "start of a new partition"
    # we want a list of the lengths of all partitions
    for i in range(size):
        if pbit & (1 << i):  # it's a 1: ends old partition, starts new
            res.append(count)  # add partition
            count = 1  # start again
        else:
            count += 1
    # end reached, add whatever is left. could have done this by creating
    # "fake" extra bit on the partitions, but hey
    res.append(count)

    return res


# Prototype https://bugs.libre-soc.org/show_bug.cgi?id=713#c53
# this provides a "compatibility" layer with existing SimdSignal
# behaviour.  the idea is that this interface defines which "combinations"
# of partition selections are relevant, and as an added bonus it says
# which partition lanes are completely irrelevant (padding, blank).
class PartType:  # TODO decide name
    def __init__(self, psig):
        self.psig = psig

    def get_mask(self):
        return list(self.psig.partpoints.values())

    def get_switch(self):
        return Cat(self.get_mask())

    def get_cases(self):
        return range(1 << len(self.get_mask()))

    def get_num_elements(self, pbit):
        keys = list(self.psig.partpoints.keys())
        return len(get_runlengths(pbit, len(keys)))

    def get_el_range(self, pbit, el_num):
        """based on the element number and the current elwid/pbit (case)
        return the range start/end of the element within its underlying signal
        this function is not at all designed to be efficient.
        """
        keys = list(self.psig.partpoints.keys())
        runs = get_runlengths(pbit, len(keys))
        keys = [0] + keys + [len(self.psig.sig)]
        y = 0
        for i in range(el_num):
            numparts = runs[i]
            y += numparts
        numparts = runs[el_num]
        return range(keys[y], keys[y+numparts])

    @property
    def blanklanes(self):
        return 0


# this one would be an elwidth version
# see https://bugs.libre-soc.org/show_bug.cgi?id=713#c34
# it requires an "adapter" which is the layout() function
# where the PartitionPoints was *created* by the layout()
# function and this class then "understands" the relationship
# between elwidth and the PartitionPoints that were created
# by layout()
class ElwidPartType:  # TODO decide name
    def __init__(self, psig):
        self.psig = psig

    def get_mask(self):
        return list(self.psig._shape.partpoints.values())  # i think

    def get_switch(self):
        return self.psig.scope.elwid       # switch on elwid: match get_cases()

    def get_cases(self):
        return self.psig._shape.bitp.keys()  # all possible values of elwid

    @property
    def blanklanes(self):
        return self.psig.shape.blankmask


# declares priority of the SimdShape
PRIORITY_FIXED = 0b01
PRIORITY_ELWID = 0b10
PRIORITY_BOTH  = 0b11

class SimdShape(Shape):
    """a SIMD variant of Shape. supports:
    * fixed overall width with variable (maxed-out) element lengths
    * fixed element widths with overall size auto-determined
    * both fixed overall width and fixed element widths

    Documentation / Analysis:
    https://libre-soc.org/3d_gpu/architecture/dynamic_simd/shape/

    naming is preserved to be compatible with Shape(): the (calculated *or*
    given) fixed_width is *explicitly* passed through as Shape.width
    in order to ensure downcasting works as expected.

    a mode flag records what behaviour is required for arithmetic operators.
    see wiki documentation: it's... complicated.
    """

    def __init__(self, scope, width=None,  # this is actually widths_at_elwid
                 signed=False,
                 fixed_width=None):  # fixed overall width
        # record the mode and scope
        self.scope = scope
        widths_at_elwid = width
        self.mode_flag = 0
        # when both of these are set it creates mode_flag=PRIORITY_BOTH
        # otherwise creates a priority of either FIXED width or ELWIDs
        if fixed_width is not None:
            self.mode_flag |= PRIORITY_FIXED
        if widths_at_elwid is not None:
            self.mode_flag |= PRIORITY_ELWID

        print("SimdShape width", width, "fixed_width", fixed_width)
        # this check is done inside layout but do it again here anyway
        assert fixed_width != None or widths_at_elwid != None, \
            "both width (widths_at_elwid) and fixed_width cannot be None"
        (pp, bitp, lpoints, bmask, fixed_width, lane_shapes, part_wid) = \
            layout(scope.elwid,
                   scope.vec_el_counts,
                   widths_at_elwid,
                   fixed_width)
        self.partpoints = pp
        self.bitp = bitp        # binary values for partpoints at each elwidth
        self.lpoints = lpoints  # layout ranges
        self.blankmask = bmask  # blanking mask (partitions always padding)
        self.partwid = part_wid  # smallest alignment start point for elements
        self.lane_shapes = lane_shapes

        # pass through the calculated width to Shape() so that when/if
        # objects using this Shape are downcast, they know exactly how to
        # get *all* bits and need know absolutely nothing about SIMD at all
        Shape.__init__(self, fixed_width, signed)

    def __mul__(self, other):
        if isinstance(other, int):
            # for integer multiply, by a nice coincidence it does not
            # matter if the LHS is PRIORITY_FIXED or PRIORITY_ELWID.
            # however the priority has to be preserved.
            fixed_width = None
            lane_shapes = None

            # first, check if fixed_width is needed (if originally,
            # self was constructed with a fixed_width=None we must
            # *return* another SimdShape with a fixed_width=None)
            if self.mode_flag & PRIORITY_FIXED:
                fixed_width = self.width * other

            # likewise for lane elwidths: if, originally, self was constructed
            # with [widths_at_elwidth==lane_shapes==]width not None,
            # the return result also has to set up explicit lane_shapes
            if self.mode_flag & PRIORITY_ELWID:
                lane_shapes = {k: v * other for k, v in self.lane_shapes}

            # wheww, got everything.
            return SimdShape(self.scope,              # same scope
                             width=lane_shapes,       # widths_at_elwid
                             signed=self.signed,      # same sign? hmmm XXX
                             fixed_width=fixed_width) # overall width
        else:
            raise NotImplementedError(
                f"Multiplying a SimdShape by {type(other)} isn't implemented")

            # TODO (and go over examples, sigh).  this is deliberately *after*
            # the raise NotImplementedError because it needs review.

            # also probably TODO: potentially the other argument could be
            # a Shape() not a SimdShape().  sigh.

            # for SimdShape-to-SimdShape multiply, the rules are slightly
            # different: both sides have to be PRIORITY_FIXED for a
            # PRIORITY_FIXED result to be returned.  if either (or both)
            # of the LHS and RHS were given elwidths (lane_shapes != None)
            # then tough luck: the return result is still PRIORITY_ELWID.
            # TODO: review that.  it *might* be the case (again, due to
            # a coincidence of multiply, that when PRIORITY_BOTH is set
            # it is possible to return a PRIORITY_BOTH result. but..
            # it is unlikely)

            fixed_width = None
            lane_shapes = None

            # first, check if this is fixed_width mode.  this is *only*
            # possible if *both* LHS *and* RHS are PRIORITY_FIXED.
            if (self.mode_flag == PRIORITY_FIXED and
                other.mode_flag == PRIORITY_FIXED):
                fixed_width = self.width * other.width
            else:
                # (XXX assume other is SimdShape) - when PRIORITY_ELWID
                # the result *has* to be a PRIORITY_ELWID (FIXED is *IGNORED*)
                # use *either* the computed *or* the given lane_shapes
                lane_shapes = {k: v * other.lane_shapes[k] \
                                  for k, v in self.lane_shapes}

            # wheww, got everything.
            return SimdShape(self.scope,              # same scope
                             width=lane_shapes,       # widths_at_elwid
                             signed=self.signed,      # same sign? hmmm XXX
                             fixed_width=fixed_width) # overall width


    def __rmul__(self, other):
        return self.__mul__(other)

    def __add__(self, other):
        if isinstance(other, int):
            lane_shapes = {k: v + other for k, v in self.lane_shapes}
            return SimdShape(self.scope, lane_shapes, signed=self.signed)
        elif isinstance(other, SimdShape):
            assert other.scope is self.scope, "scope mismatch"
            o = other.lane_shapes
            lane_shapes = {k: v + o[k] for k, v in self.lane_shapes}
            # XXX not correct, we need a width-hint, not an overwrite
            # lane_shapes argument...
            return SimdShape(self.scope, lane_shapes, signed=self.signed,
                             fixed_width=self.width + other.width)
        else:
            raise NotImplementedError(
                f"Adding a SimdShape to {type(other)} isn't implemented")

    def __radd__(self, other):
        return self.__add__(other)


class SimdSignal(UserValue):
    # XXX ################################################### XXX
    # XXX Keep these functions in the same order as ast.Value XXX
    # XXX ################################################### XXX
    def __init__(self, mask, shape=None, *args,
                 src_loc_at=0, fixed_width=None, **kwargs):
        super().__init__(src_loc_at=src_loc_at)
        print("SimdSignal shape", shape)
        # create partition points
        if isinstance(mask, SimdScope):  # mask parameter is a SimdScope
            self.scope = mask
            self.ptype = ElwidPartType(self)
            # adapt shape to a SimdShape
            if not isinstance(shape, SimdShape):
                shape = SimdShape(self.scope, shape, fixed_width=fixed_width)
            self._shape = shape
            self.sig = Signal(shape, *args, **kwargs)
            # get partpoints from SimdShape
            self.partpoints = shape.partpoints
        else:
            self.sig = Signal(shape, *args, **kwargs)
            width = len(self.sig)  # get signal width
            if isinstance(mask, PartitionPoints):
                self.partpoints = mask
            else:
                self.partpoints = make_partition2(mask, width)
            self.ptype = PartType(self)

    def set_module(self, m):
        self.m = m

    def get_modname(self, category):
        modnames[category] += 1
        return "%s_%d" % (category, modnames[category])

    @staticmethod
    def like(other, *args, **kwargs):
        """Builds a new SimdSignal with the same PartitionPoints and
        Signal properties as the other"""
        result = SimdSignal(PartitionPoints(other.partpoints))
        result.sig = Signal.like(other.sig, *args, **kwargs)
        result.m = other.m
        return result

    def lower(self):
        return self.sig

    # nmigen-redirected constructs (Mux, Cat, Switch, Assign)

    # TODO, http://bugs.libre-riscv.org/show_bug.cgi?id=716
    # def __Part__(self, offset, width, stride=1, *, src_loc_at=0):
        raise NotImplementedError("TODO: implement as "
                                  "(self>>(offset*stride)[:width]")
    # TODO, http://bugs.libre-riscv.org/show_bug.cgi?id=716

    def __Slice__(self, start, stop, *, src_loc_at=0):
        # NO.  Swizzled shall NOT be deployed, it violates
        # Project Development Practices
        raise NotImplementedError("TODO: need PartitionedSlice")

    def __Repl__(self, count, *, src_loc_at=0):
        return PRepl(self.m, self, count, self.ptype)

    def __Cat__(self, *args, src_loc_at=0):
        print("partsig cat", self, args)
        # TODO: need SwizzledSimdValue-aware Cat
        args = [self] + list(args)
        for sig in args:
            assert isinstance(sig, SimdSignal), \
                "All SimdSignal.__Cat__ arguments must be " \
                "a SimdSignal. %s is not." % repr(sig)
        return PCat(self.m, args, self.ptype)

    def __Mux__(self, val1, val2):
        # print ("partsig mux", self, val1, val2)
        assert len(val1) == len(val2), \
            "SimdSignal width sources must be the same " \
            "val1 == %d, val2 == %d" % (len(val1), len(val2))
        return PMux(self.m, self.partpoints, self, val1, val2, self.ptype)

    def __Assign__(self, val, *, src_loc_at=0):
        print("partsig assign", self, val)
        # this is a truly awful hack, outlined here:
        # https://bugs.libre-soc.org/show_bug.cgi?id=731#c13
        # during the period between constructing Simd-aware sub-modules
        # and the elaborate() being called on them there is a window of
        # opportunity to indicate which of those submodules is LHS and
        # which is RHS. manic laughter is permitted.  *gibber*.
        if hasattr(self, "_hack_submodule"):
            self._hack_submodule.set_lhs_mode(True)
        if hasattr(val, "_hack_submodule"):
            val._hack_submodule.set_lhs_mode(False)
        return PAssign(self.m, self, val, self.ptype)

    # TODO, http://bugs.libre-riscv.org/show_bug.cgi?id=458
    # def __Switch__(self, cases, *, src_loc=None, src_loc_at=0,
    #                               case_src_locs={}):

    # no override needed, Value.__bool__ sufficient
    # def __bool__(self):

    # unary ops that do not require partitioning

    def __invert__(self):
        result = SimdSignal.like(self)
        self.m.d.comb += result.sig.eq(~self.sig)
        return result

    # unary ops that require partitioning

    def __neg__(self):
        z = Const(0, len(self.sig))
        result, _ = self.sub_op(z, self)
        return result

    # binary ops that need partitioning

    def add_op(self, op1, op2, carry):
        op1 = getsig(op1)
        op2 = getsig(op2)
        pa = PartitionedAdder(len(op1), self.partpoints)
        setattr(self.m.submodules, self.get_modname('add'), pa)
        comb = self.m.d.comb
        comb += pa.a.eq(op1)
        comb += pa.b.eq(op2)
        comb += pa.carry_in.eq(carry)
        result = SimdSignal.like(self)
        comb += result.sig.eq(pa.output)
        return result, pa.carry_out

    def sub_op(self, op1, op2, carry=~0):
        op1 = getsig(op1)
        op2 = getsig(op2)
        pa = PartitionedAdder(len(op1), self.partpoints)
        setattr(self.m.submodules, self.get_modname('add'), pa)
        comb = self.m.d.comb
        comb += pa.a.eq(op1)
        comb += pa.b.eq(~op2)
        comb += pa.carry_in.eq(carry)
        result = SimdSignal.like(self)
        comb += result.sig.eq(pa.output)
        return result, pa.carry_out

    def __add__(self, other):
        result, _ = self.add_op(self, other, carry=0)
        return result

    def __radd__(self, other):
        #   https://bugs.libre-soc.org/show_bug.cgi?id=718
        result, _ = self.add_op(other, self)
        return result

    def __sub__(self, other):
        result, _ = self.sub_op(self, other)
        return result

    def __rsub__(self, other):
        #   https://bugs.libre-soc.org/show_bug.cgi?id=718
        result, _ = self.sub_op(other, self)
        return result

    def __mul__(self, other):
        raise NotImplementedError  # too complicated at the moment
        return Operator("*", [self, other])

    def __rmul__(self, other):
        raise NotImplementedError  # too complicated at the moment
        return Operator("*", [other, self])

    # not needed: same as Value.__check_divisor
    # def __check_divisor(self):

    def __mod__(self, other):
        raise NotImplementedError
        other = Value.cast(other)
        other.__check_divisor()
        return Operator("%", [self, other])

    def __rmod__(self, other):
        raise NotImplementedError
        self.__check_divisor()
        return Operator("%", [other, self])

    def __floordiv__(self, other):
        raise NotImplementedError
        other = Value.cast(other)
        other.__check_divisor()
        return Operator("//", [self, other])

    def __rfloordiv__(self, other):
        raise NotImplementedError
        self.__check_divisor()
        return Operator("//", [other, self])

    # not needed: same as Value.__check_shamt
    # def __check_shamt(self):

    # TODO: detect if the 2nd operand is a Const, a Signal or a
    # SimdSignal.  if it's a Const or a Signal, a global shift
    # can occur.  if it's a SimdSignal, that's much more interesting.
    def ls_op(self, op1, op2, carry, shr_flag=0):
        op1 = getsig(op1)
        if isinstance(op2, Const) or isinstance(op2, Signal):
            scalar = True
            pa = PartitionedScalarShift(len(op1), self.partpoints)
        else:
            scalar = False
            op2 = getsig(op2)
            pa = PartitionedDynamicShift(len(op1), self.partpoints)
        # else:
        #   TODO: case where the *shifter* is a SimdSignal but
        #   the thing *being* Shifted is a scalar (Signal, expression)
        #   https://bugs.libre-soc.org/show_bug.cgi?id=718
        setattr(self.m.submodules, self.get_modname('ls'), pa)
        comb = self.m.d.comb
        if scalar:
            comb += pa.data.eq(op1)
            comb += pa.shifter.eq(op2)
            comb += pa.shift_right.eq(shr_flag)
        else:
            comb += pa.a.eq(op1)
            comb += pa.b.eq(op2)
            comb += pa.shift_right.eq(shr_flag)
        # XXX TODO: carry-in, carry-out (for arithmetic shift)
        #comb += pa.carry_in.eq(carry)
        return (pa.output, 0)

    def __lshift__(self, other):
        z = Const(0, len(self.partpoints)+1)
        result, _ = self.ls_op(self, other, carry=z)  # TODO, carry
        return result

    def __rlshift__(self, other):
        #   https://bugs.libre-soc.org/show_bug.cgi?id=718
        raise NotImplementedError
        return Operator("<<", [other, self])

    def __rshift__(self, other):
        z = Const(0, len(self.partpoints)+1)
        result, _ = self.ls_op(self, other, carry=z, shr_flag=1)  # TODO, carry
        return result

    def __rrshift__(self, other):
        #   https://bugs.libre-soc.org/show_bug.cgi?id=718
        raise NotImplementedError
        return Operator(">>", [other, self])

    # binary ops that don't require partitioning

    def __and__(self, other):
        return applyop(self, other, and_)

    def __rand__(self, other):
        return applyop(other, self, and_)

    def __or__(self, other):
        return applyop(self, other, or_)

    def __ror__(self, other):
        return applyop(other, self, or_)

    def __xor__(self, other):
        return applyop(self, other, xor)

    def __rxor__(self, other):
        return applyop(other, self, xor)

    # binary comparison ops that need partitioning

    def _compare(self, width, op1, op2, opname, optype):
        # print (opname, op1, op2)
        pa = PartitionedEqGtGe(width, self.partpoints)
        setattr(self.m.submodules, self.get_modname(opname), pa)
        comb = self.m.d.comb
        comb += pa.opcode.eq(optype)  # set opcode
        if isinstance(op1, SimdSignal):
            comb += pa.a.eq(op1.sig)
        else:
            comb += pa.a.eq(op1)
        if isinstance(op2, SimdSignal):
            comb += pa.b.eq(op2.sig)
        else:
            comb += pa.b.eq(op2)
        return pa.output

    def __eq__(self, other):
        width = len(self.sig)
        return self._compare(width, self, other, "eq", PartitionedEqGtGe.EQ)

    def __ne__(self, other):
        width = len(self.sig)
        eq = self._compare(width, self, other, "eq", PartitionedEqGtGe.EQ)
        ne = Signal(eq.width)
        self.m.d.comb += ne.eq(~eq)
        return ne

    def __lt__(self, other):
        width = len(self.sig)
        # swap operands, use gt to do lt
        return self._compare(width, other, self, "gt", PartitionedEqGtGe.GT)

    def __le__(self, other):
        width = len(self.sig)
        # swap operands, use ge to do le
        return self._compare(width, other, self, "ge", PartitionedEqGtGe.GE)

    def __gt__(self, other):
        width = len(self.sig)
        return self._compare(width, self, other, "gt", PartitionedEqGtGe.GT)

    def __ge__(self, other):
        width = len(self.sig)
        return self._compare(width, self, other, "ge", PartitionedEqGtGe.GE)

    # no override needed: Value.__abs__ is general enough it does the job
    # def __abs__(self):

    def __len__(self):
        return len(self.sig)

    # TODO, http://bugs.libre-riscv.org/show_bug.cgi?id=716
    # def __getitem__(self, key):

    def __new_sign(self, signed):
        # XXX NO - SimdShape not Shape
        print("XXX requires SimdShape not Shape")
        shape = Shape(len(self), signed=signed)
        result = SimdSignal.like(self, shape=shape)
        self.m.d.comb += result.sig.eq(self.sig)
        return result

    # http://bugs.libre-riscv.org/show_bug.cgi?id=719
    def as_unsigned(self):
        return self.__new_sign(False)

    def as_signed(self):
        return self.__new_sign(True)

    # useful operators

    def bool(self):
        """Conversion to boolean.

        Returns
        -------
        Value, out
            ``1`` if any bits are set, ``0`` otherwise.
        """
        width = len(self.sig)
        pa = PartitionedBool(width, self.partpoints)
        setattr(self.m.submodules, self.get_modname("bool"), pa)
        self.m.d.comb += pa.a.eq(self.sig)
        return pa.output

    def any(self):
        """Check if any bits are ``1``.

        Returns
        -------
        Value, out
            ``1`` if any bits are set, ``0`` otherwise.
        """
        return self != Const(0)  # leverage the __ne__ operator here
        return Operator("r|", [self])

    def all(self):
        """Check if all bits are ``1``.

        Returns
        -------
        Value, out
            ``1`` if all bits are set, ``0`` otherwise.
        """
        # something wrong with PartitionedAll, but self == Const(-1)"
        # XXX https://bugs.libre-soc.org/show_bug.cgi?id=176#c17
        #width = len(self.sig)
        #pa = PartitionedAll(width, self.partpoints)
        #setattr(self.m.submodules, self.get_modname("all"), pa)
        #self.m.d.comb += pa.a.eq(self.sig)
        # return pa.output
        return self == Const(-1)  # leverage the __eq__ operator here

    def xor(self):
        """Compute pairwise exclusive-or of every bit.

        Returns
        -------
        Value, out
            ``1`` if an odd number of bits are set, ``0`` if an
                  even number of bits are set.
        """
        width = len(self.sig)
        pa = PartitionedXOR(width, self.partpoints)
        setattr(self.m.submodules, self.get_modname("xor"), pa)
        self.m.d.comb += pa.a.eq(self.sig)
        return pa.output

    # not needed: Value.implies does the job
    # def implies(premise, conclusion):

    # TODO. contains a Value.cast which means an override is needed (on both)
    # def bit_select(self, offset, width):
    # def word_select(self, offset, width):

    # not needed: Value.matches, amazingly, should do the job
    # def matches(self, *patterns):

    # TODO, http://bugs.libre-riscv.org/show_bug.cgi?id=713
    def shape(self):
        return self.sig.shape()
