""" key strategic example showing how to do multi-input fan-in into a
    multi-stage pipeline, then multi-output fanout.

    the multiplex ID from the fan-in is passed in to the pipeline, preserved,
    and used as a routing ID on the fanout.
"""

from random import randint
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil


class InputTest:
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


class InputTestRandom(InputTest):
    def __init__(self, dut, width, fpkls, fpop, single_op=False, n_vals=10):
        vals = []
        for muxid in range(dut.num_rows):
            for i in range(n_vals):
                if single_op:
                    op1 = randint(0, (1<<width)-1)
                    #op1 = 0x40900000
                    #op1 = 0x94607b66
                    #op1 = 0x889cd8c
                    #op1 = 0xe98646d7
                    #op1 = 0x3340f2a7
                    #op1 = 0xfff13f05
                    #op1 = 0xc53eb000
                    #op1 = 0x3a05de50
                    #op1 = 0xc27ff989
                    vals.append((op1,))
                else:
                    op1 = randint(0, (1<<width)-1)
                    op2 = randint(0, (1<<width)-1)
                    vals.append((op1, op2,))

        InputTest.__init__(self, dut, width, fpkls, fpop, vals, single_op)


def runfp(dut, width, name, fpkls, fpop, single_op=False, n_vals=10):
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("%s.il" % name, "w") as f:
        f.write(vl)

    test = InputTestRandom(dut, width, fpkls, fpop, single_op, n_vals)
    run_simulation(dut, [test.rcv(1), test.rcv(0),
                         test.rcv(3), test.rcv(2),
                         test.send(0), test.send(1),
                         test.send(3), test.send(2),
                        ],
                   vcd_name="%s.vcd" % name)

