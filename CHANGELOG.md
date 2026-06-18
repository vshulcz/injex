# Changelog

All notable changes to Injex are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning.

## [Unreleased]

## [1.5.0] - 2026-06-19

### Changed

- Compiled async resolution. `aresolve()` now compiles a flat `async` creator
  that inlines the synchronous parts of a graph and awaits only the genuinely
  async nodes, instead of walking the graph with a coroutine per node:
  - a graph with no async factories reuses the synchronous compiled creator and
    drops from `~5.1 µs/op` to `~0.44 µs/op` (on par with sync `resolve()`) — the
    common FastAPI shape of awaiting `aresolve()` on plain classes;
  - a graph with an `async def` factory drops from `~3.0 µs/op` to `~1.2 µs/op`
    on the project benchmark.

  See `benchmarks/resolve_async.py` for a reproducible cross-library comparison.
  Async resources keep their LIFO finalization semantics; graphs that can't be
  flattened fall back to the previous interpreted async walk.

### Added

- Typed `resolve()` / `resolve_all()` / `aresolve()` via `@overload`: passing a
  type now infers that type (`resolve(Foo) -> Foo`, `resolve_all(Foo) -> list[Foo]`)
  instead of `Any`, so resolved services stay type-checked at the call site. A
  string interface still falls back to `Any`.
- `aresolve()` on the container raises a clear error when asked to resolve a
  scoped/transient async resource directly (which it would finalize immediately),
  pointing at `async with container.ascope()`.
- Docstrings on the public registration and scope methods.
- Async resolution, sync-first and still zero-dependency. `await container.aresolve(T)`
  and `async with container.ascope() as scope: await scope.aresolve(T)` await
  `async def` factories and manage async resources: register an async-generator
  factory (`async def f(...): ...; yield x; await cleanup()`) and the yielded value
  is finalized when its scope exits (scoped/transient) or on `await container.aclose()`
  (singleton), via a stdlib `AsyncExitStack`. The sync `resolve()` raises a clear
  `AsyncResolutionRequiredException` if the graph needs async work. Cycle detection
  on the async path uses a per-resolution guard (safe under concurrent resolves).
  The synchronous fast path is untouched — same compiled creators, same ~0.4 µs/op.
- `PropertyInjectionException` with a clear message when property injection
  (`@inject` methods) targets a `__slots__` type or a frozen dataclass, instead
  of a raw `AttributeError` / `FrozenInstanceError`. Constructor injection into
  such types already worked (the compiled path calls the constructor directly and
  never sets attributes) and is unaffected; the hot path is untouched.

## [1.4.0] - 2026-06-12

### Changed

- Faster hot-path resolution, from `0.818 µs/op` to `0.401 µs/op` on the project
  benchmark (same machine and graph, roughly halved), via three changes:
  - the fast resolve path no longer pays a per-resolve cycle guard. A compiled
    fast creator is only built when the whole subgraph is statically proven
    acyclic and fully registered, so the runtime `cls in resolving` check could
    never fire there;
  - `resolve()` now dispatches through a direct `interface -> creator` cache for
    the common unnamed, no-scope case, skipping the per-call key-tuple allocation
    and registration attribute reads;
  - transient service graphs are compiled to a single flat creator that inlines
    the constructor spine and computes each shared singleton/instance once
    (common-subexpression elimination), removing the per-resolve closure call for
    every intermediate transient. Singleton, scoped, and instance leaves reuse the
    existing creators, so caching, laziness, and invalidation are unchanged; any
    graph the compiler cannot handle falls back to the previous creators.
  Cycle detection is unchanged for the interpreted path and for `validate()` /
  `assert_valid()`. The compiled flat path is verified against an independent
  reference resolver over thousands of randomized graphs.

## [1.3.0] - 2026-06-06

### Added

- Reproducible dependency-resolution benchmark script for comparing Injex with
  manual wiring, Wireup, dependency-injector, lagom, and punq.
- Performance documentation explaining the benchmark shape, environment, and
  interpretation.
- Regression tests for fast-path resolution, cached plans, fallback behavior,
  overrides, optional dependencies, and unhashable factories.
- Documentation site pages with canonical URLs, sitemap, robots.txt,
  Open Graph metadata, and structured data.
- Article page explaining why a small Python DI container can be useful for
  services, CLIs, workers, tests, and clean architecture.
- Favicon, PNG social preview card, 404 page, and FAQ structured data for the
  Python dependency injection guide.

### Changed

- Resolution now caches dependency plans and uses a fast path for common
  constructor-injection graphs.
- Internal implementation was split into focused modules for errors, planning,
  registry, and container runtime logic.
- Test coverage was raised to 96%.
- Public website now links to local documentation pages instead of only GitHub
  Markdown files.
- Landing page and documentation pages now use a more polished visual system,
  improved navigation, responsive cards, focus states, and reduced-motion-safe
  CSS animations.
- Added a Python dependency injection guide for readers comparing manual wiring,
  framework DI, and small containers.
- Sitemap now contains only indexable HTML pages, with service files kept outside
  the sitemap.
- Mobile navigation and social metadata were tightened across the static site.

### Fixed

- Fast-path resolution now preserves cycle detection, override invalidation,
  optional injected properties, and unhashable callable factory support.

## [1.2.1] - 2026-05-25

### Added

- Release workflow for tagged builds with wheel smoke tests and release assets.
- Release checklist for maintainers.
- CODEOWNERS and issue template chooser configuration.
- GitHub Pages-ready docs site.
- Positioning guide, usage scenarios, and project overview copy.
- Comparison guide for choosing between manual wiring, framework dependencies,
  Injex, and larger DI containers.

### Changed

- CI now uses `astral-sh/setup-uv`, builds distributions, smoke-tests wheels,
  and avoids failing fork pull requests on Codecov token availability.
- README and docs site now surface the public website more prominently.
- Package description now emphasizes typed dependency injection for Python apps.

## [1.2.0] - 2026-05-25

### Added

- Dependency graph validation through `Container.validate()` and
  `Container.assert_valid()`.
- Public API export list for stable imports from `injex`.
- PEP 561 typing marker for downstream type checkers.
- SPDX license metadata for modern Python packaging.
- API reference, validation guide, roadmap, security policy, and GitHub issue/PR
  templates.

### Fixed

- Invalid lifestyle error message now includes scoped services.
- Tutorial table of contents typos and anchors.

## [1.1.0] - 2026-05-25

### Added

- Temporary dependency overrides for focused tests and local composition changes.
- Real-world examples for clean architecture, CLI applications, and testing.
- Contributor guide with local setup, quality checks, and contribution scope.

### Changed

- README now focuses on practical application wiring, trade-offs, and examples.

## [1.0.0] - 2024-10-23

### Added

- Stable container API for services, factories, instances, named registrations,
  scoped services, optional dependencies, and property injection.
- Python 3.10, 3.11, 3.12, and 3.13 support.

## [0.1.2] - 2024-10-21

### Changed

- Documentation and packaging refinements.

## [0.1.1] - 2024-10-20

### Fixed

- Minor registration and resolution edge cases.

## [0.1.0] - 2024-10-19

### Added

- Initial public release.
