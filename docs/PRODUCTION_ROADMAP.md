# Saarthi Production Roadmap

This roadmap tracks the transition from the current YONO experience prototype to an SBI pilot and, subject to governance approval, a production service.

## Phase 1 — Trust boundary foundation

Status: in progress

- [x] Server-authoritative purpose consent gate
- [x] Separate consent revocation from erasure
- [x] Remove raw PII from orchestration responses
- [x] Atomic two-per-cycle promotional nudge budget
- [x] Exempt customer-support interventions from promotional budget
- [x] Persist pending recommendations with expiry
- [x] Single-use server authorization tokens after explicit action consent
- [x] Unit and HTTP lifecycle tests
- [x] Authenticated customer identity instead of caller-supplied customer IDs
- [ ] Encryption keys and secrets from an SBI-approved vault/KMS
- [x] Application/database append-only pseudonymous hash chain with integrity verification
- [ ] Independently operated WORM audit sink with retention and legal-hold policies

Exit criteria: no customer can be profiled or authorized through an unauthenticated or unconsented path; security and privacy threat models are approved.

## Phase 2 — Platform services

- [x] Replace the standard-library HTTP server with a supported ASGI API service and typed request/response schemas.
- [x] Introduce ordered, transactional schema migrations for the current SQLite persistence layer.
- [x] Add a PostgreSQL-compatible SQLAlchemy persistence implementation and Compose deployment.
- [ ] Run SBI-environment PostgreSQL load, failover, backup, restore, and migration rehearsals.
- [x] Bind customer-scoped endpoints to verified identity, with asymmetric OIDC/JWKS verification and an explicit development-only header mode.
- [x] Replace the in-memory event stream in the container stack with a real Redis Streams adapter.
- [x] Add atomic request/event idempotency, retry-safe dependency failures, trace event IDs, and readiness checks.
- [x] Add consumer groups, stale-message recovery, bounded retries, dead-letter handling, idempotent replay operations, and SLO telemetry.
- [ ] Approve production SLO thresholds, alert routing, and on-call ownership with SBI operations.
- [x] Package the frontend, API, and event worker as separate deployable services with environment-specific configuration and health checks.

Exit criteria: repeatable deployment in an SBI non-production environment, observable end-to-end processing, and recovery tests.

## Phase 3 — Decision intelligence

- [x] Replace inline keyword classification with versioned signal features, input-bound provenance, executable evaluation evidence, and a fail-closed SBI service adapter.
- [ ] Connect the detector adapter to an SBI-approved production model and complete population-level precision, recall, drift, and harm validation.
- [x] Add a versioned, effective-dated Neo4j eligibility adapter with parameter-bound queries.
- [x] Add signed, versioned product/rules artifacts with trust-anchor verification, four-eyes activation, rollback, restart materialization, and Neo4j runtime application.
- [ ] Connect the signed product/rules artifact source to SBI-owned catalogue, pricing, and eligibility release systems.
- [x] Reject tampered, unapproved, future, or expired policy manifest entries and return structured provenance.
- [x] Add signed, versioned policy-registry artifacts with content-digest validation, four-eyes activation, rollback, restart materialization, and runtime retrieval updates.
- [ ] Connect the signed policy-registry artifact source to SBI-owned policy/legal release systems.
- [x] Add a durable reviewer queue and block high-risk authorization until independent approval.
- [x] Compile deterministic decision nodes as a typed LangGraph workflow; retain review durability in the transactional database state machine.
- [x] Bind eligibility to a trusted, fresh server-side customer context rather than a caller-selected segment.
- [x] Add deterministic suitability, affordability, vulnerable-customer, and channel-frequency gates.
- [x] Add privacy-minimized, idempotent outcome ingestion and minimum-sample disparity monitoring by operational segment, signal, and product.
- [ ] Add policy-owner-approved fairness thresholds, protected-class analysis, and ongoing disparate-outcome monitoring.

Exit criteria: documented precision/recall and harm metrics, reproducible recommendations, policy-owner approval, and full decision reason codes.

## Phase 4 — SBI integration

- [x] Implement the OIDC/JWKS verifier contract, asymmetric algorithm allowlist, issuer/audience validation, and role extraction.
- [ ] Connect and certify the verifier against SBI YONO's live identity tenant and workload/network controls.
- [x] Define and enforce the fail-closed SBI customer decision-context API contract.
- [ ] Connect the context contract to approved CBS, cards, CRM, branch, and consent read models in an SBI environment.
- [x] Define token-bound, idempotent fulfilment and persist execution claims, failures, retries, and downstream references.
- [ ] Connect and certify product-specific fulfilment endpoints in an SBI sandbox.
- Integrate product catalogue, eligibility, KFS, pricing, and fulfilment APIs.
- Route stress cases to CRM/RM workflows without promotional cross-sell.
- [x] Reconcile every executed action against downstream banking status with concurrency-safe retries, discrepancy metrics, and an operator queue.
- [x] Add a four-eyes, idempotent reconciliation-escalation workflow with typed SBI case-management adapter, retry-safe submission, and status synchronization.
- [ ] Connect and certify the case adapter against SBI incident/case management and approve product-specific compensating procedures.

Exit criteria: sandbox journeys complete against SBI-owned services with no synthetic shortcuts on the execution path.

## Phase 5 — Governance and controlled rollout

- Complete privacy impact assessment, threat model, VAPT, model-risk review, legal review, and records-retention approval.
- [x] Run non-customer-visible shadow mode without persisting offers or consuming nudge budget.
- [x] Pilot with deterministic percentage cohorts and conservative budgets.
- [x] Instrument complaints, opt-outs, false positives, conversion, benefit, harm, and operational-group disparity indicators.
- [ ] Connect certified SBI outcome feeds and prove customer benefit exceeds harm under approved production thresholds.
- [x] Provide four-eyes controls and emergency kill switches at global, product, segment, signal, channel, and exact model-version levels.
- [x] Require signed product and policy artifacts in production configuration.
- [ ] Approve SBI signing-key custody, rotation, release transport, and operational evidence procedures.

Exit criteria: signed production approvals, proven rollback, agreed service levels, and evidence that customer benefit exceeds measured harm.
