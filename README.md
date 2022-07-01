# IEEE754 Floating-Point ALU, in nmigen(tm)

nmigen (and all aliases) are Trademarks of M-Labs.
nmigen is a Registered Trademark of M-Labs
https://uspto.report/TM/88980893

This project implements a parameteriseable pipelined IEEE754 floating-point
ALU that supports FP16, FP32 and FP64.  Other FP sizes (FP80, BF16, FP128)
are a matter of adding new parameters for mantissa and exponent.
The IEEE754 FP Library is a general-purpose unit that may be used in
any project (not limited to one specific processor).  Limited Formal
Correctness Proofs are provided (so far for fpadd, fpsub) as well as
hundreds of thousands of unit tests.

Developed under Grants from NLnet (http://nlnet.nl), from
EU Grants 871528 and 957073.  more information may be found at
http://libre-soc.org

# Requirements

* nmigen (https://gitlab.com/nmigen/nmigen)
* libresoc-nmutil (https://git.libre-soc.org/?p=nmutil.git;a=summary)
* yosys (latest git repository, required by nmigen)
* sfpy (running unit tests).  provides python bindings to berkeley softfloat-3

# Building sfpy

The standard sfpy will not work without being modified to the type of
IEEE754 FP emulation being tested.  This FPU is emulating RISC-V, and
there is some weirdness in x86 IEEE754 implementations when it comes
to FP16 non-canonical NaNs.

The following modifications are required to the sfpy berkeley-softfloat-3
submodule:

    cd /path/to/sfpy/berkeley-softfloat-3
    git apply /path/to/ieee754fpu/berkeley-softfloat.patch

The following modifications are required to the sfpy SoftPosit Makefile:

    cd /path/to/sfpy/SoftPosit
    git apply /path/to/ieee754fpu/SoftPosit.patch

# Useful resources

* https://en.wikipedia.org/wiki/IEEE_754-1985
* http://weitz.de/ieee/
* https://steve.hollasch.net/cgindex/coding/ieeefloat.html

