# Changelog

All notable changes to Injex are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning.

## [Unreleased]

## [1.6.0] - 2026-06-19

### Added

- `container.call(func, **overrides)` (and async `acall`) invoke a function with
  its annotated parameters injected from the container, while `overrides` supplies
  per-call values (a request, parsed args, a message). `acall` awaits async
  dependencies and coroutine functions and finalizes async resources opened for
  the call. This is the building block for wiring handlers, CLI commands, and
  task consumers without turning them into classes.
- Inject a named registration into a constructor with
  `Annotated[T, Named("primary")]`. Previously a named registration could only be
  reached through `resolve(T, name="primary")`; now it can be a constructor
  dependency, and `validate()` checks it like any other.
- `Scope` is a context manager: `with container.create_scope() as scope: ...`
  drops the scope's per-scope instances on exit.

### Changed

- Clearer resolution errors. A missing dependency now reads
  `Service for interface 'DB' is not registered. It is required by Repo.db.`
  instead of printing the raw class repr with no context. `validate()` no longer
  repeats the same error once per root that shares a dependency.

## [1.5.1] - 2026-06-19

### Fixed

- Thread-safe singleton construction. Concurrent first resolves of the same
  singleton could each build it, handing different threads different instances.
  Construction is now guarded by a reentrant lock with a lock-free fast path, so
  a singleton is built once; the warm resolve path is unchanged.
- Async singletons are also built once. Concurrent `aresolve()` calls for the same
  uncached singleton shared no build, so each constructed its own; they now await
  a single in-flight build.

## [1.5.0] - 2026-06-19

### Changed

- Faster repeated resolves. The compiled creator now realizes scope-free
  singletons once at build time and inlines them as constants, so resolving a
  graph runs its constructors with no per-resolve getter calls. Sync `resolve()`
  drops from `0.40` to `0.33 µs/op` (1.25× manual wiring) on the project
  benchmark; singleton-heavy graphs improve ~60%. Singleton identity, laziness,
  and override semantics are unchanged.

### Added

- Typed `resolve()` / `resolve_all()` / `aresolve()` via `@overload`: passing a
  type now infers that type (`resolve(Foo) -> Foo`, `resolve_all(Foo) -> list[Foo]`)
  instead of `Any`, so resolved services stay type-checked at the call site. A
  string interface still falls back to `Any`.
- `aresolve()` on the container raises a clear error when asked to resolve a
  scoped/transient async resource directly (which it would finalize immediately),
  pointing at `async with container.ascope()`.
- Docstrings on the public registration and scope methods.
- Async resolution, zero-dependency and sync-first. `await container.aresolve(T)`
  and `async with container.ascope() as scope: await scope.aresolve(T)` await
  `async def` factories and manage async-generator resources (`yield` then
  `await cleanup()`), finalized when the scope exits, or on
  `await container.aclose()` for singletons, via a stdlib `AsyncExitStack`.
  `aresolve()` compiles a flat async creator that inlines the synchronous parts of
  the graph and awaits only the genuinely async nodes: a fully-sync graph resolves
  at sync speed (~0.44 µs/op), a graph with an `async def` factory at ~1.2 µs/op.
  Sync `resolve()` raises `AsyncResolutionRequiredException` if the graph needs
  async work, and is itself untouched. See `benchmarks/resolve_async.py`.
- `PropertyInjectionException` with a clear message when property injection
  (`@inject` methods) targets a `__slots__` type or a frozen dataclass, instead of
  a raw `AttributeError` / `FrozenInstanceError`. Constructor injection into those
  types is unaffected.

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
