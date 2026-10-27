# Architecture and Trust Boundaries

## Runtime services

- Port 8000: FastAPI control plane, UI files, SQLite event store, incident state transitions, and investigation.
- Port 8001: Order HTTP service; calls inventory then payment, with a 700ms payment deadline.
- Port 8002: Inventory HTTP service; returns simulated stock and emits real request events.
- Port 8003: Payment HTTP service; applies a reversible simulated fault configuration and emits real request events.
- Port 8080 (optional): Spring Boot REST adapter; proxies supported operations into the Python control plane.

Every checkout uses a random trace ID transmitted through `X-Trace-Id`. Each service records request timestamps, duration, operation, status, optional fault attributes and a message by posting to the local ingest endpoint. These are correlated as a custom trace. That is **not** OpenTelemetry propagation, span context, or comprehensive instrumentation.

## Incident lifecycle

`DETECTED → ROOT_CAUSE_PROPOSED → AWAITING_APPROVAL → APPROVED → RESOLVED`.

A verification failure transitions to `FAILED` instead. Investigation does not automatically create a patch. Proposal generation is allowlisted to the two demo mitigation types. Users must explicitly approve before the engine updates runtime configuration. Verification runs **three actual HTTP checkouts** and requires three `201` responses. It then marks the incident `RESOLVED`. The verification record includes test trace IDs and pre/post configuration.

## Causality

The investigator reads evidence scoped to the incident's **trace ID** rather than all logs. It differentiates healthy inventory spans from a failing payment response, ranks hypotheses and preserves each event identifier. For payment timeout, the emitting payment service can finish after the order service has already timed out. The local fault trigger briefly waits to capture the delayed payment span before creating the incident.

## Security scope

All active services listen on loopback. This is an isolated **demonstration only**. Local HTTP clients may inject telemetry, change demo configuration or reset data; do not expose these ports publicly. A production version must have mTLS or ingestion tokens, authenticated RBAC, per-workspace authorization, transport encryption, retention/privacy controls, bounded event size and trusted service identities. The optional `OPENAI_BASE_URL` must be trusted; user-supplied target URLs would require strict allowlisting.

Future untrusted repository/code execution must be placed in separately isolated, resource-restricted containers; current MVP deliberately does not offer an execution endpoint.
