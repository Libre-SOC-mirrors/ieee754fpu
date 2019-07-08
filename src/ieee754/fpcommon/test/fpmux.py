""" key strategic example showing how to do multi-input fan-in into a
    multi-stage pipeline, then multi-output fanout.

    the multiplex ID from the fan-in is passed in to the pipeline, preserved,
    and used as a routing ID on the fanout.
"""

from random import randint
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil


class MuxInOut:
    def __init__(self, dut, width, fpkls, fpop, vals, single_op):
        self.dut = dut
        self.fpkls = fpkls
        self.fpop = fpop
        self.single_op = single_op
        self.di = {}
        self.do = {}
        self.tlen = len(vals) // dut.num_rows
        self.width = width
        for muxid in range(dut.num_rows):
            self.di[muxid] = {}
            self.do[muxid] = []
            for i in range(self.tlen):
                if self.single_op:
                    (op1, ) = vals.pop(0)
                    res = self.fpop(self.fpkls(op1))
                    self.di[muxid][i] = (op1, )
                else:
                    (op1, op2, ) = vals.pop(0)
                    #print ("test", hex(op1), hex(op2))
                    res = self.fpop(self.fpkls(op1), self.fpkls(op2))
                    self.di[muxid][i] = (op1, op2)
                self.do[muxid].append(res.bits)

    def send(self, muxid):
        for i in range(self.tlen):
            if self.single_op:
                op1, = self.di[muxid][i]
            else:
                op1, op2 = self.di[muxid][i]
            rs = self.dut.p[muxid]
            yield rs.valid_i.eq(1)
            yield rs.data_i.a.eq(op1)
            if not self.single_op:
                yield rs.data_i.b.eq(op2)
            yield rs.data_i.muxid.eq(muxid)
            yield
            o_p_ready = yield rs.ready_o
            while not o_p_ready:
                yield
                o_p_ready = yield rs.ready_o

            if self.single_op:
                fop1 = self.fpkls(op1)
                res = self.fpop(fop1)
                print ("send", muxid, i, hex(op1), hex(res.bits),
                               fop1, res)
            else:
                fop1 = self.fpkls(op1)
                fop2 = self.fpkls(op2)
                res = self.fpop(fop1, fop2)
                print ("send", muxid, i, hex(op1), hex(op2), hex(res.bits),
                               fop1, fop2, res)

            yield rs.valid_i.eq(0)
            # wait random period of time before queueing another value
            for i in range(randint(0, 3)):
                yield

        yield rs.valid_i.eq(0)
        yield

        print ("send ended", muxid)

        ## wait random period of time before queueing another value
        #for i in range(randint(0, 3)):
        #    yield

        #send_range = randint(0, 3)
        #if send_range == 0:
        #    send = True
        #else:
        #    send = randint(0, send_range) != 0

    def rcv(self, muxid):
        while True:
            #stall_range = randint(0, 3)
            #for j in range(randint(1,10)):
            #    stall = randint(0, stall_range) != 0
            #    yield self.dut.n[0].ready_i.eq(stall)
            #    yield
            n = self.dut.n[muxid]
            yield n.ready_i.eq(1)
            yield
            o_n_valid = yield n.valid_o
            i_n_ready = yield n.ready_i
            if not o_n_valid or not i_n_ready:
                continue

            out_muxid = yield n.data_o.muxid
            out_z = yield n.data_o.z

            out_i = 0

            print ("recv", out_muxid, hex(out_z), "expected",
                        hex(self.do[muxid][out_i] ))

            # see if this output has occurred already, delete it if it has
            assert muxid == out_muxid, "out_muxid %d not correct %d" % \
                                       (out_muxid, muxid)
            assert self.do[muxid][out_i] == out_z
            del self.do[muxid][out_i]

            # check if there's any more outputs
            if len(self.do[muxid]) == 0:
                break
        print ("recv ended", muxid)


def create_random(num_rows, width, single_op=False, n_vals=10):
    vals = []
    for muxid in range(num_rows):
        for i in range(n_vals):
            if single_op:
                op1 = randint(0, (1<<width)-1)
                #op1 = 0x40900000
                #op1 = 0x94607b66
                #op1 = 0x889cd8c
                #op1 = 0xe98646d7
                #op1 = 0x3340f2a7
                #op1 = 0xfff13f05
                #op1 = 0x453eb000
                #op1 = 0x3a05de50
                #op1 = 0xc27ff989
                #op1 = 0x41689000
                #op1 = 0xbbc0edec
                #op1 = 0x2EDBE6FF
                #op1 = 0x358637BD
                #op1 = 0x3340f2a7
                #op1 = 0x33D6BF95
                #op1 = 0x9885020648d8c0e8
                vals.append((op1,))
            else:
                op1 = randint(0, (1<<width)-1)
                op2 = randint(0, (1<<width)-1)
                vals.append((op1, op2,))
    return vals


def repeat(num_rows, vals):
    """ bit of a hack: repeats the last value to create a list
        that will be accepted by the muxer, all mux lists to be
        of equal length
    """
    vals = list(vals)
    n_to_repeat = len(vals) % num_rows
    return vals + [vals[-1]] * n_to_repeat


def pipe_cornercases_repeat(dut, name, mod, fmod, width, fn, cc, fpfn, count,
                            single_op=False):
    for i, fixed_num in enumerate(cc(mod)):
        vals = fn(mod, fixed_num, count, width)
        vals = repeat(dut.num_rows, vals)
        fmt = "test_pipe_fp%d_%s_cornercases_%d"
        runfp(dut, width, fmt % (width, name, i),
                   fmod, fpfn, vals=vals, single_op=single_op)


def runfp(dut, width, name, fpkls, fpop, single_op=False, n_vals=10, vals=None):
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("%s.il" % name, "w") as f:
        f.write(vl)

    if vals is None:
        vals = create_random(dut.num_rows, width, single_op, n_vals)

    test = MuxInOut(dut, width, fpkls, fpop, vals, single_op)
    fns = []
    for i in range(dut.num_rows):
        fns.append(test.rcv(i))
        fns.append(test.send(i))
    run_simulation(dut, fns, vcd_name="%s.vcd" % name)
