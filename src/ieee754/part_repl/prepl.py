# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2021 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "repl" class, directly equivalent
to nmigen Repl

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/repl
* http://bugs.libre-riscv.org/show_bug.cgi?id=709

"""



modcount = 0 # global for now
def PRepl(m, repl, qty, ctx):
    from ieee754.part_repl.repl import PartitionedRepl # recursion issue
    global modcount
    modcount += 1
    pc = PartitionedRepl(repl, qty, ctx)
    setattr(m.submodules, "repl%d" % modcount, pc)
    return pc.output

