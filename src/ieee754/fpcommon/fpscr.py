# SPDX-License-Identifier: LGPLv3+
# Funded by NLnet https://nlnet.nl/

""" Record for FPSCR as defined in
Power ISA v3.1B Book I section 4.2.2 page 136(162)

FPSCR fields in MSB0:

|Bits |Mnemonic | Description                                                 |
|-----|---------|-------------------------------------------------------------|
|0:28 | &nbsp;  | Reserved                                                    |
|29:31| DRN     | Decimal Rounding Mode                                       |
|32   | FX      | FP Exception Summary                                        |
|33   | FEX     | FP Enabled Exception Summary                                |
|34   | VX      | FP Invalid Operation Exception Summary                      |
|35   | OX      | FP Overflow Exception                                       |
|36   | UX      | FP Underflow Exception                                      |
|37   | ZX      | FP Zero Divide Exception                                    |
|38   | XX      | FP Inexact Exception                                        |
|39   | VXSNAN  | FP Invalid Operation Exception (SNaN)                       |
|40   | VXISI   | FP Invalid Operation Exception (∞ - ∞)                      |
|41   | VXIDI   | FP Invalid Operation Exception (∞ ÷ ∞)                      |
|42   | VXZDZ   | FP Invalid Operation Exception (0 ÷ 0)                      |
|43   | VXIMZ   | FP Invalid Operation Exception (∞ × 0)                      |
|44   | VXVC    | FP Invalid Operation Exception (Invalid Compare)            |
|45   | FR      | FP Fraction Rounded                                         |
|46   | FI      | FP Fraction Inexact                                         |
|47:51| FPRF    | FP Result Flags                                             |
|47   | C       | FP Result Class Descriptor                                  |
|48:51| FPCC    | FP Condition Code                                           |
|48   | FL      | FP Less Than or Negative                                    |
|49   | FG      | FP Greater Than or Positive                                 |
|50   | FE      | FP Equal or Zero                                            |
|51   | FU      | FP Unordered or NaN                                         |
|52   | &nbsp;  | Reserved                                                    |
|53   | VXSOFT  | FP Invalid Operation Exception (Software-Defined Condition) |
|54   | VXSQRT  | FP Invalid Operation Exception (Invalid Square Root)        |
|55   | VXCVI   | FP Invalid Operation Exception (Invalid Integer Convert)    |
|56   | VE      | FP Invalid Operation Exception Enable                       |
|57   | OE      | FP Overflow Exception Enable                                |
|58   | UE      | FP Underflow Exception Enable                               |
|59   | ZE      | FP Zero Divide Exception Enable                             |
|60   | XE      | FP Inexact Exception Enable                                 |
|61   | NI      | FP Non-IEEE Mode                                            |
|62:63| RN      | FP Rounding Control                                         |


https://bugs.libre-soc.org/show_bug.cgi?id=1135
to allow FP ops to compute in parallel despite each fp op semantically reading
the FPSCR output from the previous op, the FPSCR will be split into 3 parts
(I picked names that aren't necessarily standard names):
* volatile part: written nearly every insn but is rarely read
    FR, FI, FPRF
* sticky part: usually doesn't change but is read/written by nearly all insns:
    all the sticky exception bits
* control part: generally doesn't change and is only read by nearly all insns:
    all the other bits

The explanation of why FPSCR is split into 3 parts follows, we may not
implement it this way.

Additionally, as of Aug 2023 we're not planning on implementing it this way
anytime soon.

the idea is that the cpu will have all three parts in separate registers and
will speculatively execute fp insns with the current value of the sticky part
register (not the one from the previous instruction, but the one from the
register, avoiding needing a dependency chain), and then will cancel and retry
all later insns if it turns out that the insn changed the sticky part (which
is rare).

if desired the control part can be put in the same register and handled the
same way as the sticky part, but this makes code that temporarily changes the
rounding mode slower than necessary (common in x87 emulation and some math
library functions).
"""

from nmigen import Record, Shape
from enum import Enum, Flag, unique
from functools import lru_cache


class RoundingMode(Enum):
    # names match:
    # * PowerISA rounding modes (v3.1B 4.3.6 page 143(169))
    # * PowerISA bfp_ROUND_<mode> functions (v3.1B 7.6.2.2 page 607(633))
    # * SMTLIB abbreviated rounding modes
    # https://smtlib.cs.uiowa.edu/theories-FloatingPoint.shtml
    RNE = 0b00
    NearEven = RNE
    RoundToNearest = RNE
    RTZ = 0b01
    Trunc = RTZ
    RoundTowardZero = RTZ
    RTP = 0b10
    Ceil = RTP
    RoundTowardPosInfinity = RTP
    RTN = 0b11
    Floor = RTN
    RoundTowardNegInfinity = RTN


assert Shape.cast(RoundingMode) == Shape(width=2, signed=False)


class FPSCRBase(Record):
    @unique
    class Part(Enum):
        Volatile = "volatile"
        "the part written nearly every insn but rarely read"

        Sticky = "sticky"
        """usually doesn't change but is read/written by nearly all
        instructions in order to or-in exception bits
        """

        Control = "control"
        "generally doesn't change and is only read by nearly all instructions"

        Everything = "everything"

        @property
        @lru_cache(maxsize=None)
        def layout(self):
            Part = __class__
            l = (
                ("RN", RoundingMode, Part.Control),
                ("NI", 1, Part.Control),
                ("XE", 1, Part.Control),
                ("ZE", 1, Part.Control),
                ("UE", 1, Part.Control),
                ("OE", 1, Part.Control),
                ("VE", 1, Part.Control),
                ("VXCVI", 1, Part.Sticky),
                ("VXSQRT", 1, Part.Sticky),

                # we may decide to set VXSOFT if something like `fcospi`
                # causes an invalid exception, because it doesn't have an
                # assigned exception bit and because doing it that way makes
                # it match the math library better.
                ("VXSOFT", 1, Part.Sticky),
                ("rsvd1", 1, Part.Control),
                ("FPRF", (
                    ("FPCC", (
                        ("FU", 1),
                        ("FE", 1),
                        ("FG", 1),
                        ("FL", 1),
                    )),
                    ("C", 1),
                ), Part.Volatile),
                ("FI", 1, Part.Volatile),
                ("FR", 1, Part.Volatile),
                ("VXVC", 1, Part.Sticky),
                ("VXIMZ", 1, Part.Sticky),
                ("VXZDZ", 1, Part.Sticky),
                ("VXIDI", 1, Part.Sticky),
                ("VXISI", 1, Part.Sticky),
                ("VXSNAN", 1, Part.Sticky),
                ("XX", 1, Part.Sticky),
                ("ZX", 1, Part.Sticky),
                ("UX", 1, Part.Sticky),
                ("OX", 1, Part.Sticky),
                ("VX", 1, Part.Sticky),
                ("FEX", 1, Part.Sticky),
                ("FX", 1, Part.Sticky),
                ("DRN", 3, Part.Control),
                ("rsvd2", 29, Part.Control),
            )
            everything = self is Part.Everything
            return tuple((n, s) for n, s, p in l if everything or p is self)

    PART = Part.Everything
    layout = PART.layout

    def __init__(self, *, name=None, fields=None, src_loc_at=0):
        super().__init__(layout=self.PART.layout, name=name,
                         fields=fields, src_loc_at=src_loc_at + 1)


class FPSCR(FPSCRBase):
    def calc_summary(self):
        """calculate and assign the summary bits in self"""
        return [
            self.fields['VX'].eq(self.VX),
            self.fields['FEX'].eq(self.FEX),
        ]

    @property
    def VX(self):
        return (self.VXSNAN |
                self.VXISI |
                self.VXIDI |
                self.VXZDZ |
                self.VXIMZ |
                self.VXVC |
                self.VXSOFT |
                self.VXSQRT |
                self.VXCVI)

    @property
    def FEX(self):
        return ((self.VX & self.VE) |
                (self.OX & self.OE) |
                (self.UX & self.UE) |
                (self.ZX & self.ZE) |
                (self.XX & self.XE))

    @staticmethod
    def __make_record(fields, cls, name, src_loc_at):
        return cls(name=name, fields=fields, src_loc_at=1+src_loc_at)

    def volatile_part(self, *, name=None, src_loc_at=0):
        return FPSCR.__make_record(self.fields, cls=FPSCRVolatilePart,
                                   name=name, src_loc_at=1+src_loc_at)

    def sticky_part(self, *, name=None, src_loc_at=0):
        return FPSCR.__make_record(self.fields, cls=FPSCRStickyPart,
                                   name=name, src_loc_at=1+src_loc_at)

    def control_part(self, *, name=None, src_loc_at=0):
        return FPSCR.__make_record(self.fields, cls=FPSCRControlPart,
                                   name=name, src_loc_at=1+src_loc_at)

    @staticmethod
    def from_parts(*, volatile_part, sticky_part, control_part,
                   name=None, src_loc_at=0):
        fields = {**volatile_part.fields,
                  **sticky_part.fields,
                  **control_part.fields}
        return FPSCR.__make_record(fields, cls=FPSCR,
                                   name=name, src_loc_at=1+src_loc_at)


class FPSCRVolatilePart(FPSCRBase):
    """ the part of FPSCR that is written by nearly every FP instruction,
    but is rarely read.
    """
    PART = FPSCR.Part.Volatile
    layout = PART.layout


class FPSCRStickyPart(FPSCRBase):
    """ the part of FPSCR that usually doesn't change but is read/written by
    nearly all FP instructions in order to or-in exception bits.
    """
    PART = FPSCR.Part.Sticky
    layout = PART.layout


class FPSCRControlPart(FPSCRBase):
    """ the part of FPSCR that generally doesn't change and is read by
    nearly all FP instructions.
    """

    PART = FPSCR.Part.Control
    layout = PART.layout


if __name__ == "__main__":
    from pprint import pprint
    for part in FPSCR.Part:
        print(f"{part}.layout:")
        pprint(part.layout)
