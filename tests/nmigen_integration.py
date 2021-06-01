#!/usr/bin/env python3

from amigen import *
from nmigen.back.verilog import convert
from nmigen import Memory, Elaboratable, Module, DomainRenamer, Fragment

def test_nmigen_integration():
    class B(Elaboratable):
        def elaborate(self, plat):
            m = Module()

            m.domains += ClockDomain("nmigen_clock_domain")
            m.domains += ClockDomain("nmigen_clock_domain2")

            nmigen_a = Signal()
            nmigen_b = Signal()

            m.d.nmigen_clock_domain += nmigen_a.eq(nmigen_b)

            m.submodules += DomainRenamer({"sync": "nmigen_clock_domain", "a": "nmigen_clock_domain2"})(A())

            return m


    class A(Element):
        def create(self, context):
            self.m.domains += ClockDomain("a")
            self.m.domains += ClockDomain("sync")

            assert context.platform == "the_platform"

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


    dut = B()
    frag = Fragment.get(dut, "the_platform")
    frag = frag.subfragments[0][0]
    statements = [repr(stmt) for stmt in frag.statements]
    assert "(eq (sig _internal_A_sync_clk) (clk nmigen_clock_domain))" in statements
    assert "(eq (sig _internal_A_sync_rst) (rst nmigen_clock_domain))" in statements
    assert "(eq (sig _internal_A_a_clk) (clk nmigen_clock_domain2))" in statements
    assert "(eq (sig _internal_A_a_rst) (rst nmigen_clock_domain2))" in statements
