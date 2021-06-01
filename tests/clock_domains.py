#!/usr/bin/env python3

from amigen import *
from nmigen import Fragment

def test_clock_domains():
    class A(Element):
        def create(self, context):
            self.m.domains += ClockDomain("a")
            self.m.domains += ClockDomain("b")

            a = self.a = Signal()
            b = self.b = Signal()
            c = self.c = Signal()
            d = self.d = Signal()

            self.m.d.a += a.eq(b)
            self.m.d.b += c.eq(d)

            self.m.submodules += DomainMapper("a")(B())

    class B(Element):
        def create(self, context):
            e = context.parent.element.e = Signal()
            f = context.parent.element.f = Signal()
            self.m.d.sync += e.eq(f)
            self.m.submodules += C()

    class C(Element):
        def create(self, context):
            h = context.parent.parent.element.h = Signal()
            i = context.parent.parent.element.i = Signal()
            j = context.parent.parent.element.j = Signal()
            k = context.parent.parent.element.k = Signal()

            self.m.domains += ClockDomain("a")
            self.m.d.sync += h.eq(i)

            context.parent.parent.element.clksignal_a = ClockSignal("a")
            context.parent.parent.element.clksignal_b = ClockSignal("b")
            context.parent.parent.element.clksignal_sync = ClockSignal("sync")

    top = A()
    mod = element_to_module(top)
    frag = Fragment.get(mod, None)

    assert '_internal_top_a' in frag.domains
    assert '_internal_top_b' in frag.domains

    assert top.a in frag.drivers['_internal_top_a']
    assert top.c in frag.drivers['_internal_top_b']

    subfrag = frag.subfragments[0][0]
    assert top.e in subfrag.drivers['_internal_top_a']

    subfrag = subfrag.subfragments[0][0]
    assert top.h in subfrag.drivers['_internal_top_a']

    assert id(top.clksignal_b) == id(frag.domains['_internal_top_b'].clk)
    assert id(top.clksignal_sync) == id(frag.domains['_internal_top_a'].clk)

    assert id(top.clksignal_a) == id(subfrag.domains['_internal_top/B#0/C#0_a'].clk)
