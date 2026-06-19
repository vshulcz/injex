# Roadmap

Injex stays small by design. The roadmap focuses on practical wiring, testing,
and documentation rather than framework-specific abstractions.

## Near term

- Grow recipes, migration, and example coverage from real usage patterns.
- Document common error messages and their fixes.

## Later

- Explore opt-in diagnostics for registration inspection (print/inspect the
  resolved graph).

## Done

- Typed `resolve` / `resolve_all` / `aresolve` overloads and strict mypy.
- Named injection via `Annotated[T, Named(...)]`.
- Sync and async resources with teardown; `close()` / `aclose()`.
- Function injection (`call()` / `acall()`) and auto-registration
  (`@injectable` + `scan()`).
- FastAPI (`injex.ext.fastapi`) and Typer/Click (`injex.ext.cli`) integrations.
- Published the documentation site and a reproducible resolve benchmark.
- Cached dependency plans with a fast compiled path for common graphs.

## Non-goals

- No runtime dependencies in the core package (integrations live in optional
  `injex.ext.*`, installed via extras).
- No decorators required for constructor injection.
- No large configuration DSL.
