#!/usr/bin/env python3

from amigen import *
from nmigen import Memory, Fragment

def test_nmigen_modules():
    class A(Element):
        def create(self, context):
            self.m.domains += ClockDomain("a")
            self.m.domains += ClockDomain("sync")

            a = Signal()
            b = Signal()
            self.m.d.sync += a.eq(b)


            memory = Memory(width=32, depth=32)

            out = Signal(32)

            read_port = self.m.submodules.read_port = memory.read_port(domain = "a")

            self.m.d.comb += out.eq(read_port.data)

            write_port = self.m.submodules.write_port = memory.write_port(domain = "sync")

            addr = Signal(32)
            data = Signal(32)
            self.m.d.comb += write_port.addr.eq(addr)
            self.m.d.comb += write_port.data.eq(data)
            self.m.d.comb += write_port.en.eq(1)


    dut = A()
    mod = element_to_module(dut)
    frag = Fragment.get(mod, None)

    # read port
    assert set(frag.subfragments[0][0].drivers.keys()) == set([None, "_internal_top_a"])
    # write port
    assert set(frag.subfragments[1][0].drivers.keys()) == set(["_internal_top_sync"])

