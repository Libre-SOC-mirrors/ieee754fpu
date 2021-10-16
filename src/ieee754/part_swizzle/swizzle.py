# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

from dataclasses import dataclass
from functools import reduce
from typing import Dict, FrozenSet, List, Set, Tuple
from nmigen.hdl.ast import Cat, Const, Shape, Signal, SignalKey, Value, ValueKey
from nmigen.hdl.dsl import Module
from nmigen.hdl.ir import Elaboratable
from ieee754.part.partsig import SimdSignal


@dataclass(frozen=True, unsafe_hash=True)
class Bit:
    def get_value(self):
        """get the value of this bit as a nmigen `Value`"""
        raise NotImplementedError("called abstract method")


@dataclass(frozen=True, unsafe_hash=True)
class ValueBit(Bit):
    src: ValueKey
    bit_index: int

    def __init__(self, src, bit_index):
        if not isinstance(src, ValueKey):
            src = ValueKey(src)
        assert isinstance(bit_index, int)
        assert bit_index in range(len(src.value))
        object.__setattr__(self, "src", src)
        object.__setattr__(self, "bit_index", bit_index)

    def get_value(self):
        """get the value of this bit as a nmigen `Value`"""
        return self.src.value[self.bit_index]

    def get_assign_target_sig(self):
        """get the Signal that assigning to this bit would assign to"""
        if isinstance(self.src.value, Signal):
            return self.src.value
        raise TypeError("not a valid assignment target")

    def assign(self, value, signals_map):
        sig = self.get_assign_target_sig()
        return signals_map[SignalKey(sig)][self.bit_index].eq(value)


@dataclass(frozen=True, unsafe_hash=True)
class ConstBit(Bit):
    bit: bool

    def get_value(self):
        return Const(self.bit, 1)


@dataclass(frozen=True)
class Swizzle:
    bits: List[Bit]

    def __init__(self, bits=()):
        bits = list(bits)
        for bit in bits:
            assert isinstance(bit, Bit)
        object.__setattr__(self, "bits", bits)

    @staticmethod
    def from_const(value, width):
        return Swizzle(ConstBit((value & (1 << i)) != 0) for i in range(width))

    @staticmethod
    def from_value(value):
        value = Value.cast(value)
        if isinstance(value, Const):
            return Swizzle.from_const(value.value, len(value))
        return Swizzle(ValueBit(value, i) for i in range(len(value)))

    def get_value(self):
        return Cat(*(bit.get_value() for bit in self.bits))

    def get_sign(self):
        return self.bits[-1] if len(self.bits) != 0 else ConstBit(False)

    def convert_u_to(self, shape):
        shape = Shape.cast(shape)
        additional = shape.width - len(self.bits)
        self.bits[shape.width:] = [ConstBit(False)] * additional

    def convert_s_to(self, shape):
        shape = Shape.cast(shape)
        additional = shape.width - len(self.bits)
        self.bits[shape.width:] = [self.get_sign()] * additional

    def __getitem__(self, key):
        if isinstance(key, int):
            return Swizzle([self.bits[key]])
        assert isinstance(key, slice)
        return Swizzle(self.bits[key])

    def __add__(self, other):
        if isinstance(other, Swizzle):
            return Swizzle(self.bits + other.bits)
        return NotImplemented

    def __radd__(self, other):
        if isinstance(other, Swizzle):
            return Swizzle(other.bits + self.bits)
        return NotImplemented

    def __iadd__(self, other):
        assert isinstance(other, Swizzle)
        self.bits += other.bits
        return self

    def get_assign_target_sigs(self):
        for b in self.bits:
            assert isinstance(b, ValueBit)
            yield b.get_assign_target_sig()


@dataclass(frozen=True)
class SwizzleKey:
    """should be elwid or something similar.
    importantly, all SimdSignals that are used together must have equal
    SwizzleKeys."""
    value: ValueKey
    possible_values: FrozenSet[int]

    @staticmethod
    def from_simd_signal(simd_signal):
        if isinstance(simd_signal, SwizzledSimdValue):
            return simd_signal.swizzle_key

        # can't just be PartitionPoints, since those vary between
        # SimdSignals with different padding
        raise NotImplementedError("TODO: implement extracting a SwizzleKey "
                                  "from a SimdSignal")

    def __init__(self, value, possible_values):
        object.__setattr__(self, "value", ValueKey(value))
        pvalues = []
        shape = self.value.value.shape()
        for value in possible_values:
            if isinstance(value, int):
                assert value == Const.normalize(value, shape)
            else:
                value = Value.cast(value)
                assert isinstance(value, Const)
                value = value.value
            pvalues.append(value)
        assert len(pvalues) != 0, "SwizzleKey can't have zero possible values"
        object.__setattr__(self, "possible_values", frozenset(pvalues))


class ResolveSwizzle(Elaboratable):
    def __init__(self, swizzled_simd_value):
        assert isinstance(swizzled_simd_value, SwizzledSimdValue)
        self.swizzled_simd_value = swizzled_simd_value

    def elaborate(self, platform):
        m = Module()
        swizzle_key = self.swizzled_simd_value.swizzle_key
        swizzles = self.swizzled_simd_value.swizzles
        output = self.swizzled_simd_value.sig
        with m.Switch(swizzle_key.value):
            for k in sorted(swizzle_key.possible_values):
                swizzle = swizzles[k]
                with m.Case(k):
                    m.d.comb += output.eq(swizzle.get_value())
        return m


class AssignSwizzle(Elaboratable):
    def __init__(self, swizzled_simd_value, src_sig):
        assert isinstance(swizzled_simd_value, SwizzledSimdValue)
        self.swizzled_simd_value = swizzled_simd_value
        assert isinstance(src_sig, Signal)
        self.src_sig = src_sig
        self.converted_src_sig = Signal.like(swizzled_simd_value._sig_internal)
        targets = swizzled_simd_value._get_assign_target_sigs()
        targets = sorted({SignalKey(s) for s in targets})

        def make_sig(i, s):
            return Signal.like(s.signal, name=f"outputs_{i}")
        self.outputs = {s: make_sig(i, s) for i, s in enumerate(targets)}

    def elaborate(self, platform):
        m = Module()
        swizzle_key = self.swizzled_simd_value.swizzle_key
        swizzles = self.swizzled_simd_value.swizzles
        for k, v in self.outputs.items():
            m.d.comb += v.eq(k.signal)
        m.d.comb += self.converted_src_sig.eq(self.src_sig)
        with m.Switch(swizzle_key.value):
            for k in sorted(swizzle_key.possible_values):
                swizzle = swizzles[k]
                with m.Case(k):
                    for index, bit in enumerate(swizzle.bits):
                        rhs = self.converted_src_sig[index]
                        assert isinstance(bit, ValueBit)
                        m.d.comb += bit.assign(rhs, self.outputs)
        return m


class SwizzledSimdValue(SimdSignal):
    """the result of any number of Cat and Slice operations on
    Signals/SimdSignals. This is specifically intended to support assignment
    to Cat and Slice, but is also useful for reducing the number of muxes
    chained together down to a single layer of muxes."""
    __next_id = 0

    @staticmethod
    def from_simd_signal(simd_signal):
        if isinstance(simd_signal, SwizzledSimdValue):
            return simd_signal
        assert isinstance(simd_signal, SimdSignal)
        swizzle_key = SwizzleKey.from_simd_signal(simd_signal)
        swizzle = Swizzle.from_value(simd_signal.sig)
        retval = SwizzledSimdValue(swizzle_key, swizzle)
        retval.set_module(simd_signal.m)
        return retval

    @staticmethod
    def __do_splat(swizzle_key, value):
        """splat a non-simd value, returning a SimdSignal"""
        raise NotImplementedError("TODO: need splat implementation")

    def __do_convert_rhs_to_simd_signal_like_self(self, rhs):
        """convert a value to be a SimdSignal of the same layout/shape as self,
        returning a SimdSignal."""
        raise NotImplementedError("TODO: need conversion implementation")

    @staticmethod
    def from_value(swizzle_key, value):
        if not isinstance(value, SimdSignal):
            value = SwizzledSimdValue.__do_splat(swizzle_key, value)
        retval = SwizzledSimdValue.from_simd_signal(value)
        assert swizzle_key == retval.swizzle_key
        return retval

    @classmethod
    def __make_name(cls):
        id_ = cls.__next_id
        cls.__next_id = id_ + 1
        return f"swizzle_{id_}"

    def __init__(self, swizzle_key, swizzles):
        assert isinstance(swizzle_key, SwizzleKey)
        self.swizzle_key = swizzle_key
        possible_keys = swizzle_key.possible_values
        if isinstance(swizzles, Swizzle):
            self.swizzles = {k: swizzles for k in possible_keys}
        else:
            self.swizzles = {}
            for k in possible_keys:
                swizzle = swizzles[k]
                assert isinstance(swizzle, Swizzle)
                self.swizzles[k] = swizzle
        width = None
        for swizzle in self.swizzles.values():
            if width is None:
                width = len(swizzle.bits)
            assert width == len(swizzle.bits), \
                "inconsistent swizzle widths"
        assert width is not None
        self.__sig_need_setup = False  # ignore accesses during __init__
        super().__init__(swizzle_key.value, width, name="output")
        self.__sig_need_setup = True

    @property
    def sig(self):
        # override sig to handle lazily adding the ResolveSwizzle submodule
        if self.__sig_need_setup:
            self.__sig_need_setup = False
            submodule = ResolveSwizzle(self)
            setattr(self.m.submodules, self.__make_name(), submodule)
        return self._sig_internal

    @sig.setter
    def sig(self, value):
        assert isinstance(value, Signal)
        self._sig_internal = value

    def _get_assign_target_sigs(self):
        for swizzle in self.swizzles.values():
            yield from swizzle.get_assign_target_sigs()

    def __Assign__(self, val, *, src_loc_at=0):
        rhs = self.__do_convert_rhs_to_simd_signal_like_self(val)
        assert isinstance(rhs, SimdSignal)
        submodule = AssignSwizzle(self, rhs.sig)
        setattr(self.m.submodules, self.__make_name(), submodule)
        return [k.signal.eq(v) for k, v in submodule.outputs.items()]

    def __Cat__(self, *args, src_loc_at=0):
        raise NotImplementedError("TODO: implement")

    def __Slice__(self, start, stop, *, src_loc_at=0):
        raise NotImplementedError("TODO: implement")
