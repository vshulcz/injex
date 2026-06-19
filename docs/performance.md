# Performance notes

Injex is designed for small explicit service graphs. Injex adds cached
dependency plans and a fast resolve path for the common case: singleton
infrastructure plus transient application services.

## Benchmark shape

The benchmark resolves this graph repeatedly:

- singleton `Settings` instance;
- singleton `ApiClient(settings)`;
- transient `UserRepository(client)`;
- transient `EmailSender(client)`;
- transient `AuditLog(settings)`;
- transient `RegisterUser(repository, email_sender, audit_log)`.

This mirrors a common service-layer shape: app-wide configuration and clients,
with per-operation use cases.

## Local result

Environment used for the project benchmark:

- Python `3.13.5`;
- macOS arm64;
- `injex 1.5.0`;
- `wireup 2.11.3`;
- `dishka 1.10.1`;
- `dependency-injector 4.49.1`;
- `lagom 2.7.7`;
- `punq 0.7.0`.

| Library | Median resolve time |
| --- | ---: |
| manual wiring | `0.266 µs/op` |
| Injex | `0.333 µs/op` |
| dishka | `0.786 µs/op` |
| Wireup, same scope | `0.872 µs/op` |
| Wireup, scope per operation | `1.544 µs/op` |
| dependency-injector | `1.709 µs/op` |
| lagom | `9.487 µs/op` |
| punq | `56.982 µs/op` |

These numbers are not a universal ranking. They are a small synthetic benchmark
for one graph shape. Different lifetimes, framework integrations, factories,
async resources, and request context models can change results. dishka in
particular is measured here on a synchronous graph; its async-resource and
scope features are not exercised, so treat its number as "this graph," not
"dishka in general."

## Reproduce

Run from the repository root:

```bash
uv run --with punq --with lagom --with dependency-injector --with wireup --with dishka \
  python benchmarks/resolve_graph.py
```

The benchmark prints Python/package versions, the graph shape, median time, min
and max samples, and relative overhead compared with manual wiring.

See also: [`benchmarks/README.md`](../benchmarks/README.md).

## What this means

The result supports Injex's niche: explicit typed wiring can stay small while
keeping hot-path resolve overhead low. Use the numbers as a sanity check, not as
a substitute for measuring your own application graph.
