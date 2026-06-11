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
uv run --with punq --with lagom --with dependency-injector --with wireup \
  python benchmarks/resolve_graph.py
```

## Latest local result

Environment:

- Python `3.13.5` on macOS arm64;
- `injex` main (fast-path resolution, post-1.3.0);
- `wireup 2.11.1`;
- `dependency-injector 4.49.0`;
- `lagom 2.7.7`;
- `punq 0.7.0`.

| Library | Median resolve time |
| --- | ---: |
| manual wiring | `0.265 µs/op` |
| Injex | `0.629 µs/op` |
| Wireup, same scope | `0.877 µs/op` |
| Wireup, scope per operation | `1.545 µs/op` |
| dependency-injector | `1.721 µs/op` |
| lagom | `9.840 µs/op` |
| punq | `57.136 µs/op` |

## Interpretation

This is not a universal DI ranking. It is a reproducible sanity check for one
graph shape. Different lifetimes, framework integrations, async resources,
provider styles, and request scopes can change results.

The goal is narrower: show that Injex keeps repeated resolve overhead low for
small explicit service graphs.
