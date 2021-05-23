#!/usr/bin/env python3

from __future__ import annotations
from nmigen import *

# Bad hack :(
del Module.__init_subclass__

class ModuleWrapper(Module):
    def __init__(self):
        super().__init__()
        self.submodules = []


class Element:
    m: ModuleWrapper
    
    def create(self, context):
        ...

    def finalize(self, context):
        ...


class Ila(Element):
    def __init__(self, *, child):
        self.child = child
        self.probes = []

    def create(self, context):
        self.m.submodules += [self.child]

    def finalize(self, context):
        for probe in self.probes:
            probe_storage = Signal(10)
            self.m.d.sync += probe_storage.eq(Cat(probe, probe_storage))

    def add_probe(self, signal):
        self.probes.append(signal)


class Test(Element):
    def create(self, context):
        a = Signal()
        b = Signal()

        context.find(Ila).add_probe(a)
        context.find(Ila).add_probe(b)

        self.m.d.sync += a.eq(b)

    def finalize(self, context):
        c = Signal(10)
        self.m.d.sync += c.eq(c + 1)


class ElaborationContext:
    def __init__(self, element: Element, parent: ElaborationContext = None):
        self.parent = parent
        self.element = element

    def find(self, cls):
        val = self
        while (parent := self.parent) != None:
            if isinstance(val.element, cls):
                return val.element
            val = parent


def element_to_module(element: Element, parent: ElaborationContext = None) -> Module:
    context = ElaborationContext(element, parent = parent)

    module = ModuleWrapper()
    element.m = module
    element.create(context)

    for submodule in module.submodules:
        module._add_submodule(element_to_module(submodule, parent = context))

    element.finalize(context)
    return module
        
from nmigen.back.verilog import convert

print(convert(element_to_module(Ila(child = Test()))))
