"""Equivalence + lifecycle fuzzing for the async resolution path.

Part A reuses the sync fuzzer's random-graph generator and its independent
reference resolver: for graphs with no async nodes, the async path must produce
the same object graph (same classes, same sharing) as the reference. Since the
sync path is already fuzz-verified, this pins the async interpreted path to it.

Part B generates graphs that include async-generator resources and asserts the
lifecycle invariants: every opened resource is closed exactly once, scoped
resources are reused within a scope and fresh across scopes, and nothing is
finalized before its scope exits.
"""

import asyncio
import random
from collections import Counter

from injex import Container

from tests.test_flat_creator_fuzz import _fingerprint, _make_graph


def _aresolve_in_scope(container, cls):
    async def go():
        async with container.ascope() as scope:
            return await scope.aresolve(cls)

    return asyncio.run(go())


def test_async_path_matches_reference_on_random_graphs():
    for seed in range(2000):
        container, classes, ref = _make_graph(seed)
        got = _aresolve_in_scope(container, classes[0])
        assert _fingerprint(got, {}) == _fingerprint(ref(), {}), f"seed {seed}"


def _build_resource_graph(seed):
    """Random acyclic graph whose leaves may be async-generator resources.

    Returns (container, root_cls, events). ``events`` records (i, 'open'|'close').
    """
    rng = random.Random(seed)
    n = rng.randint(2, 7)
    deps = []
    for i in range(n):
        candidates = list(range(i + 1, n))
        k = rng.randint(0, min(2, len(candidates)))
        deps.append(sorted(rng.sample(candidates, k)))

    # Leaf nodes (no deps) may become async resources; others are sync classes
    # with one of the lifestyles.
    kinds = []
    lifestyles = []
    for i in range(n):
        if not deps[i] and rng.random() < 0.6:
            kinds.append("resource")
            lifestyles.append(rng.choice(["scoped", "singleton"]))
        else:
            kinds.append("class")
            lifestyles.append(rng.choice(["transient", "scoped", "singleton"]))

    classes = [type(f"R{seed}_{i}", (), {}) for i in range(n)]
    events = []
    container = Container()

    for i in range(n):
        d = deps[i]
        if kinds[i] == "class":
            params = [f"a{j}" for j in range(len(d))]
            ann = {f"a{j}": classes[d[j]] for j in range(len(d))}
            body = "self.deps = ({})".format("".join(f"{p}, " for p in params))
            src = "def __init__(self{}{}):\n    {}\n".format(
                ", " if params else "", ", ".join(params), body
            )
            ns = {}
            exec(src, {}, ns)
            init = ns["__init__"]
            init.__annotations__ = ann
            classes[i].__init__ = init
            reg = {
                "transient": container.add_transient,
                "scoped": container.add_scoped,
                "singleton": container.add_singleton,
            }[lifestyles[i]]
            reg(classes[i])
        else:
            # async-generator resource leaf (no deps), records open/close.
            # Capture cls/idx via a closure (not parameters, which Injex would
            # try to inject as dependencies).
            def make_res(cls, idx):
                async def res():
                    obj = cls()
                    obj.deps = ()
                    events.append((idx, "open"))
                    try:
                        yield obj
                    finally:
                        events.append((idx, "close"))

                return res

            (
                container.add_singleton_factory
                if lifestyles[i] == "singleton"
                else container.add_scoped_factory
            )(classes[i], make_res(classes[i], i))

    return container, classes[0], events, kinds, lifestyles


def test_async_resource_lifecycle_invariants():
    # Each seed runs in a single event loop: a singleton async resource must
    # outlive the scope and be finalized only by aclose(), which requires the
    # loop to stay alive across resolve + aclose (asyncio.run() finalizes
    # suspended async generators on loop shutdown).
    async def check(seed):
        container, root, events, kinds, lifestyles = _build_resource_graph(seed)
        singleton_res = {
            i
            for i in range(len(kinds))
            if kinds[i] == "resource" and lifestyles[i] == "singleton"
        }

        async with container.ascope() as scope:
            await scope.aresolve(root)
            assert all(k == "open" for _, k in events), f"seed {seed} early close"

        opened = {i for i, k in events if k == "open"}
        closed_after_scope = {i for i, k in events if k == "close"}
        # scoped/transient resources closed on scope exit; singletons not yet
        assert (opened - singleton_res) <= closed_after_scope, f"seed {seed}"
        assert not (singleton_res & closed_after_scope), f"seed {seed} singleton early"

        await container.aclose()

        closes = Counter(i for i, k in events if k == "close")
        for i in opened:
            assert closes[i] == 1, f"seed {seed} node {i} closed {closes[i]}x"
        assert set(closes) == opened, f"seed {seed} closed set mismatch"

    for seed in range(1500):
        asyncio.run(check(seed))


def test_scoped_resource_fresh_across_scopes_reused_within():
    events = []

    async def res():
        obj = object()
        events.append(("open", id(obj)))
        try:
            yield obj
        finally:
            events.append(("close", id(obj)))

    async def main():
        c = Container()
        c.add_scoped_factory(object, res)
        async with c.ascope() as s1:
            a1 = await s1.aresolve(object)
            a2 = await s1.aresolve(object)
            assert a1 is a2  # reused within scope
        async with c.ascope() as s2:
            b = await s2.aresolve(object)
            assert b is not a1  # fresh across scopes
        opens = [e for e in events if e[0] == "open"]
        closes = [e for e in events if e[0] == "close"]
        assert len(opens) == 2 and len(closes) == 2

    asyncio.run(main())
