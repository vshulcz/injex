# Roadmap

Injex stays small by design. The roadmap focuses on practical wiring, testing,
and documentation rather than framework-specific abstractions.

## Near term

- Expand framework and background worker examples based on real usage patterns.
- Improve public method type hints without making the API harder to read.
- Add more validation coverage for named and scoped registrations.
- Document common error messages and fixes.

## Later

- Explore opt-in diagnostics for registration inspection (print/inspect the
  resolved graph).
- Grow the recipe and migration guides as real usage patterns emerge.

## Done

- Published the documentation site at
  [vshulcz.github.io/injex](https://vshulcz.github.io/injex/).
- Added recipes for CLI, web, worker, and clean architecture layouts.
- Added a reproducible resolve benchmark and performance notes.
- Cached dependency plans with a fast path for common constructor graphs.

## Non-goals

- No runtime dependencies.
- No framework-specific core package code.
- No decorators required for constructor injection.
- No large configuration DSL.
