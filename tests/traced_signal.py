#!/usr/bin/env python3

from __future__ import annotations
from amigen import *
from nmigen import tracer

def test_context_lookup_elaboration_order():
    class TracedSignal(Signal):
        def __init__(self, name = None, *args, **kwargs):
            super().__init__(*args, **kwargs)

            if name is None:
                try:
                    name = tracer.get_var_name()
                except tracer.NameNotFound:
                    raise ValueError("Clock domain name must be specified explicitly")

            self.name = name

            GlobalElaborationContext.with_context(self._on_context)

        def _on_context(self, context):
            self.path = "/".join(reversed([self.name] + list(context.path())))
            context.find(TracedSignalCollector).add_signal(self)

    class TracedSignalCollector(Element):
        def __init__(self, child: Element):
            self.child = child
            self.signals = {}

        def create(self, context):
            self.m.submodules += self.child

        def add_signal(self, signal: TracedSignal):
            self.signals[signal.path] = signal


    class A(Element):
        def __init__(self):
            print("init A")
            self.a_signal_in_init = TracedSignal()
            self.c = C()

        def create(self, context):
            print("creating A")
            self.m.submodules += B()
            a_signal_in_create = TracedSignal()

        def finalize(self, context):
            print("finalizing A")
            self.m.submodules += B(self.c)
            a_signal_in_finalize = TracedSignal()

    class B(Element):
        def __init__(self, child = None):
            print("init B")
            self.b_signal_in_init = TracedSignal()
            self.child = child

        def create(self, context):
            print("creating B")
            b_signal_in_create = TracedSignal()

        def finalize(self, context):
            print("finalizing B")
            b_signal_in_finalize = TracedSignal()
            if self.child != None:
                self.m.submodules += self.child

    class C(Element):
        def __init__(self):
            print("init C")
            self.c_signal_in_init = TracedSignal()

        def create(self, context):
            print("creating C")
            c_signal_in_create = TracedSignal()

        def finalize(self, context):
            print("finalizing C")
            c_signal_in_finalize = TracedSignal()


    top = TracedSignalCollector(A())
    element_to_module(top)

    for signal in ['top/A#0/a_signal_in_init'
    , 'top/A#0/a_signal_in_create'
    , 'top/A#0/a_signal_in_finalize'
    , 'top/A#0/B#0/b_signal_in_init'
    , 'top/A#0/B#0/b_signal_in_create'
    , 'top/A#0/B#0/b_signal_in_finalize'
    , 'top/A#0/B#1/b_signal_in_init'
    , 'top/A#0/B#1/b_signal_in_create'
    , 'top/A#0/B#1/b_signal_in_finalize'
    , 'top/A#0/B#1/C#0/c_signal_in_init'
    , 'top/A#0/B#1/C#0/c_signal_in_create'
    , 'top/A#0/B#1/C#0/c_signal_in_finalize'
    ]:
        assert signal in top.signals
