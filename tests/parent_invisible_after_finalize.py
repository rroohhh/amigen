#!/usr/bin/env python3
from amigen import *

def test_parent_invisible_after_finalize():
    class A(Element):
        def create(self, context):
            self.m.submodules += B()
        def finalize(self, context):
            self.m.submodules += C()

    class B(Element):
        def create(self, context):
            assert context.find(A) != None

        def finalize(self, context):
            assert context.find(A) != None

    class C(Element):
        def create(self, context):
            assert context.find(A) == None

        def finalize(self, context):
            assert context.find(A) == None

    top = A()
    element_to_module(top)
