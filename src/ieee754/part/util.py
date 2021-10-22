# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information

from enum import Enum
from typing import Mapping
import operator
import math
from types import MappingProxyType


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

DEFAULT_FP_VEC_EL_COUNTS = SimdMap({
    FpElWid.F64: 1,
    FpElWid.F32: 2,
    FpElWid.F16: 4,
    FpElWid.BF16: 4,
})

DEFAULT_INT_VEC_EL_COUNTS = SimdMap({
    IntElWid.I64: 1,
    IntElWid.I32: 2,
    IntElWid.I16: 4,
    IntElWid.I8: 8,
})

_check_for_missing_elwidths("XLEN")
_check_for_missing_elwidths("DEFAULT_FP_VEC_EL_COUNTS", FpElWid)
_check_for_missing_elwidths("DEFAULT_INT_VEC_EL_COUNTS", IntElWid)
