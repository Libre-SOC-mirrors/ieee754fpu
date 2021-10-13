# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information

from enum import Enum
from typing import Mapping
import operator
import math
from types import MappingProxyType
from contextlib import contextmanager

from nmigen.hdl.ast import Signal


class ElWid(Enum):
    def __repr__(self):
        return super().__str__()


class FpElWid(ElWid):
    F64 = 0
    F32 = 1
    F16 = 2
    BF16 = 3


class IntElWid(ElWid):
    I64 = 0
    I32 = 1
    I16 = 2
    I8 = 3


class SimdMap:
    """A map from ElWid values to Python values.
    SimdMap instances are immutable."""

    ALL_ELWIDTHS = (*FpElWid, *IntElWid)
    __slots__ = ("__map",)

    @classmethod
    def extract_value(cls, elwid, values, default=None):
        """get the value for elwid.
        if `values` is a `SimdMap` or a `Mapping`, then return the
        corresponding value for `elwid`, recursing until finding a non-map.
        if `values` ever ends up not existing (in the case of a map) or being
        `None`, return `default`.

        Examples:
        SimdMap.extract_value(IntElWid.I8, 5) == 5
        SimdMap.extract_value(IntElWid.I8, None) == None
        SimdMap.extract_value(IntElWid.I8, None, 3) == 3
        SimdMap.extract_value(IntElWid.I8, {}) == None
        SimdMap.extract_value(IntElWid.I8, {IntElWid.I8: 5}) == 5
        SimdMap.extract_value(IntElWid.I8, {
            IntElWid.I8: {IntElWid.I8: 5},
        }) == 5
        SimdMap.extract_value(IntElWid.I8, {
            IntElWid.I8: SimdMap({IntElWid.I8: 5}),
        }) == 5
        """
        assert elwid in cls.ALL_ELWIDTHS
        step = 0
        while values is not None:
            # specifically use base class to catch all SimdMap instances
            if isinstance(values, SimdMap):
                values = values.__map.get(elwid)
            elif isinstance(values, Mapping):
                values = values.get(elwid)
            else:
                return values
            step += 1
            # use object.__repr__ since repr() would probably recurse forever
            assert step < 10000, (f"can't resolve infinitely recursive "
                                  f"value {object.__repr__(values)}")
        return default

    def __init__(self, values=None):
        """construct a SimdMap"""
        mapping = {}
        for elwid in self.ALL_ELWIDTHS:
            v = self.extract_value(elwid, values)
            if v is not None:
                mapping[elwid] = v
        self.__map = MappingProxyType(mapping)

    @property
    def mapping(self):
        """the values as a read-only Mapping[ElWid, Any]"""
        return self.__map

    def values(self):
        return self.__map.values()

    def keys(self):
        return self.__map.keys()

    def items(self):
        return self.__map.items()

    @classmethod
    def map_with_elwid(cls, f, *args):
        """get the SimdMap of the results of calling
        `f(elwid, value1, value2, value3, ...)` where
        `value1`, `value2`, `value3`, ... are the results of calling
        `cls.extract_value` on each `args`.

        This is similar to Python's built-in `map` function.

        Examples:
        SimdMap.map_with_elwid(lambda elwid, a: a + 1, {IntElWid.I32: 5}) ==
            SimdMap({IntElWid.I32: 6})
        SimdMap.map_with_elwid(lambda elwid, a: a + 1, 3) ==
            SimdMap({IntElWid.I8: 4, IntElWid.I16: 4, ...})
        SimdMap.map_with_elwid(lambda elwid, a, b: a + b,
            3, {IntElWid.I8: 4},
        ) == SimdMap({IntElWid.I8: 7})
        SimdMap.map_with_elwid(lambda elwid: elwid.name) ==
            SimdMap({IntElWid.I8: "I8", IntElWid.I16: "I16"})
        """
        retval = {}
        for elwid in cls.ALL_ELWIDTHS:
            extracted_args = [cls.extract_value(elwid, arg) for arg in args]
            if None not in extracted_args:
                retval[elwid] = f(elwid, *extracted_args)
        return cls(retval)

    @classmethod
    def map(cls, f, *args):
        """get the SimdMap of the results of calling
        `f(value1, value2, value3, ...)` where
        `value1`, `value2`, `value3`, ... are the results of calling
        `cls.extract_value` on each `args`.

        This is similar to Python's built-in `map` function.

        Examples:
        SimdMap.map(lambda a: a + 1, {IntElWid.I32: 5}) ==
            SimdMap({IntElWid.I32: 6})
        SimdMap.map(lambda a: a + 1, 3) ==
            SimdMap({IntElWid.I8: 4, IntElWid.I16: 4, ...})
        SimdMap.map(lambda a, b: a + b,
            3, {IntElWid.I8: 4},
        ) == SimdMap({IntElWid.I8: 7})
        """
        return cls.map_with_elwid(lambda elwid, *args2: f(*args2), *args)

    def get(self, elwid, default=None, *, raise_key_error=False):
        if raise_key_error:
            retval = self.extract_value(elwid, self)
            if retval is None:
                raise KeyError()
            return retval
        return self.extract_value(elwid, self, default)

    def __iter__(self):
        """return an iterator of (elwid, value) pairs"""
        return self.__map.items()

    def __add__(self, other):
        return self.map(operator.add, self, other)

    def __radd__(self, other):
        return self.map(operator.add, other, self)

    def __sub__(self, other):
        return self.map(operator.sub, self, other)

    def __rsub__(self, other):
        return self.map(operator.sub, other, self)

    def __mul__(self, other):
        return self.map(operator.mul, self, other)

    def __rmul__(self, other):
        return self.map(operator.mul, other, self)

    def __floordiv__(self, other):
        return self.map(operator.floordiv, self, other)

    def __rfloordiv__(self, other):
        return self.map(operator.floordiv, other, self)

    def __truediv__(self, other):
        return self.map(operator.truediv, self, other)

    def __rtruediv__(self, other):
        return self.map(operator.truediv, other, self)

    def __mod__(self, other):
        return self.map(operator.mod, self, other)

    def __rmod__(self, other):
        return self.map(operator.mod, other, self)

    def __abs__(self):
        return self.map(abs, self)

    def __and__(self, other):
        return self.map(operator.and_, self, other)

    def __rand__(self, other):
        return self.map(operator.and_, other, self)

    def __divmod__(self, other):
        return self.map(divmod, self, other)

    def __ceil__(self):
        return self.map(math.ceil, self)

    def __float__(self):
        return self.map(float, self)

    def __floor__(self):
        return self.map(math.floor, self)

    def __eq__(self, other):
        if isinstance(other, SimdMap):
            return self.mapping == other.mapping
        return NotImplemented

    def __hash__(self):
        return hash(tuple(self.mapping.get(i) for i in self.ALL_ELWIDTHS))

    def __repr__(self):
        return f"{self.__class__.__name__}({dict(self.mapping)})"

    def __invert__(self):
        return self.map(operator.invert, self)

    def __lshift__(self, other):
        return self.map(operator.lshift, self, other)

    def __rlshift__(self, other):
        return self.map(operator.lshift, other, self)

    def __rshift__(self, other):
        return self.map(operator.rshift, self, other)

    def __rrshift__(self, other):
        return self.map(operator.rshift, other, self)

    def __neg__(self):
        return self.map(operator.neg, self)

    def __pos__(self):
        return self.map(operator.pos, self)

    def __or__(self, other):
        return self.map(operator.or_, self, other)

    def __ror__(self, other):
        return self.map(operator.or_, other, self)

    def __xor__(self, other):
        return self.map(operator.xor, self, other)

    def __rxor__(self, other):
        return self.map(operator.xor, other, self)

    def missing_elwidths(self, *, all_elwidths=None):
        """an iterator of the elwidths where self doesn't have a corresponding
        value"""
        if all_elwidths is None:
            all_elwidths = self.ALL_ELWIDTHS
        for elwid in all_elwidths:
            if elwid not in self.keys():
                yield elwid


def _check_for_missing_elwidths(name, all_elwidths=None):
    missing = list(globals()[name].missing_elwidths(all_elwidths=all_elwidths))
    assert missing == [], f"{name} is missing entries for {missing}"


XLEN = SimdMap({
    IntElWid.I64: 64,
    IntElWid.I32: 32,
    IntElWid.I16: 16,
    IntElWid.I8: 8,
    FpElWid.F64: 64,
    FpElWid.F32: 32,
    FpElWid.F16: 16,
    FpElWid.BF16: 16,
})

DEFAULT_FP_PART_COUNTS = SimdMap({
    FpElWid.F64: 4,
    FpElWid.F32: 2,
    FpElWid.F16: 1,
    FpElWid.BF16: 1,
})

DEFAULT_INT_PART_COUNTS = SimdMap({
    IntElWid.I64: 8,
    IntElWid.I32: 4,
    IntElWid.I16: 2,
    IntElWid.I8: 1,
})

_check_for_missing_elwidths("XLEN")
_check_for_missing_elwidths("DEFAULT_FP_PART_COUNTS", FpElWid)
_check_for_missing_elwidths("DEFAULT_INT_PART_COUNTS", IntElWid)


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
