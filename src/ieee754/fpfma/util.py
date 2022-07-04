from ieee754.fpcommon.fpbase import FPFormat
from nmigen.hdl.ast import signed, unsigned


def expanded_exponent_shape(fpformat):
    assert isinstance(fpformat, FPFormat)
    return signed(fpformat.e_width + 3)


EXPANDED_MANTISSA_SPACE_BETWEEN_SUM_PROD = 16  # FIXME: change back to 3
r""" the number of bits of space between the lsb of a large addend and the msb
of the product of two small factors to guarantee that the product ends up
entirely in the sticky bit.

e.g. let's assume the floating point format has
5 mantissa bits (4 bits in the field + 1 implicit bit):

if `a` and `b` are `0b11111` and `c` is `0b11111 * 2**-50`, and we are
computing `a * c + b`:

the computed mantissa would be:

```text
      sticky bit
         |
         v
0b111110001111000001
  \-b-/   \-product/
```

(note this isn't the mathematically correct
answer, but it rounds to the correct floating-point answer and takes
less hardware)
"""

# the number of extra LSBs needed by the expanded mantissa to avoid
# having a tiny addend conflict with the lsb of the product.
EXPANDED_MANTISSA_EXTRA_LSBS = 16  # FIXME: change back to 2


# the number of extra MSBs needed by the expanded mantissa to avoid
# overflowing. 2 bits -- 1 bit for carry out of addition, 1 bit for sign.
EXPANDED_MANTISSA_EXTRA_MSBS = 16  # FIXME: change back to 2


def expanded_mantissa_shape(fpformat):
    assert isinstance(fpformat, FPFormat)
    return signed((fpformat.fraction_width + 1) * 3
                  + EXPANDED_MANTISSA_EXTRA_MSBS
                  + EXPANDED_MANTISSA_SPACE_BETWEEN_SUM_PROD
                  + EXPANDED_MANTISSA_EXTRA_LSBS)


def multiplicand_mantissa_shape(fpformat):
    assert isinstance(fpformat, FPFormat)
    return unsigned(fpformat.fraction_width + 1)


def product_mantissa_shape(fpformat):
    assert isinstance(fpformat, FPFormat)
    return unsigned(multiplicand_mantissa_shape(fpformat).width * 2)
