"""IEEE754 Floating Point Library

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
Copyright (C) 2019,2022 Jacob Lifshay <programmerjake@gmail.com>

"""


from nmigen import (Signal, Cat, Const, Mux, Module, Elaboratable, Array,
                    Value, Shape, signed, unsigned)
from nmigen.utils import bits_for
from operator import or_
from functools import reduce

from nmutil.singlepipe import PrevControl, NextControl
from nmutil.pipeline import ObjectProxy
import unittest
import math
import enum

try:
    from nmigen.hdl.smtlib2 import RoundingModeEnum
    _HAVE_SMTLIB2 = True
except ImportError:
    _HAVE_SMTLIB2 = False

# value so FPRoundingMode.to_smtlib2 can detect when no default is supplied
_raise_err = object()


class FPRoundingMode(enum.Enum):
    # matches the FPSCR.RN field values, but includes some extra
    # values (>= 0b100) used in miscellaneous instructions.

    # naming matches smtlib2 names, doc strings are the OpenPower ISA
    # specification's names (v3.1 section 7.3.2.6 --
    # matches values in section 4.3.6).
    RNE = 0b00
    """Round to Nearest Even

    Rounds to the nearest representable floating-point number, ties are
    rounded to the number with the even mantissa. Treats +-Infinity as if
    it were a normalized floating-point number when deciding which number
    is closer when rounding. See IEEE754 spec. for details.
    """

    ROUND_NEAREST_TIES_TO_EVEN = RNE
    DEFAULT = RNE

    RTZ = 0b01
    """Round towards Zero

    If the result is exactly representable as a floating-point number, return
    that, otherwise return the nearest representable floating-point value
    with magnitude smaller than the exact answer.
    """

    ROUND_TOWARDS_ZERO = RTZ

    RTP = 0b10
    """Round towards +Infinity

    If the result is exactly representable as a floating-point number, return
    that, otherwise return the nearest representable floating-point value
    that is numerically greater than the exact answer. This can round up to
    +Infinity.
    """

    ROUND_TOWARDS_POSITIVE = RTP

    RTN = 0b11
    """Round towards -Infinity

    If the result is exactly representable as a floating-point number, return
    that, otherwise return the nearest representable floating-point value
    that is numerically less than the exact answer. This can round down to
    -Infinity.
    """

    ROUND_TOWARDS_NEGATIVE = RTN

    RNA = 0b100
    """Round to Nearest Away

    Rounds to the nearest representable floating-point number, ties are
    rounded to the number with the maximum magnitude. Treats +-Infinity as if
    it were a normalized floating-point number when deciding which number
    is closer when rounding. See IEEE754 spec. for details.
    """

    ROUND_NEAREST_TIES_TO_AWAY = RNA

    RTOP = 0b101
    """Round to Odd, unsigned zeros are Positive

    Not in smtlib2.

    If the result is exactly representable as a floating-point number, return
    that, otherwise return the nearest representable floating-point value
    that has an odd mantissa.

    If the result is zero but with otherwise undetermined sign
    (e.g. `1.0 - 1.0`), the sign is positive.

    This rounding mode is used for instructions with Round To Odd enabled,
    and `FPSCR.RN != RTN`.

    This is useful to avoid double-rounding errors when doing arithmetic in a
    larger type (e.g. f128) but where the answer should be a smaller type
    (e.g. f80).
    """

    ROUND_TO_ODD_UNSIGNED_ZEROS_ARE_POSITIVE = RTOP

    RTON = 0b110
    """Round to Odd, unsigned zeros are Negative

    Not in smtlib2.

    If the result is exactly representable as a floating-point number, return
    that, otherwise return the nearest representable floating-point value
    that has an odd mantissa.

    If the result is zero but with otherwise undetermined sign
    (e.g. `1.0 - 1.0`), the sign is negative.

    This rounding mode is used for instructions with Round To Odd enabled,
    and `FPSCR.RN == RTN`.

    This is useful to avoid double-rounding errors when doing arithmetic in a
    larger type (e.g. f128) but where the answer should be a smaller type
    (e.g. f80).
    """

    ROUND_TO_ODD_UNSIGNED_ZEROS_ARE_NEGATIVE = RTON

    @staticmethod
    def make_array(f):
        l = [None] * len(FPRoundingMode)
        for rm in FPRoundingMode:
            l[rm.value] = f(rm)
        return Array(l)

    def overflow_rounds_to_inf(self, sign):
        """returns true if an overflow should round to `inf`,
        false if it should round to `max_normal`
        """
        not_sign = ~sign if isinstance(sign, Value) else not sign
        if self is FPRoundingMode.RNE:
            return True
        elif self is FPRoundingMode.RTZ:
            return False
        elif self is FPRoundingMode.RTP:
            return not_sign
        elif self is FPRoundingMode.RTN:
            return sign
        elif self is FPRoundingMode.RNA:
            return True
        elif self is FPRoundingMode.RTOP:
            return False
        else:
            assert self is FPRoundingMode.RTON
            return False

    def underflow_rounds_to_zero(self, sign):
        """returns true if an underflow should round to `zero`,
        false if it should round to `min_denormal`
        """
        not_sign = ~sign if isinstance(sign, Value) else not sign
        if self is FPRoundingMode.RNE:
            return True
        elif self is FPRoundingMode.RTZ:
            return True
        elif self is FPRoundingMode.RTP:
            return sign
        elif self is FPRoundingMode.RTN:
            return not_sign
        elif self is FPRoundingMode.RNA:
            return True
        elif self is FPRoundingMode.RTOP:
            return False
        else:
            assert self is FPRoundingMode.RTON
            return False

    def zero_sign(self):
        """which sign an exact zero result should have when it isn't
        otherwise determined, e.g. for `1.0 - 1.0`.
        """
        if self is FPRoundingMode.RNE:
            return False
        elif self is FPRoundingMode.RTZ:
            return False
        elif self is FPRoundingMode.RTP:
            return False
        elif self is FPRoundingMode.RTN:
            return True
        elif self is FPRoundingMode.RNA:
            return False
        elif self is FPRoundingMode.RTOP:
            return False
        else:
            assert self is FPRoundingMode.RTON
            return True

    if _HAVE_SMTLIB2:
        def to_smtlib2(self, default=_raise_err):
            """return the corresponding smtlib2 rounding mode for `self`. If
            there is no corresponding smtlib2 rounding mode, then return
            `default` if specified, else raise `ValueError`.
            """
            if self is FPRoundingMode.RNE:
                return RoundingModeEnum.RNE
            elif self is FPRoundingMode.RTZ:
                return RoundingModeEnum.RTZ
            elif self is FPRoundingMode.RTP:
                return RoundingModeEnum.RTP
            elif self is FPRoundingMode.RTN:
                return RoundingModeEnum.RTN
            elif self is FPRoundingMode.RNA:
                return RoundingModeEnum.RNA
            else:
                assert self in (FPRoundingMode.RTOP, FPRoundingMode.RTON)
                if default is _raise_err:
                    raise ValueError(
                        "no corresponding smtlib2 rounding mode", self)
                return default




class FPFormat:
    """ Class describing binary floating-point formats based on IEEE 754.

    :attribute e_width: the number of bits in the exponent field.
    :attribute m_width: the number of bits stored in the mantissa
        field.
    :attribute has_int_bit: if the FP format has an explicit integer bit (like
        the x87 80-bit format). The bit is considered part of the mantissa.
    :attribute has_sign: if the FP format has a sign bit. (Some Vulkan
        Image/Buffer formats are FP numbers without a sign bit.)
    """

    def __init__(self,
                 e_width,
                 m_width,
                 has_int_bit=False,
                 has_sign=True):
        """ Create ``FPFormat`` instance. """
        self.e_width = e_width
        self.m_width = m_width
        self.has_int_bit = has_int_bit
        self.has_sign = has_sign

    def __eq__(self, other):
        """ Check for equality. """
        if not isinstance(other, FPFormat):
            return NotImplemented
        return (self.e_width == other.e_width
                and self.m_width == other.m_width
                and self.has_int_bit == other.has_int_bit
                and self.has_sign == other.has_sign)

    @staticmethod
    def standard(width):
        """ Get standard IEEE 754-2008 format.

        :param width: bit-width of requested format.
        :returns: the requested ``FPFormat`` instance.
        """
        if width == 16:
            return FPFormat(5, 10)
        if width == 32:
            return FPFormat(8, 23)
        if width == 64:
            return FPFormat(11, 52)
        if width == 128:
            return FPFormat(15, 112)
        if width > 128 and width % 32 == 0:
            if width > 1000000:  # arbitrary upper limit
                raise ValueError("width too big")
            e_width = round(4 * math.log2(width)) - 13
            return FPFormat(e_width, width - 1 - e_width)
        raise ValueError("width must be the bit-width of a valid IEEE"
                         " 754-2008 binary format")

    def __repr__(self):
        """ Get repr. """
        try:
            if self == self.standard(self.width):
                return f"FPFormat.standard({self.width})"
        except ValueError:
            pass
        retval = f"FPFormat({self.e_width}, {self.m_width}"
        if self.has_int_bit is not False:
            retval += f", {self.has_int_bit}"
        if self.has_sign is not True:
            retval += f", {self.has_sign}"
        return retval + ")"

    def get_sign_field(self, x):
        """ returns the sign bit of its input number, x
            (assumes FPFormat is set to signed - has_sign=True)
        """
        return x >> (self.e_width + self.m_width)

    def get_exponent_field(self, x):
        """ returns the raw exponent of its input number, x (no bias subtracted)
        """
        x = ((x >> self.m_width) & self.exponent_inf_nan)
        return x

    def get_exponent(self, x):
        """ returns the exponent of its input number, x
        """
        x = self.get_exponent_field(x)
        if isinstance(x, Value) and not x.shape().signed:
            # convert x to signed without changing its value,
            # since exponents can be negative
            x |= Const(0, signed(1))
        return x - self.exponent_bias

    def get_exponent_value(self, x):
        """ returns the exponent of its input number, x, adjusted for the
        mathematically correct subnormal exponent.
        """
        x = self.get_exponent_field(x)
        if isinstance(x, Value) and not x.shape().signed:
            # convert x to signed without changing its value,
            # since exponents can be negative
            x |= Const(0, signed(1))
        return x + (x == self.exponent_denormal_zero) - self.exponent_bias

    def get_mantissa_field(self, x):
        """ returns the mantissa of its input number, x
        """
        return x & self.mantissa_mask

    def get_mantissa_value(self, x):
        """ returns the mantissa of its input number, x, but with the
        implicit bit, if any, made explicit.
        """
        if self.has_int_bit:
            return self.get_mantissa_field(x)
        exponent_field = self.get_exponent_field(x)
        mantissa_field = self.get_mantissa_field(x)
        implicit_bit = exponent_field != self.exponent_denormal_zero
        return (implicit_bit << self.fraction_width) | mantissa_field

    def is_zero(self, x):
        """ returns true if x is +/- zero
        """
        return (self.get_exponent(x) == self.e_sub) & \
            (self.get_mantissa_field(x) == 0)

    def is_subnormal(self, x):
        """ returns true if x is subnormal (exp at minimum)
        """
        return (self.get_exponent(x) == self.e_sub) & \
            (self.get_mantissa_field(x) != 0)

    def is_inf(self, x):
        """ returns true if x is infinite
        """
        return (self.get_exponent(x) == self.e_max) & \
            (self.get_mantissa_field(x) == 0)

    def is_nan(self, x):
        """ returns true if x is a nan (quiet or signalling)
        """
        return (self.get_exponent(x) == self.e_max) & \
            (self.get_mantissa_field(x) != 0)

    def is_quiet_nan(self, x):
        """ returns true if x is a quiet nan
        """
        highbit = 1 << (self.m_width - 1)
        return (self.get_exponent(x) == self.e_max) & \
            (self.get_mantissa_field(x) != 0) & \
            (self.get_mantissa_field(x) & highbit != 0)

    def to_quiet_nan(self, x):
        """ converts `x` to a quiet NaN """
        highbit = 1 << (self.m_width - 1)
        return x | highbit | self.exponent_mask

    def quiet_nan(self, sign=0):
        """ return the default quiet NaN with sign `sign` """
        return self.to_quiet_nan(self.zero(sign))

    def zero(self, sign=0):
        """ return zero with sign `sign` """
        return (sign != 0) << (self.e_width + self.m_width)

    def inf(self, sign=0):
        """ return infinity with sign `sign` """
        return self.zero(sign) | self.exponent_mask

    def is_nan_signaling(self, x):
        """ returns true if x is a signalling nan
        """
        highbit = 1 << (self.m_width - 1)
        return (self.get_exponent(x) == self.e_max) & \
            (self.get_mantissa_field(x) != 0) & \
            (self.get_mantissa_field(x) & highbit) == 0

    @property
    def width(self):
        """ Get the total number of bits in the FP format. """
        return self.has_sign + self.e_width + self.m_width

    @property
    def mantissa_mask(self):
        """ Get a mantissa mask based on the mantissa width """
        return (1 << self.m_width) - 1

    @property
    def exponent_mask(self):
        """ Get an exponent mask """
        return self.exponent_inf_nan << self.m_width

    @property
    def exponent_inf_nan(self):
        """ Get the value of the exponent field designating infinity/NaN. """
        return (1 << self.e_width) - 1

    @property
    def e_max(self):
        """ get the maximum exponent (minus bias)
        """
        return self.exponent_inf_nan - self.exponent_bias

    @property
    def e_sub(self):
        return self.exponent_denormal_zero - self.exponent_bias
    @property
    def exponent_denormal_zero(self):
        """ Get the value of the exponent field designating denormal/zero. """
        return 0

    @property
    def exponent_min_normal(self):
        """ Get the minimum value of the exponent field for normal numbers. """
        return 1

    @property
    def exponent_max_normal(self):
        """ Get the maximum value of the exponent field for normal numbers. """
        return self.exponent_inf_nan - 1

    @property
    def exponent_bias(self):
        """ Get the exponent bias. """
        return (1 << (self.e_width - 1)) - 1

    @property
    def fraction_width(self):
        """ Get the number of mantissa bits that are fraction bits. """
        return self.m_width - self.has_int_bit


class TestFPFormat(unittest.TestCase):
    """ very quick test for FPFormat
    """

    def test_fpformat_fp64(self):
        f64 = FPFormat.standard(64)
        from sfpy import Float64
        x = Float64(1.0).bits
        print (hex(x))

        self.assertEqual(f64.get_exponent(x), 0)
        x = Float64(2.0).bits
        print (hex(x))
        self.assertEqual(f64.get_exponent(x), 1)

        x = Float64(1.5).bits
        m = f64.get_mantissa_field(x)
        print (hex(x), hex(m))
        self.assertEqual(m, 0x8000000000000)

        s = f64.get_sign_field(x)
        print (hex(x), hex(s))
        self.assertEqual(s, 0)

        x = Float64(-1.5).bits
        s = f64.get_sign_field(x)
        print (hex(x), hex(s))
        self.assertEqual(s, 1)

    def test_fpformat_fp32(self):
        f32 = FPFormat.standard(32)
        from sfpy import Float32
        x = Float32(1.0).bits
        print (hex(x))

        self.assertEqual(f32.get_exponent(x), 0)
        x = Float32(2.0).bits
        print (hex(x))
        self.assertEqual(f32.get_exponent(x), 1)

        x = Float32(1.5).bits
        m = f32.get_mantissa_field(x)
        print (hex(x), hex(m))
        self.assertEqual(m, 0x400000)

        # NaN test
        x = Float32(-1.0).sqrt()
        x = x.bits
        i = f32.is_nan(x)
        print (hex(x), "nan", f32.get_exponent(x), f32.e_max,
               f32.get_mantissa_field(x), i)
        self.assertEqual(i, True)

        # Inf test
        x = Float32(1e36) * Float32(1e36) * Float32(1e36)
        x = x.bits
        i = f32.is_inf(x)
        print (hex(x), "inf", f32.get_exponent(x), f32.e_max,
               f32.get_mantissa_field(x), i)
        self.assertEqual(i, True)

        # subnormal
        x = Float32(1e-41)
        x = x.bits
        i = f32.is_subnormal(x)
        print (hex(x), "sub", f32.get_exponent(x), f32.e_max,
               f32.get_mantissa_field(x), i)
        self.assertEqual(i, True)

        x = Float32(0.0)
        x = x.bits
        i = f32.is_subnormal(x)
        print (hex(x), "sub", f32.get_exponent(x), f32.e_max,
               f32.get_mantissa_field(x), i)
        self.assertEqual(i, False)

        # zero
        i = f32.is_zero(x)
        print (hex(x), "zero", f32.get_exponent(x), f32.e_max,
               f32.get_mantissa_field(x), i)
        self.assertEqual(i, True)


class MultiShiftR(Elaboratable):

    def __init__(self, width):
        self.width = width
        self.smax = bits_for(width - 1)
        self.i = Signal(width, reset_less=True)
        self.s = Signal(self.smax, reset_less=True)
        self.o = Signal(width, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.i >> self.s)
        return m


class MultiShift:
    """ Generates variable-length single-cycle shifter from a series
        of conditional tests on each bit of the left/right shift operand.
        Each bit tested produces output shifted by that number of bits,
        in a binary fashion: bit 1 if set shifts by 1 bit, bit 2 if set
        shifts by 2 bits, each partial result cascading to the next Mux.

        Could be adapted to do arithmetic shift by taking copies of the
        MSB instead of zeros.
    """

    def __init__(self, width):
        self.width = width
        self.smax = bits_for(width - 1)

    def lshift(self, op, s):
        res = op << s
        return res[:len(op)]

    def rshift(self, op, s):
        res = op >> s
        return res[:len(op)]


class FPNumBaseRecord:
    """ Floating-point Base Number Class.

    This class is designed to be passed around in other data structures
    (between pipelines and between stages).  Its "friend" is FPNumBase,
    which is a *module*.  The reason for the discernment is because
    nmigen modules that are not added to submodules results in the
    irritating "Elaboration" warning.  Despite not *needing* FPNumBase
    in many cases to be added as a submodule (because it is just data)
    this was not possible to solve without splitting out the data from
    the module.
    """

    def __init__(self, width, m_extra=True, e_extra=False, name=None):
        if name is None:
            name = ""
            # assert false, "missing name"
        else:
            name += "_"
        self.width = width
        m_width = {16: 11, 32: 24, 64: 53}[width]  # 1 extra bit (overflow)
        e_width = {16: 7,  32: 10, 64: 13}[width]  # 2 extra bits (overflow)
        e_max = 1 << (e_width-3)
        self.rmw = m_width - 1  # real mantissa width (not including extras)
        self.e_max = e_max
        if m_extra:
            # mantissa extra bits (top,guard,round)
            self.m_extra = 3
            m_width += self.m_extra
        else:
            self.m_extra = 0
        if e_extra:
            self.e_extra = 6  # enough to cover FP64 when converting to FP16
            e_width += self.e_extra
        else:
            self.e_extra = 0
        # print (m_width, e_width, e_max, self.rmw, self.m_extra)
        self.m_width = m_width
        self.e_width = e_width
        self.e_start = self.rmw
        self.e_end = self.rmw + self.e_width - 2  # for decoding

        self.v = Signal(width, reset_less=True,
                        name=name+"v")  # Latched copy of value
        self.m = Signal(m_width, reset_less=True, name=name+"m")  # Mantissa
        self.e = Signal(signed(e_width),
                        reset_less=True, name=name+"e")  # exp+2 bits, signed
        self.s = Signal(reset_less=True, name=name+"s")  # Sign bit

        self.fp = self
        self.drop_in(self)

    def drop_in(self, fp):
        fp.s = self.s
        fp.e = self.e
        fp.m = self.m
        fp.v = self.v
        fp.rmw = self.rmw
        fp.width = self.width
        fp.e_width = self.e_width
        fp.e_max = self.e_max
        fp.m_width = self.m_width
        fp.e_start = self.e_start
        fp.e_end = self.e_end
        fp.m_extra = self.m_extra

        m_width = self.m_width
        e_max = self.e_max
        e_width = self.e_width

        self.mzero = Const(0, unsigned(m_width))
        m_msb = 1 << (self.m_width-2)
        self.msb1 = Const(m_msb, unsigned(m_width))
        self.m1s = Const(-1, unsigned(m_width))
        self.P128 = Const(e_max, signed(e_width))
        self.P127 = Const(e_max-1, signed(e_width))
        self.N127 = Const(-(e_max-1), signed(e_width))
        self.N126 = Const(-(e_max-2), signed(e_width))

    def create(self, s, e, m):
        """ creates a value from sign / exponent / mantissa

            bias is added here, to the exponent.

            NOTE: order is important, because e_start/e_end can be
            a bit too long (overwriting s).
        """
        return [
          self.v[0:self.e_start].eq(m),        # mantissa
          self.v[self.e_start:self.e_end].eq(e + self.fp.P127),  # (add bias)
          self.v[-1].eq(s),          # sign
        ]

    def _nan(self, s):
        return (s, self.fp.P128, 1 << (self.e_start-1))

    def _inf(self, s):
        return (s, self.fp.P128, 0)

    def _zero(self, s):
        return (s, self.fp.N127, 0)

    def nan(self, s):
        return self.create(*self._nan(s))

    def quieted_nan(self, other):
        assert isinstance(other, FPNumBaseRecord)
        assert self.width == other.width
        return self.create(other.s, self.fp.P128,
                           other.v[0:self.e_start] | (1 << (self.e_start - 1)))

    def inf(self, s):
        return self.create(*self._inf(s))

    def max_normal(self, s):
        return self.create(s, self.fp.P127, ~0)

    def min_denormal(self, s):
        return self.create(s, self.fp.N127, 1)

    def zero(self, s):
        return self.create(*self._zero(s))

    def create2(self, s, e, m):
        """ creates a value from sign / exponent / mantissa

            bias is added here, to the exponent
        """
        e = e + self.P127  # exp (add on bias)
        return Cat(m[0:self.e_start],
                   e[0:self.e_end-self.e_start],
                   s)

    def nan2(self, s):
        return self.create2(s, self.P128, self.msb1)

    def inf2(self, s):
        return self.create2(s, self.P128, self.mzero)

    def zero2(self, s):
        return self.create2(s, self.N127, self.mzero)

    def __iter__(self):
        yield self.s
        yield self.e
        yield self.m

    def eq(self, inp):
        return [self.s.eq(inp.s), self.e.eq(inp.e), self.m.eq(inp.m)]


class FPNumBase(FPNumBaseRecord, Elaboratable):
    """ Floating-point Base Number Class
    """

    def __init__(self, fp):
        fp.drop_in(self)
        self.fp = fp
        e_width = fp.e_width

        self.is_nan = Signal(reset_less=True)
        self.is_zero = Signal(reset_less=True)
        self.is_inf = Signal(reset_less=True)
        self.is_overflowed = Signal(reset_less=True)
        self.is_denormalised = Signal(reset_less=True)
        self.exp_128 = Signal(reset_less=True)
        self.exp_sub_n126 = Signal(signed(e_width), reset_less=True)
        self.exp_lt_n126 = Signal(reset_less=True)
        self.exp_zero = Signal(reset_less=True)
        self.exp_gt_n126 = Signal(reset_less=True)
        self.exp_gt127 = Signal(reset_less=True)
        self.exp_n127 = Signal(reset_less=True)
        self.exp_n126 = Signal(reset_less=True)
        self.m_zero = Signal(reset_less=True)
        self.m_msbzero = Signal(reset_less=True)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.is_nan.eq(self._is_nan())
        m.d.comb += self.is_zero.eq(self._is_zero())
        m.d.comb += self.is_inf.eq(self._is_inf())
        m.d.comb += self.is_overflowed.eq(self._is_overflowed())
        m.d.comb += self.is_denormalised.eq(self._is_denormalised())
        m.d.comb += self.exp_128.eq(self.e == self.fp.P128)
        m.d.comb += self.exp_sub_n126.eq(self.e - self.fp.N126)
        m.d.comb += self.exp_gt_n126.eq(self.exp_sub_n126 > 0)
        m.d.comb += self.exp_lt_n126.eq(self.exp_sub_n126 < 0)
        m.d.comb += self.exp_zero.eq(self.e == 0)
        m.d.comb += self.exp_gt127.eq(self.e > self.fp.P127)
        m.d.comb += self.exp_n127.eq(self.e == self.fp.N127)
        m.d.comb += self.exp_n126.eq(self.e == self.fp.N126)
        m.d.comb += self.m_zero.eq(self.m == self.fp.mzero)
        m.d.comb += self.m_msbzero.eq(self.m[self.fp.e_start] == 0)

        return m

    def _is_nan(self):
        return (self.exp_128) & (~self.m_zero)

    def _is_inf(self):
        return (self.exp_128) & (self.m_zero)

    def _is_zero(self):
        return (self.exp_n127) & (self.m_zero)

    def _is_overflowed(self):
        return self.exp_gt127

    def _is_denormalised(self):
        # XXX NOT to be used for "official" quiet NaN tests!
        # particularly when the MSB has been extended
        return (self.exp_n126) & (self.m_msbzero)


class FPNumOut(FPNumBase):
    """ Floating-point Number Class

        Contains signals for an incoming copy of the value, decoded into
        sign / exponent / mantissa.
        Also contains encoding functions, creation and recognition of
        zero, NaN and inf (all signed)

        Four extra bits are included in the mantissa: the top bit
        (m[-1]) is effectively a carry-overflow.  The other three are
        guard (m[2]), round (m[1]), and sticky (m[0])
    """

    def __init__(self, fp):
        FPNumBase.__init__(self, fp)

    def elaborate(self, platform):
        m = FPNumBase.elaborate(self, platform)

        return m


class MultiShiftRMerge(Elaboratable):
    """ shifts down (right) and merges lower bits into m[0].
        m[0] is the "sticky" bit, basically
    """

    def __init__(self, width, s_max=None):
        if s_max is None:
            s_max = bits_for(width - 1)
        self.smax = Shape.cast(s_max)
        self.m = Signal(width, reset_less=True)
        self.inp = Signal(width, reset_less=True)
        self.diff = Signal(s_max, reset_less=True)
        self.width = width

    def elaborate(self, platform):
        m = Module()

        rs = Signal(self.width, reset_less=True)
        m_mask = Signal(self.width, reset_less=True)
        smask = Signal(self.width, reset_less=True)
        stickybit = Signal(reset_less=True)
        # XXX GRR frickin nuisance https://github.com/nmigen/nmigen/issues/302
        maxslen = Signal(self.smax.width, reset_less=True)
        maxsleni = Signal(self.smax.width, reset_less=True)

        sm = MultiShift(self.width-1)
        m0s = Const(0, self.width-1)
        mw = Const(self.width-1, len(self.diff))
        m.d.comb += [maxslen.eq(Mux(self.diff > mw, mw, self.diff)),
                     maxsleni.eq(Mux(self.diff > mw, 0, mw-self.diff)),
                     ]

        m.d.comb += [
                # shift mantissa by maxslen, mask by inverse
                rs.eq(sm.rshift(self.inp[1:], maxslen)),
                m_mask.eq(sm.rshift(~m0s, maxsleni)),
                smask.eq(self.inp[1:] & m_mask),
                # sticky bit combines all mask (and mantissa low bit)
                stickybit.eq(smask.bool() | self.inp[0]),
                # mantissa result contains m[0] already.
                self.m.eq(Cat(stickybit, rs))
           ]
        return m


class FPNumShift(FPNumBase, Elaboratable):
    """ Floating-point Number Class for shifting
    """

    def __init__(self, mainm, op, inv, width, m_extra=True):
        FPNumBase.__init__(self, width, m_extra)
        self.latch_in = Signal()
        self.mainm = mainm
        self.inv = inv
        self.op = op

    def elaborate(self, platform):
        m = FPNumBase.elaborate(self, platform)

        m.d.comb += self.s.eq(op.s)
        m.d.comb += self.e.eq(op.e)
        m.d.comb += self.m.eq(op.m)

        with self.mainm.State("align"):
            with m.If(self.e < self.inv.e):
                m.d.sync += self.shift_down()

        return m

    def shift_down(self, inp):
        """ shifts a mantissa down by one. exponent is increased to compensate

            accuracy is lost as a result in the mantissa however there are 3
            guard bits (the latter of which is the "sticky" bit)
        """
        return [self.e.eq(inp.e + 1),
                self.m.eq(Cat(inp.m[0] | inp.m[1], inp.m[2:], 0))
                ]

    def shift_down_multi(self, diff):
        """ shifts a mantissa down. exponent is increased to compensate

            accuracy is lost as a result in the mantissa however there are 3
            guard bits (the latter of which is the "sticky" bit)

            this code works by variable-shifting the mantissa by up to
            its maximum bit-length: no point doing more (it'll still be
            zero).

            the sticky bit is computed by shifting a batch of 1s by
            the same amount, which will introduce zeros.  it's then
            inverted and used as a mask to get the LSBs of the mantissa.
            those are then |'d into the sticky bit.
        """
        sm = MultiShift(self.width)
        mw = Const(self.m_width-1, len(diff))
        maxslen = Mux(diff > mw, mw, diff)
        rs = sm.rshift(self.m[1:], maxslen)
        maxsleni = mw - maxslen
        m_mask = sm.rshift(self.m1s[1:], maxsleni)  # shift and invert

        stickybits = reduce(or_, self.m[1:] & m_mask) | self.m[0]
        return [self.e.eq(self.e + diff),
                self.m.eq(Cat(stickybits, rs))
                ]

    def shift_up_multi(self, diff):
        """ shifts a mantissa up. exponent is decreased to compensate
        """
        sm = MultiShift(self.width)
        mw = Const(self.m_width, len(diff))
        maxslen = Mux(diff > mw, mw, diff)

        return [self.e.eq(self.e - diff),
                self.m.eq(sm.lshift(self.m, maxslen))
                ]


class FPNumDecode(FPNumBase):
    """ Floating-point Number Class

        Contains signals for an incoming copy of the value, decoded into
        sign / exponent / mantissa.
        Also contains encoding functions, creation and recognition of
        zero, NaN and inf (all signed)

        Four extra bits are included in the mantissa: the top bit
        (m[-1]) is effectively a carry-overflow.  The other three are
        guard (m[2]), round (m[1]), and sticky (m[0])
    """

    def __init__(self, op, fp):
        FPNumBase.__init__(self, fp)
        self.op = op

    def elaborate(self, platform):
        m = FPNumBase.elaborate(self, platform)

        m.d.comb += self.decode(self.v)

        return m

    def decode(self, v):
        """ decodes a latched value into sign / exponent / mantissa

            bias is subtracted here, from the exponent.  exponent
            is extended to 10 bits so that subtract 127 is done on
            a 10-bit number
        """
        args = [0] * self.m_extra + [v[0:self.e_start]]  # pad with extra zeros
        #print ("decode", self.e_end)
        return [self.m.eq(Cat(*args)),  # mantissa
                self.e.eq(v[self.e_start:self.e_end] - self.fp.P127),  # exp
                self.s.eq(v[-1]),                 # sign
                ]


class FPNumIn(FPNumBase):
    """ Floating-point Number Class

        Contains signals for an incoming copy of the value, decoded into
        sign / exponent / mantissa.
        Also contains encoding functions, creation and recognition of
        zero, NaN and inf (all signed)

        Four extra bits are included in the mantissa: the top bit
        (m[-1]) is effectively a carry-overflow.  The other three are
        guard (m[2]), round (m[1]), and sticky (m[0])
    """

    def __init__(self, op, fp):
        FPNumBase.__init__(self, fp)
        self.latch_in = Signal()
        self.op = op

    def decode2(self, m):
        """ decodes a latched value into sign / exponent / mantissa

            bias is subtracted here, from the exponent.  exponent
            is extended to 10 bits so that subtract 127 is done on
            a 10-bit number
        """
        v = self.v
        args = [0] * self.m_extra + [v[0:self.e_start]]  # pad with extra zeros
        #print ("decode", self.e_end)
        res = ObjectProxy(m, pipemode=False)
        res.m = Cat(*args)                             # mantissa
        res.e = v[self.e_start:self.e_end] - self.fp.P127  # exp
        res.s = v[-1]                                  # sign
        return res

    def decode(self, v):
        """ decodes a latched value into sign / exponent / mantissa

            bias is subtracted here, from the exponent.  exponent
            is extended to 10 bits so that subtract 127 is done on
            a 10-bit number
        """
        args = [0] * self.m_extra + [v[0:self.e_start]]  # pad with extra zeros
        #print ("decode", self.e_end)
        return [self.m.eq(Cat(*args)),  # mantissa
                self.e.eq(v[self.e_start:self.e_end] - self.P127),  # exp
                self.s.eq(v[-1]),                 # sign
                ]

    def shift_down(self, inp):
        """ shifts a mantissa down by one. exponent is increased to compensate

            accuracy is lost as a result in the mantissa however there are 3
            guard bits (the latter of which is the "sticky" bit)
        """
        return [self.e.eq(inp.e + 1),
                self.m.eq(Cat(inp.m[0] | inp.m[1], inp.m[2:], 0))
                ]

    def shift_down_multi(self, diff, inp=None):
        """ shifts a mantissa down. exponent is increased to compensate

            accuracy is lost as a result in the mantissa however there are 3
            guard bits (the latter of which is the "sticky" bit)

            this code works by variable-shifting the mantissa by up to
            its maximum bit-length: no point doing more (it'll still be
            zero).

            the sticky bit is computed by shifting a batch of 1s by
            the same amount, which will introduce zeros.  it's then
            inverted and used as a mask to get the LSBs of the mantissa.
            those are then |'d into the sticky bit.
        """
        if inp is None:
            inp = self
        sm = MultiShift(self.width)
        mw = Const(self.m_width-1, len(diff))
        maxslen = Mux(diff > mw, mw, diff)
        rs = sm.rshift(inp.m[1:], maxslen)
        maxsleni = mw - maxslen
        m_mask = sm.rshift(self.m1s[1:], maxsleni)  # shift and invert

        #stickybit = reduce(or_, inp.m[1:] & m_mask) | inp.m[0]
        stickybit = (inp.m[1:] & m_mask).bool() | inp.m[0]
        return [self.e.eq(inp.e + diff),
                self.m.eq(Cat(stickybit, rs))
                ]

    def shift_up_multi(self, diff):
        """ shifts a mantissa up. exponent is decreased to compensate
        """
        sm = MultiShift(self.width)
        mw = Const(self.m_width, len(diff))
        maxslen = Mux(diff > mw, mw, diff)

        return [self.e.eq(self.e - diff),
                self.m.eq(sm.lshift(self.m, maxslen))
                ]


class Trigger(Elaboratable):
    def __init__(self):

        self.stb = Signal(reset=0)
        self.ack = Signal()
        self.trigger = Signal(reset_less=True)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.trigger.eq(self.stb & self.ack)
        return m

    def eq(self, inp):
        return [self.stb.eq(inp.stb),
                self.ack.eq(inp.ack)
                ]

    def ports(self):
        return [self.stb, self.ack]


class FPOpIn(PrevControl):
    def __init__(self, width):
        PrevControl.__init__(self)
        self.width = width

    @property
    def v(self):
        return self.data_i

    def chain_inv(self, in_op, extra=None):
        stb = in_op.stb
        if extra is not None:
            stb = stb & extra
        return [self.v.eq(in_op.v),          # receive value
                self.stb.eq(stb),      # receive STB
                in_op.ack.eq(~self.ack),  # send ACK
                ]

    def chain_from(self, in_op, extra=None):
        stb = in_op.stb
        if extra is not None:
            stb = stb & extra
        return [self.v.eq(in_op.v),          # receive value
                self.stb.eq(stb),      # receive STB
                in_op.ack.eq(self.ack),  # send ACK
                ]


class FPOpOut(NextControl):
    def __init__(self, width):
        NextControl.__init__(self)
        self.width = width

    @property
    def v(self):
        return self.data_o

    def chain_inv(self, in_op, extra=None):
        stb = in_op.stb
        if extra is not None:
            stb = stb & extra
        return [self.v.eq(in_op.v),          # receive value
                self.stb.eq(stb),      # receive STB
                in_op.ack.eq(~self.ack),  # send ACK
                ]

    def chain_from(self, in_op, extra=None):
        stb = in_op.stb
        if extra is not None:
            stb = stb & extra
        return [self.v.eq(in_op.v),          # receive value
                self.stb.eq(stb),      # receive STB
                in_op.ack.eq(self.ack),  # send ACK
                ]


class Overflow:
    # TODO: change FFLAGS to be FPSCR's status flags
    FFLAGS_NV = Const(1<<4, 5) # invalid operation
    FFLAGS_DZ = Const(1<<3, 5) # divide by zero
    FFLAGS_OF = Const(1<<2, 5) # overflow
    FFLAGS_UF = Const(1<<1, 5) # underflow
    FFLAGS_NX = Const(1<<0, 5) # inexact
    def __init__(self, name=None):
        if name is None:
            name = ""
        self.guard = Signal(reset_less=True, name=name+"guard")     # tot[2]
        self.round_bit = Signal(reset_less=True, name=name+"round")  # tot[1]
        self.sticky = Signal(reset_less=True, name=name+"sticky")   # tot[0]
        self.m0 = Signal(reset_less=True, name=name+"m0")  # mantissa bit 0
        self.fpflags = Signal(5, reset_less=True, name=name+"fflags")

        self.sign = Signal(reset_less=True, name=name+"sign")
        """sign bit -- 1 means negative, 0 means positive"""

        self.rm = Signal(FPRoundingMode, name=name+"rm",
                         reset=FPRoundingMode.DEFAULT)
        """rounding mode"""

        #self.roundz = Signal(reset_less=True)

    def __iter__(self):
        yield self.guard
        yield self.round_bit
        yield self.sticky
        yield self.m0
        yield self.fpflags
        yield self.sign
        yield self.rm

    def eq(self, inp):
        return [self.guard.eq(inp.guard),
                self.round_bit.eq(inp.round_bit),
                self.sticky.eq(inp.sticky),
                self.m0.eq(inp.m0),
                self.fpflags.eq(inp.fpflags),
                self.sign.eq(inp.sign),
                self.rm.eq(inp.rm)]

    @property
    def roundz_rne(self):
        """true if the mantissa should be rounded up for `rm == RNE`

        assumes the rounding mode is `ROUND_NEAREST_TIES_TO_EVEN`
        """
        return self.guard & (self.round_bit | self.sticky | self.m0)

    @property
    def roundz_rna(self):
        """true if the mantissa should be rounded up for `rm == RNA`

        assumes the rounding mode is `ROUND_NEAREST_TIES_TO_AWAY`
        """
        return self.guard

    @property
    def roundz_rtn(self):
        """true if the mantissa should be rounded up for `rm == RTN`

        assumes the rounding mode is `ROUND_TOWARDS_NEGATIVE`
        """
        return self.sign & (self.guard | self.round_bit | self.sticky)

    @property
    def roundz_rto(self):
        """true if the mantissa should be rounded up for `rm in (RTOP, RTON)`

        assumes the rounding mode is `ROUND_TO_ODD_UNSIGNED_ZEROS_ARE_POSITIVE`
        or `ROUND_TO_ODD_UNSIGNED_ZEROS_ARE_NEGATIVE`
        """
        return ~self.m0 & (self.guard | self.round_bit | self.sticky)

    @property
    def roundz_rtp(self):
        """true if the mantissa should be rounded up for `rm == RTP`

        assumes the rounding mode is `ROUND_TOWARDS_POSITIVE`
        """
        return ~self.sign & (self.guard | self.round_bit | self.sticky)

    @property
    def roundz_rtz(self):
        """true if the mantissa should be rounded up for `rm == RTZ`

        assumes the rounding mode is `ROUND_TOWARDS_ZERO`
        """
        return False

    @property
    def roundz(self):
        """true if the mantissa should be rounded up for the current rounding
        mode `self.rm`
        """
        d = {
            FPRoundingMode.RNA: self.roundz_rna,
            FPRoundingMode.RNE: self.roundz_rne,
            FPRoundingMode.RTN: self.roundz_rtn,
            FPRoundingMode.RTOP: self.roundz_rto,
            FPRoundingMode.RTON: self.roundz_rto,
            FPRoundingMode.RTP: self.roundz_rtp,
            FPRoundingMode.RTZ: self.roundz_rtz,
        }
        return FPRoundingMode.make_array(lambda rm: d[rm])[self.rm]


class OverflowMod(Elaboratable, Overflow):
    def __init__(self, name=None):
        Overflow.__init__(self, name)
        if name is None:
            name = ""
        self.roundz_out = Signal(reset_less=True, name=name+"roundz_out")

    def __iter__(self):
        yield from Overflow.__iter__(self)
        yield self.roundz_out

    def eq(self, inp):
        return [self.roundz_out.eq(inp.roundz_out)] + Overflow.eq(self)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.roundz_out.eq(self.roundz) # roundz is a property
        return m


class FPBase:
    """ IEEE754 Floating Point Base Class

        contains common functions for FP manipulation, such as
        extracting and packing operands, normalisation, denormalisation,
        rounding etc.
    """

    def get_op(self, m, op, v, next_state):
        """ this function moves to the next state and copies the operand
            when both stb and ack are 1.
            acknowledgement is sent by setting ack to ZERO.
        """
        res = v.decode2(m)
        ack = Signal()
        with m.If((op.ready_o) & (op.valid_i_test)):
            m.next = next_state
            # op is latched in from FPNumIn class on same ack/stb
            m.d.comb += ack.eq(0)
        with m.Else():
            m.d.comb += ack.eq(1)
        return [res, ack]

    def denormalise(self, m, a):
        """ denormalises a number.  this is probably the wrong name for
            this function.  for normalised numbers (exponent != minimum)
            one *extra* bit (the implicit 1) is added *back in*.
            for denormalised numbers, the mantissa is left alone
            and the exponent increased by 1.

            both cases *effectively multiply the number stored by 2*,
            which has to be taken into account when extracting the result.
        """
        with m.If(a.exp_n127):
            m.d.sync += a.e.eq(a.fp.N126)  # limit a exponent
        with m.Else():
            m.d.sync += a.m[-1].eq(1)  # set top mantissa bit

    def op_normalise(self, m, op, next_state):
        """ operand normalisation
            NOTE: just like "align", this one keeps going round every clock
                  until the result's exponent is within acceptable "range"
        """
        with m.If((op.m[-1] == 0)):  # check last bit of mantissa
            m.d.sync += [
                op.e.eq(op.e - 1),  # DECREASE exponent
                op.m.eq(op.m << 1),  # shift mantissa UP
            ]
        with m.Else():
            m.next = next_state

    def normalise_1(self, m, z, of, next_state):
        """ first stage normalisation

            NOTE: just like "align", this one keeps going round every clock
                  until the result's exponent is within acceptable "range"
            NOTE: the weirdness of reassigning guard and round is due to
                  the extra mantissa bits coming from tot[0..2]
        """
        with m.If((z.m[-1] == 0) & (z.e > z.fp.N126)):
            m.d.sync += [
                z.e.eq(z.e - 1),  # DECREASE exponent
                z.m.eq(z.m << 1),  # shift mantissa UP
                z.m[0].eq(of.guard),       # steal guard bit (was tot[2])
                of.guard.eq(of.round_bit),  # steal round_bit (was tot[1])
                of.round_bit.eq(0),        # reset round bit
                of.m0.eq(of.guard),
            ]
        with m.Else():
            m.next = next_state

    def normalise_2(self, m, z, of, next_state):
        """ second stage normalisation

            NOTE: just like "align", this one keeps going round every clock
                  until the result's exponent is within acceptable "range"
            NOTE: the weirdness of reassigning guard and round is due to
                  the extra mantissa bits coming from tot[0..2]
        """
        with m.If(z.e < z.fp.N126):
            m.d.sync += [
                z.e.eq(z.e + 1),  # INCREASE exponent
                z.m.eq(z.m >> 1),  # shift mantissa DOWN
                of.guard.eq(z.m[0]),
                of.m0.eq(z.m[1]),
                of.round_bit.eq(of.guard),
                of.sticky.eq(of.sticky | of.round_bit)
            ]
        with m.Else():
            m.next = next_state

    def roundz(self, m, z, roundz):
        """ performs rounding on the output.  TODO: different kinds of rounding
        """
        with m.If(roundz):
            m.d.sync += z.m.eq(z.m + 1)  # mantissa rounds up
            with m.If(z.m == z.fp.m1s):  # all 1s
                m.d.sync += z.e.eq(z.e + 1)  # exponent rounds up

    def corrections(self, m, z, next_state):
        """ denormalisation and sign-bug corrections
        """
        m.next = next_state
        # denormalised, correct exponent to zero
        with m.If(z.is_denormalised):
            m.d.sync += z.e.eq(z.fp.N127)

    def pack(self, m, z, next_state):
        """ packs the result into the output (detects overflow->Inf)
        """
        m.next = next_state
        # if overflow occurs, return inf
        with m.If(z.is_overflowed):
            m.d.sync += z.inf(z.s)
        with m.Else():
            m.d.sync += z.create(z.s, z.e, z.m)

    def put_z(self, m, z, out_z, next_state):
        """ put_z: stores the result in the output.  raises stb and waits
            for ack to be set to 1 before moving to the next state.
            resets stb back to zero when that occurs, as acknowledgement.
        """
        m.d.sync += [
          out_z.v.eq(z.v)
        ]
        with m.If(out_z.valid_o & out_z.ready_i_test):
            m.d.sync += out_z.valid_o.eq(0)
            m.next = next_state
        with m.Else():
            m.d.sync += out_z.valid_o.eq(1)


class FPState(FPBase):
    def __init__(self, state_from):
        self.state_from = state_from

    def set_inputs(self, inputs):
        self.inputs = inputs
        for k, v in inputs.items():
            setattr(self, k, v)

    def set_outputs(self, outputs):
        self.outputs = outputs
        for k, v in outputs.items():
            setattr(self, k, v)


class FPID:
    def __init__(self, id_wid):
        self.id_wid = id_wid
        if self.id_wid:
            self.in_mid = Signal(id_wid, reset_less=True)
            self.out_mid = Signal(id_wid, reset_less=True)
        else:
            self.in_mid = None
            self.out_mid = None

    def idsync(self, m):
        if self.id_wid is not None:
            m.d.sync += self.out_mid.eq(self.in_mid)


if __name__ == '__main__':
    unittest.main()
