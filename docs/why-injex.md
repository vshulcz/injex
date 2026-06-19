# Why Injex

## Is dependency injection even Pythonic?

Passing collaborators into a constructor is just `__init__(self, repo, mailer)` —
plain Python, no magic. The only thing a container adds is *automating the wiring*
and *checking it*. Injex does that from your existing type hints, with no decorators,
no global state, and no import-time side effects. The wiring is just your
registration list plus plain constructor annotations — nothing hidden to trace.

So Injex isn't trying to make Python feel like Java. It's trying to remove one
specific kind of busywork: hand-wiring the same object graph in several places and
keeping those copies in sync.

## The niche

Python doesn't need a DI container for small programs — plain functions and manual
wiring are better there. Injex is for the next step: when the same graph leaks into
an API, a CLI, workers, and tests, and you want it validated before startup.

It's intentionally small:

- no runtime dependencies;
- no provider DSL and no required decorators;
- no framework lock-in — normal type hints are the wiring contract;
- a compiled, cached fast path for repeated resolves.

The goal isn't to replace every Python DI library — it's to cover the common service
/ CLI / worker / clean-architecture case well, and nothing more.

## Design principle

Injex should stay boring in production: explicit registrations, predictable lifetime
rules, readable errors, and no hidden runtime dependencies. The one thing it does
that most small containers don't is **validate the whole graph without constructing
anything**, so wiring mistakes fail at startup instead of in production.

## Deciding when to use it

For the concrete decision — manual wiring vs. a framework's DI vs. Injex vs. a larger
container — see the [comparison guide](./comparison.md), and
[Injex vs FastAPI Depends](./fastapi-depends.md) for the web-boundary case.
