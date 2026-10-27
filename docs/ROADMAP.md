# Production and hackathon extension roadmap

## Milestone A: Observable Java services

- Replace Python demo order/inventory/payment services with separate **Spring Boot** services.
- Instrument Spring Boot 3.x Micrometer + OpenTelemetry SDK and use W3C `traceparent` propagation.
- Add real database pool metrics via HikariCP, JDBC spans and realistic bounded fault injection.
- Deploy Jaeger/Tempo and OpenTelemetry Collector; use real querying rather than the ad-hoc event table.

## Milestone B: Real AI agent tools

- Build trace and log retrieval tools with permission scopes and bounded execution budgets.
- Let a LangGraph-based investigator compare competing hypotheses and cite original telemetry.
- Add retrieval over indexed repository code, with safeguards against prompt injection and secret leakage.
- Introduce approved, isolated code patch generation and local test execution.

## Milestone C: Java platform, security, and collaboration

- Move incident CRUD, authentication and team boundaries into Java 21 Spring Boot + PostgreSQL.
- Secure telemetry ingestion; require authenticated session and role-checked manual approval.
- Add idempotent asynchronous job execution and durable run state with queues.
- Add audit trails, RBAC, OAuth login, private GitHub app permissions and PR review.
- Create CI pipeline with Testcontainers and a sandbox to test untrusted repository code.

## Milestone D: Polished hackathon experience

- Add a richer timed trace waterfall, service metrics charts and expandable source evidence.
- Record a concise two-minute working demo, not a list of unchecked features.
- Keep Wispr Flow participation legitimate: use the tool for dictated coding prompts and the voice investigation demo, collect the required usage proof.
