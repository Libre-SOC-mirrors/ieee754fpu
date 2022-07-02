from ieee754.fpcommon.fpbase import FPFormat
from nmigen.hdl.ast import signed, unsigned


def expanded_exponent_shape(fpformat):
    assert isinstance(fpformat, FPFormat)
    return signed(fpformat.e_width + 3)


EXPANDED_MANTISSA_EXTRA_LSBS = 3


def expanded_mantissa_shape(fpformat):
    assert isinstance(fpformat, FPFormat)
    return signed(fpformat.fraction_width * 3 +
                  2 + EXPANDED_MANTISSA_EXTRA_LSBS)


def multiplicand_mantissa_shape(fpformat):
    assert isinstance(fpformat, FPFormat)
    return unsigned(fpformat.fraction_width + 1)


def product_mantissa_shape(fpformat):
    assert isinstance(fpformat, FPFormat)
    return unsigned(multiplicand_mantissa_shape(fpformat).width * 2)


def get_fpformat(pspec):
    width = pspec.width
    assert isinstance(width, int)
    fpformat = getattr(pspec, "fpformat", None)
    if fpformat is None:
        fpformat = FPFormat.standard(width)
    else:
        assert isinstance(fpformat, FPFormat)
    assert width == fpformat.width
    return fpformat
