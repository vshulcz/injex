"""Thread-safety of the interpreted sync resolve path.

The compiled fast path never touches shared cycle-guard state, but property
injection / factory graphs fall to the interpreted path, which used to share a
single in-progress set across threads and produced spurious cycle errors. The
guard is now per-thread; this pins that down.
"""

import threading

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
