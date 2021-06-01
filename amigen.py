#!/usr/bin/env python3

from __future__ import annotations
from contextlib import contextmanager
from nmigen import Module, Signal, Value, Cat, ClockDomain, Fragment, DomainRenamer
from nmigen.build import Platform
import warnings
import nmigen
from typing import Any, Iterable
from collections import defaultdict
import functools

__all__ = [
    'GlobalKey',
    'Key',
    'Element',
    'ElaborationContext',
    'GlobalElaborationContext',
    'Signal',
    'Value',
    'Cat',
    'ClockDomain',
    'DomainMapper',
    'ClockSignal',
    'ResetSignal',
    'element_to_module'
]

def ClockSignal(name = "sync"):
    assert GlobalElaborationContext.current_element is None, "cannot use ClockSignal in __init__ of a Element"

    domains = GlobalElaborationContext.current_context.domains
    if name in domains:
        return domains[name].clk
    else:
        raise ValueError(f"domain with name {name} not found")

def ResetSignal(name = "sync"):
    assert GlobalElaborationContext.current_element is None, "cannot use ResetSignal in __init__ of a Element"

    domains = GlobalElaborationContext.current_context.domains
    if name in domains:
        if (rst := domains[name].rst) is None:
            raise ValueError(f"trying to get reset signal of resetless domain {name}")
        return rst
    else:
        raise ValueError(f"domain with name {name} not found")

# A key uniquely identifies a element in the element tree
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

# Bad hack :(
del Module.__init_subclass__

class SubmoduleBuilder:
    def __init__(self):
        object.__setattr__(self, "_storage", {})

    def __setattr__(self, name: str, value: Element) -> None:
        if name in self._storage:
            raise ValueError(f"duplicate submodule with name {name}")
        else:
            if isinstance(value, Element) and value.name != name and value.name != None:
                raise ValueError(f"submodule name {name} and element name {value.name} have to agree")
            self._storage[name] = value

    def __getattr__(self, name: str) -> Any:
        return self._storage[name]

    def __setitem__(self, name: str, value: Element):
        setattr(self, name, value)

    def __getitem__(self, key: str):
        return self._storage[key]

    def __iadd__(self, value: Element):
        if isinstance(value, Element) and value.name != None:
            self[value.name] = value
        else:
            num = 0
            cls_name = value.__class__.__name__

            while (name := f"{cls_name}#{num}") in self._storage:
                num += 1

            self._storage[name] = value
        return self

    def __iter__(self):
        return iter(self._storage.items())

class DomainSetBuilder:
    def __init__(self, element: Element, top_for_nmigen: bool):
        object.__setattr__(self, "_element", element)
        object.__setattr__(self, "_top_for_nmigen", top_for_nmigen)

    def __iadd__(self, domain):
        if not isinstance(domain, ClockDomain):
            raise TypeError("Only clock domains may be added to `m.domains`, not {!r}"
                            .format(domain))

        domain_prefix = "_internal_" + "/".join(reversed(list(self._element.context.path()))) + "_"
        domain_name = domain_prefix + domain.name

        if domain_name in self._element.context.domains:
            raise NameError("Clock domain named '{}' already exists".format(domain.name))

        assert domain.local == False, "in amigen the local parameter is ignored and the clock domain is always local"
        module_local_domain = ClockDomain(name = domain_name, clk_edge=domain.clk_edge, reset_less=domain.rst is None, async_reset=domain.async_reset, local=True)
        self._element.m._add_domain(module_local_domain)

        if self._top_for_nmigen:
            domain.local = True

            self._element.m.d.comb += module_local_domain.clk.eq(nmigen.ClockSignal(domain.name))
            if not domain.rst is None:
                self._element.m.d.comb += module_local_domain.rst.eq(nmigen.ResetSignal(domain.name))

        self._element.context.domains[domain.name] = module_local_domain

        return self

    def __setattr__(self, name, domain):
        if domain.name != name:
            raise NameError("Clock domain name {!r} must match name in `m.domains.{} += ...` "
                            "syntax"
                            .format(domain.name, name))
        self += domain

class ModuleWrapper(Module):
    def __init__(self, element, top):
        super().__init__()
        self.submodules = SubmoduleBuilder()
        self.domains = DomainSetBuilder(element, top)

class ElementMeta(type):
    def __call__(cls, *args, key = None, name = None, **kwargs):
        element = cls.__new__(cls)

        old_element = GlobalElaborationContext.current_element
        GlobalElaborationContext.current_element = element

        element.key = key
        element.name = name
        element.on_context_available = []
        element.domain_map = {}
        element.__init__(*args, **kwargs)

        old_create = element.create
        @functools.wraps(old_create)
        def patched_create(self, context):
            for hook in self.on_context_available:
                hook(context)

            if hasattr(self, "cls_on_context_available"):
                for hook in self.cls_on_context_available:
                    hook(context)

            old_create(context)
            

        import types
        element.create = types.MethodType(patched_create, element)

        GlobalElaborationContext.current_element = old_element

        return element

# A element replaces the role of a Elaboratable in amigen
# Each element goes through three phases
# 1. __init__ phase. During this time the position of the Element in the Element tree is not yet known. Because of that there is also no `context` available.
#    Nonetheless it is possible to register functions that will be executed as soon as the position in the Element tree is known / a `context` is available.
# 2. create phase. The create phase happens after the position in the Element tree is known. Here a first set of statements and submodules is added. The submodules that are added then have access to the current Element via their respective `context.parent`.
# 3. finalize phase. After the create and finalize phase of each submodule added in the create phase, the finalize phase of a Element takes place, where final statements and submodules can be added. The submodules added in in this phase however have no access to the current Element.
class Element(metaclass = ElementMeta):
    m: ModuleWrapper 
    # a name, used to name this element in the Element tree, alternative to specifiying the name when adding as a submodule (self.submodule.name = ...)
    name: str
    key: Key | None 
    # the context / position in the Element tree, as soon as we are added to the hierarchy
    context: ElaborationContext | None
    # a list of hooks to run as soon as we get added to the Element tree
    on_context_available: list 
    # a list of hooks to run as soon as we get added to the Element tree, defined by the class not the instance
    cls_on_context_available: list
    # a way to rename clock domains, maps the submodule clock domain name, to the name used by the parent. Usually not set directly but instead by using DomainMapper.
    # applies recursively downwards
    domain_map: dict[str, str]

    @classmethod
    def add_class_context_hook(cls, hook):
        if not hasattr(cls, "cls_on_context_available"):
            cls.cls_on_context_available = []

        cls.cls_on_context_available.append(hook)

    def create(self, context):
        ...

    def finalize(self, context):
        ...

    def elaborate(self, platform):
        warnings.warn("elaborate called on Element. While this is supported, this might lead to unexpected behaviour.")
        return element_to_module(self, top_name=f"{self.__class__.__name__}", for_nmigen=True, platform = platform)

class DomainMapper:
    def __init__(self, map):
        if isinstance(map, str):
            map = { "sync" : map }
        self.map = map

    def __call__(self, element: Element):
        # TODO(robin): is this the behaviour we want?
        element.domain_map.update(self.map)
        return element
        

class ElaborationContext:
    # true if this context is visible. During the `create(self, context)` phase, context is visible, during `finalize` it is not visible
    visible: bool
    # points to the parent context, or null if the root is reached
    parent: ElaborationContext | None
    # point to the element this context belongs to
    element: Element
    # maps name to a ClockDomain object
    domains: dict[str, ClockDomain]
    platform: Platform

    def __init__(self, element: Element, platform: Platform, domains: dict[str, ClockDomain], parent: ElaborationContext = None, visible = True):
        self.visible = visible
        self.parent = parent
        self.element = element
        self.domains = domains
        self.platform = platform

    def _copy_invisible(self) -> ElaborationContext:
        return ElaborationContext(self.element, self.platform, self.domains, self.parent, False)

    def find(self, cls):
        val = self
        while (val := val.parent) != None:
            if isinstance(val.element, cls) and val.visible:
                return val.element

    def find_by_key(self, key: Key):
        val = self
        while (val := val.parent) != None:
            if val.element.key == key and val.visible:
                return val.element

    def path(self) -> Iterable[str]:
        val = self

        yield val.element.name

        while (val := val.parent) != None:
            yield val.element.name

class GlobalElaborationContext:
    current_context: ElaborationContext | None = None
    current_element: Element | None = None

    @staticmethod
    def with_context(func):
        # We are in some __init__ of some Element
        if GlobalElaborationContext.current_element != None:
            GlobalElaborationContext.current_element.on_context_available.append(func)
        else:
            func(GlobalElaborationContext.current_context)  
            
    @staticmethod
    @contextmanager
    def context_for(*, element: Element, parent: ElaborationContext, domains: dict[str, ClockDomain], platform: Platform):
        context = ElaborationContext(element, platform, domains.copy(), parent)
        element.context = context
        old_context = GlobalElaborationContext.current_context
        GlobalElaborationContext.current_context = context

        try:
            yield context
        finally:
            GlobalElaborationContext.current_context = old_context

def element_to_module(element: Element, platform = None, top_name = "top", for_nmigen = False) -> Module:
    def element_to_module_inner(element: Element, top = False, domains = {}, parent: ElaborationContext = None) -> Module:
        with GlobalElaborationContext.context_for(element = element, parent = parent, domains = domains, platform = platform) as context:
            module = ModuleWrapper(element, top and for_nmigen)
            element.m = module

            done_submodules = set()

            # create phase, add the first set of statements and submodules
            element.create(context)
            # assert that we have no hanging control flow
            assert module.domain._depth == 0

            # add the default sync domain
            if top and len(context.domains) == 0:
                module.domains += ClockDomain("sync")

            def add_submodule(name, submodule, context):
                if isinstance(submodule, Element):
                    if submodule.name == None:
                        submodule.name = name

                    domains_for_submodule = {}
                    domain_map_inverse = defaultdict(list)

                    for submodule_name, parent_name in submodule.domain_map.items():
                        domain_map_inverse[parent_name].append(submodule_name)

                    for domain_name, domain in context.domains.items():
                        if domain_name in domain_map_inverse:
                            for submodule_name in domain_map_inverse[domain_name]:
                                domains_for_submodule[submodule_name] = domain
                        else:
                            domains_for_submodule[domain_name] = domain

                    module._add_submodule(element_to_module_inner(submodule, parent = context, domains = domains_for_submodule), name)
                elif hasattr(submodule, "elaborate") or isinstance(submodule, Fragment):
                    done_submodules.add(submodule)

                    domain_mapping_dict = { domain_name : domain.name for domain_name, domain in context.domains.items() }

                    module._add_submodule(DomainRenamer(domain_mapping_dict)(submodule), name)
                else:
                    raise ValueError(f"don't know what to do with submodule {name} = {submodule}")

            for name, submodule in module.submodules:
                add_submodule(name, submodule, context)


            element.finalize(context)
            assert module.domain._depth == 0

            # translate the drivers from the names used in the module to the names of the actual clock domains
            for sig, name in module._driving.items():
                if name is not None:
                    if name not in context.domains:
                        raise ValueError(f"{sig} driven by unknown domain {name} in module {'/'.join(reversed(list(context.path())))}")
                    else:
                        actual_name = context.domains[name].name
                        module._driving[sig] = actual_name

            for name, submodule in module.submodules:
                # only add submodules we did not already add after create
                if not hasattr(submodule, "m") and submodule not in done_submodules:
                    add_submodule(name, submodule, context._copy_invisible())

            return module

    if element.name == None:
        element.name = top_name

    return element_to_module_inner(element, top = True)
