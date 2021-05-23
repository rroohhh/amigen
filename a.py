#!/usr/bin/env python3

from __future__ import annotations
from nmigen import *

# Bad hack :(
del Module.__init_subclass__

class Key:
    value: object 

    def __eq__(self, other: Key) -> bool:
        if not isinstance(other, Key):
            return False
        else:
            return other.value == self.value
        

class GlobalKey(Key):
    __counter = 0
    def __init__(self):
        self.value = GlobalKey.__counter
        GlobalKey.__counter += 1

class ModuleWrapper(Module):
    def __init__(self):
        super().__init__()
        self.submodules = []

class ElementMeta(type):
    def __call__(cls, *args, key = None, **kwargs):
        obj = cls.__new__(cls)
        obj.__init__(*args, **kwargs)
        obj.key = key
        return obj

class Element(metaclass = ElementMeta):
    m: ModuleWrapper
    key: Key
    
    def create(self, context):
        ...

    def finalize(self, context):
        ...

    def elaborate(self, platform):
        raise RuntimeError("elaborate called on Element. This either means you did not convert the Element to a Module before passing it to nmigen or you used a Element as a submodule of a nmigen Module, this is currently not supported")


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

    def add_probe(self: Ila | Value, signal: Value = None):
        if (signal is None and not isinstance(self, Ila)):
            GlobalElaborationContext.current_context.find(Ila).add_probe(self)
        else:    
            self.probes.append(signal)


class Test(Element):
    def create(self, context):
        a = Signal()
        b = Signal()

        Ila.add_probe(a)
        context.find_by_key(ila_key).add_probe(b)

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
        while (val := val.parent) != None:
            if isinstance(val.element, cls):
                return val.element

    def find_by_key(self, key: Key):
        val = self
        while (val := val.parent) != None:
            if val.element.key == key:
                return val.element


class GlobalElaborationContext:
    current_context: ElaborationContext


def element_to_module(element: Element, parent: ElaborationContext = None) -> Module:
    context = ElaborationContext(element, parent = parent)
    GlobalElaborationContext.current_context = context

    module = ModuleWrapper()
    element.m = module
    element.create(context)

    for submodule in module.submodules:
        module._add_submodule(element_to_module(submodule, parent = context))

    element.finalize(context)
    return module
        
from nmigen.back.verilog import convert

ila_key = GlobalKey()
print(
    convert(
        element_to_module(
            Ila(
                key = ila_key,
                child = Ila(
                    child = Test()
                )
            )
        )
    )
)
