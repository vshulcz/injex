"""Thread-safety of the sync resolve path.

Two properties are pinned here: the interpreted path's cycle guard is per-thread
(it used to share one in-progress set and raise spurious cycle errors), and a
singleton is constructed exactly once even when threads first resolve it together.
"""

import threading
import time

from injex import Container, inject


def test_no_false_cycles_under_concurrent_interpreted_resolve():
    class Dep:
        pass

    class Service:
        @inject
        def dep(self) -> Dep:  # property injection -> interpreted path
            return Dep()

    c = Container()
    c.add_singleton(Dep)
    c.add_transient(Service)
    c.resolve(Service)  # warm

    errors: list[str] = []

    def worker() -> None:
        for _ in range(5000):
            try:
                c.resolve(Service)
            except Exception as exc:
                errors.append(type(exc).__name__)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"{len(errors)} spurious errors: {set(errors)}"


def test_singleton_built_once_under_concurrent_first_resolve():
    builds = []
    builds_lock = threading.Lock()

    class Settings:
        pass

    class Pool:
        def __init__(self, settings: Settings):
            with builds_lock:
                builds.append(1)
            time.sleep(0.002)  # widen the race window

    c = Container()
    c.add_singleton(Settings)
    c.add_singleton(Pool)  # depends on another singleton: exercises reentrancy

    barrier = threading.Barrier(16)
    seen: list[int] = []

    def worker() -> None:
        barrier.wait()  # all threads hit the cold cache together
        seen.append(id(c.resolve(Pool)))

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(builds) == 1, f"singleton built {sum(builds)} times"
    assert len(set(seen)) == 1, "threads received different singleton instances"
