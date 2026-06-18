# Benchmarks

The benchmark suite is intentionally small. It measures repeated resolution of a
typical service-layer graph:

- singleton `Settings` instance;
- singleton `ApiClient(settings)`;
- transient `UserRepository(client)`;
- transient `EmailSender(client)`;
- transient `AuditLog(settings)`;
- transient `RegisterUser(repository, email_sender, audit_log)`.

This shape is common in FastAPI/Typer/worker applications: app-wide
configuration and clients, with per-operation use cases.

## Run

From the repository root:

```bash
uv run --with punq --with lagom --with dependency-injector --with wireup --with dishka \
  python benchmarks/resolve_graph.py
```

## Latest local result

Environment:

- Python `3.13.5` on macOS arm64;
- `injex 1.4.0`;
- `wireup 2.11.1`;
- `dishka 1.10.1`;
- `dependency-injector 4.49.0`;
- `lagom 2.7.7`;
- `punq 0.7.0`.

| Library | Median resolve time |
| --- | ---: |
| manual wiring | `0.264 µs/op` |
| Injex | `0.407 µs/op` |
| dishka | `0.755 µs/op` |
| Wireup, same scope | `0.935 µs/op` |
| Wireup, scope per operation | `1.559 µs/op` |
| dependency-injector | `1.721 µs/op` |
| lagom | `10.010 µs/op` |
| punq | `58.786 µs/op` |

## Async benchmark

`resolve_async.py` measures the same graph through each library's async API, for
two shapes: a synchronous graph resolved in an async context (the common FastAPI
case of awaiting a resolve on plain classes), and a graph whose `Settings` is
produced by an `async def` factory. Only libraries with a real async path are
included.

```bash
uv run --with wireup --with dishka --with dependency-injector \
  python benchmarks/resolve_async.py
```

Latest local result (Python `3.13.5`, macOS arm64; `injex 1.5.0`, `wireup 2.11.3`,
`dishka 1.10.1`):

| Library | Sync graph via async API | Graph with an async factory |
| --- | ---: | ---: |
| Injex | `0.441 µs/op` | `1.165 µs/op` |
| dishka | `1.451 µs/op` | `1.503 µs/op` |
| Wireup, scope per operation | `1.782 µs/op` | `2.094 µs/op` |

Same caveats as below: synthetic, one graph shape, not a universal ranking.

## Interpretation

This is not a universal DI ranking. It is a reproducible sanity check for one
graph shape. Different lifetimes, framework integrations, async resources,
provider styles, and request scopes can change results.

In particular, dishka is measured here on a synchronous graph with `cache=False`
transients. Its strengths — async resource lifecycles and explicit request/session
scopes — are not exercised by this shape, so treat its number as "this graph,"
not "dishka in general."

The goal is narrower: show that Injex keeps repeated resolve overhead low for
small explicit service graphs.
