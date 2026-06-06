# Performance notes

Injex is designed for small explicit service graphs. Version 1.3.0 adds cached
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
- `injex 1.3.0`;
- `wireup 2.11.1`;
- `dependency-injector 4.49.0`;
- `lagom 2.7.7`;
- `punq 0.7.0`.

| Library | Median resolve time |
| --- | ---: |
| manual wiring | `0.265 µs/op` |
| Injex | `0.818 µs/op` |
| Wireup, same scope | `0.879 µs/op` |
| Wireup, scope per operation | `1.559 µs/op` |
| dependency-injector | `1.727 µs/op` |
| lagom | `9.794 µs/op` |
| punq | `56.795 µs/op` |

These numbers are not a universal ranking. They are a small synthetic benchmark
for one graph shape. Different lifetimes, framework integrations, factories,
async resources, and request context models can change results.

## Reproduce

Run from the repository root:

```bash
uv run --with punq --with lagom --with dependency-injector --with wireup \
  python benchmarks/resolve_graph.py
```

The benchmark prints Python/package versions, the graph shape, median time, min
and max samples, and relative overhead compared with manual wiring.

## What this means

The result supports Injex's niche: explicit typed wiring can stay small while
keeping hot-path resolve overhead low. Use the numbers as a sanity check, not as
a substitute for measuring your own application graph.
