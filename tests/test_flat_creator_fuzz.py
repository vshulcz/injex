"""Equivalence fuzzing for the flat (compiled) resolve path.

For many randomly generated acyclic service graphs, the object graph produced by
``Container.resolve`` (which may use the flat exec-compiled creator) must be
structurally identical -- same classes, same instance-sharing pattern -- to an
independent reference resolver that interprets the same specification directly.

The reference resolver is deliberately simple and does not touch any Injex fast
path, so agreement is strong evidence the flat compiler preserves semantics for
singleton / transient / scoped / instance lifetimes, optional dependencies, and
defaulted parameters.
"""

import random

import pytest

from injex import Container

_LEAF = object()


def _fingerprint(obj, seen):
    """Canonical structure + identity-sharing signature of an object graph."""
    oid = id(obj)
    if oid in seen:
        return ("ref", seen[oid])
    seen[oid] = len(seen)
    deps = getattr(obj, "deps", _LEAF)
    if deps is _LEAF:
        return ("leaf", type(obj).__name__, repr(obj))
    return ("node", type(obj).__name__, tuple(_fingerprint(d, seen) for d in deps))


def _make_graph(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 8)

    # Dependencies only point to higher indices -> acyclic by construction.
    deps = []
    for i in range(n):
        candidates = list(range(i + 1, n))
        count = rng.randint(0, min(3, len(candidates)))
        deps.append(sorted(rng.sample(candidates, count)))

    lifestyles = []
    for _ in range(n):
        lifestyles.append(
            rng.choice(["transient", "singleton", "scoped", "instance", "transient"])
        )
    lifestyles[0] = "transient"  # transient root maximizes flat-path coverage
    for i in range(n):
        if lifestyles[i] == "instance":
            deps[i] = []  # prebuilt objects take no constructor dependencies

    classes = [type(f"N{seed}_{i}", (), {}) for i in range(n)]

    # An unregistered phantom type for optional / defaulted parameters.
    phantom = type(f"P{seed}", (), {})

    extras = []  # per node: list of ("opt",) / ("default", value)
    for i in range(n):
        node_extras = []
        if lifestyles[i] != "instance":
            if rng.random() < 0.3:
                node_extras.append(("opt",))
            if rng.random() < 0.3:
                node_extras.append(("default", rng.randint(0, 999)))
        extras.append(node_extras)

    for i in range(n):
        resolved = deps[i]
        params = [f"a{j}" for j in range(len(resolved))]
        annotations = {f"a{j}": classes[resolved[j]] for j in range(len(resolved))}
        tail = []
        for kind in extras[i]:
            if kind[0] == "opt":
                name = f"o{len(params) + len(tail)}"
                params.append(name)
                annotations[name] = phantom | None
            else:
                name = f"k{len(params) + len(tail)}"
                params.append(f"{name}={kind[1]!r}")
                annotations[name] = phantom
            tail.append(name)

        all_names = [p.split("=")[0] for p in params]
        body = "self.deps = ({})".format(
            "".join(f"{name}, " for name in all_names) or ""
        )
        src = "def __init__(self{}{}):\n    {}\n".format(
            ", " if params else "", ", ".join(params), body
        )
        local = {}
        exec(src, {}, local)
        init = local["__init__"]
        init.__annotations__ = annotations
        classes[i].__init__ = init

    instance_objs = {}
    container = Container()
    for i in range(n):
        ls = lifestyles[i]
        if ls == "instance":
            obj = classes[i]()
            instance_objs[i] = obj
            container.add_instance(classes[i], obj)
        elif ls == "singleton":
            container.add_singleton(classes[i])
        elif ls == "scoped":
            container.add_scoped(classes[i])
        else:
            container.add_transient(classes[i])

    def reference(i, singletons, scoped, defaults):
        ls = lifestyles[i]
        if ls == "instance":
            return instance_objs[i]
        if ls == "singleton" and i in singletons:
            return singletons[i]
        if ls == "scoped" and i in scoped:
            return scoped[i]
        args = [reference(d, singletons, scoped, defaults) for d in deps[i]]
        for kind in extras[i]:
            args.append(None if kind[0] == "opt" else kind[1])
        obj = classes[i](*args)
        if ls == "singleton":
            singletons[i] = obj
        elif ls == "scoped":
            scoped[i] = obj
        return obj

    return container, classes, lambda: reference(0, {}, {}, {})


def test_flat_creator_matches_reference_resolver():
    flat_used = 0
    for seed in range(600):
        container, classes, ref = _make_graph(seed)
        got = container.resolve(classes[0])
        expected = ref()
        assert _fingerprint(got, {}) == _fingerprint(expected, {}), f"seed {seed}"

        creator = container._registrations[(classes[0], None)][0].fast_creator
        if creator is not None and getattr(creator, "__name__", "") == "_flat":
            flat_used += 1

    # The fuzzer must actually exercise the compiled flat path, not only fallbacks.
    assert flat_used > 50, f"flat path barely used ({flat_used})"


def test_flat_creator_singletons_are_shared_and_transients_are_fresh():
    class Settings:
        pass

    class ApiClient:
        def __init__(self, settings: Settings):
            self.settings = settings

    class Repo:
        def __init__(self, client: ApiClient):
            self.client = client

    class Service:
        def __init__(self, a: Repo, b: Repo, client: ApiClient):
            self.a, self.b, self.client = a, b, client

    c = Container()
    c.add_instance(Settings, Settings())
    c.add_singleton(ApiClient)
    c.add_transient(Repo)
    c.add_transient(Service)
    c.assert_valid()

    s = c.resolve(Service)
    # Confirm the flat compiler is the active creator for this shape.
    assert c._registrations[(Service, None)][0].fast_creator.__name__ == "_flat"
    # Singleton (and the instance it holds) shared everywhere:
    assert s.a.client is s.b.client is s.client
    assert s.client.settings is s.a.client.settings
    # Transient Repo distinct per injection site:
    assert s.a is not s.b


def test_flat_creator_declines_factory_dependency():
    class Config:
        pass

    class Service:
        def __init__(self, config: Config):
            self.config = config

    c = Container()
    c.add_transient_factory(Config, lambda: Config())
    c.add_transient(Service)

    # A factory dependency is not flat-eligible; the graph must fall back and
    # still resolve correctly.
    assert c.resolve(Service).config.__class__ is Config
    assert c._registrations[(Service, None)][0].fast_creator is None


def test_flat_creator_declines_container_injection():
    class Service:
        def __init__(self, container):
            self.container = container

    c = Container()
    c.add_transient(Service)

    resolved = c.resolve(Service)
    assert resolved.container is c
    assert c._registrations[(Service, None)][0].fast_creator is None


def test_flat_creator_declines_property_injection():
    from injex import inject

    class Dep:
        pass

    class Service:
        @inject
        def dep(self) -> Dep:  # property injection; body never runs
            return Dep()

    c = Container()
    c.add_singleton(Dep)
    c.add_transient(Service)

    resolved = c.resolve(Service)
    assert isinstance(resolved.dep, Dep)
    assert c._registrations[(Service, None)][0].fast_creator is None


def test_constructor_injection_works_with_slots_and_frozen():
    import dataclasses

    class Settings:
        pass

    class Client:
        __slots__ = ("settings",)

        def __init__(self, settings: Settings):
            self.settings = settings

    @dataclasses.dataclass(frozen=True)
    class Service:
        client: Client

    c = Container()
    c.add_instance(Settings, Settings())
    c.add_singleton(Client)  # __slots__ class
    c.add_transient(Service)  # frozen dataclass

    s = c.resolve(Service)
    assert isinstance(s.client, Client)
    # Constructor injection must still take the compiled flat path here.
    assert c._registrations[(Service, None)][0].fast_creator.__name__ == "_flat"


def test_property_injection_on_frozen_or_slots_raises_clear_error():
    import dataclasses

    from injex import PropertyInjectionException, inject

    class Dep:
        pass

    @dataclasses.dataclass(frozen=True)
    class FrozenService:
        @inject
        def dep(self) -> Dep:
            return Dep()

    c = Container()
    c.add_singleton(Dep)
    c.add_transient(FrozenService)
    with pytest.raises(PropertyInjectionException):
        c.resolve(FrozenService)

    class SlotsService:
        __slots__ = ()

        @inject
        def dep(self) -> Dep:
            return Dep()

    c2 = Container()
    c2.add_singleton(Dep)
    c2.add_transient(SlotsService)
    with pytest.raises(PropertyInjectionException):
        c2.resolve(SlotsService)
