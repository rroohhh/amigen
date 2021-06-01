#!/usr/bin/env python3

from amigen import *

def test_class_hooks():
    class DriverMethodCollector(Element):
        def __init__(self, child):
            self.child = child
            self.functions = {}

        def create(self, context):
            self.m.submodules += self.child()
            self.m.submodules += self.child()

        def add_method(self, path, method):
            path = "/".join(reversed([method.__name__] + path))
            self.functions[path] = method

    class driver_method:
        def __init__(self, func):
            self.func = func

        def __set_name__(self, owner, name):
            def add_driver_method(context):
                context.find(DriverMethodCollector).add_method(list(context.path()), self.func)

            owner.add_class_context_hook(add_driver_method)

    class A(Element):
        @driver_method
        def test(self):
            pass

        @driver_method
        def test2(self):
            pass

    top = DriverMethodCollector(child = A)        
    element_to_module(top)


    assert top.functions["top/A#0/test"] == A.test.func
    assert top.functions["top/A#0/test2"] == A.test2.func

    assert top.functions["top/A#1/test"] == A.test.func
    assert top.functions["top/A#1/test2"] == A.test2.func
