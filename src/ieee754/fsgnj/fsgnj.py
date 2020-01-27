# IEEE Floating Point Conversion, FSGNJ
# Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>


from nmigen import Module, Signal, Cat, Mux

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.packdata import FPPackData
from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord


class FSGNJPipeMod(PipeModBase):
    """ FP Sign injection - replaces operand A's sign bit with one
        generated from operand B

        self.ctx.i.op & 0x3 == 0x0 : Copy sign bit from operand B
        self.ctx.i.op & 0x3 == 0x1 : Copy inverted sign bit from operand B
        self.ctx.i.op & 0x3 == 0x2 : Sign bit is A's sign XOR B's sign
    """
    def __init__(self, in_pspec):
        self.in_pspec = in_pspec
        super().__init__(in_pspec, "fsgnj")

    def ispec(self):
        return FPBaseData(self.in_pspec)

    def ospec(self):
        return FPPackData(self.in_pspec)

    def elaborate(self, platform):
        m = Module()

        width = self.pspec.width
        comb = m.d.comb

        z1 = self.o.z

        # Decode the input operands into sign, exponent, and mantissa
        a1 = FPNumBaseRecord(width, False)
        b1 = FPNumBaseRecord(width, False)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)
        comb += [a1.v.eq(self.i.a),
                 b1.v.eq(self.i.b)]

        opcode = self.i.ctx.op


        # Calculate the sign bit
        sign = Signal(reset_less=True)

        # Handle opcodes 0b00 and 0b01, copying or inverting the sign bit of B
        sign = Mux(opcode[0], ~b1.s, b1.s)
        # Handle opcodes 0b10 and 0b11, XORing the sign bits of a and b together.
        # opcode 0b11 is not defined in the RISCV spec; it is handled
        # here as equivalent to opcode 0b10 (i.e. a1.s XOR b1.s)
        # because this requires slightly less logic than making it the
        # same as opcode 0b00 (1 less Mux).
        sign = Mux(opcode[1], b1.s ^ a1.s, sign)


        # Create the floating point number from the sign bit
        # calculated earlier and the exponent and mantissa of operand a
        comb += z1.eq(a1.fp.create2(sign, a1.e, a1.m))

        # copy the context (muxid, operator)
        comb += self.o.ctx.eq(self.i.ctx)

        return m
