# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
# Copyright (C) 2021 Luke Kenneth Casson Leighton <lkcl@lkcl.net>


modcount = 0 # global for now
def PCat(m, arglist, ctx):
    from ieee754.part_cat.cat import PartitionedCat # avoid recursive import
    global modcount
    modcount += 1
    pc = PartitionedCat(arglist, ctx)
    setattr(m.submodules, "pcat%d" % modcount, pc)
    return pc.output
