# Saarthi SBI Review Demo Runbook

> **Live Deployed Prototype:** [https://invexora.github.io/saarthi-yono-copilot/](https://invexora.github.io/saarthi-yono-copilot/)
> **Audience:** SBI product, digital, risk, privacy, security, architecture and operations reviewers
> **Scope:** Repeatable evidence for the current synthetic reference prototype

## Review boundary

This runbook demonstrates implemented Saarthi routes, browser states and automated controls. It does **not** demonstrate an SBI connection or customer-ready banking service.

- All personas, customer IDs, signals, balances, action IDs, product rules and downstream references are synthetic fixtures.
- The 16 catalogue IDs used by the demo are local action identifiers, not confirmed SBI SKUs.
- The 28 boundary contracts are Saarthi's internal, transport-neutral mock contracts, not discovered InnoHub endpoints.
- Development identity headers are convenient local test identities. They are not SBI OIDC, YONO authentication or step-up authentication.
- The configured local fulfilment and reconciliation providers are synthetic. A `fulfilled` or `matched` result proves state and identity handling only; it is not a banking transaction.
- Do not quote a product rate, saving, approval or eligibility outcome from this demo. Live rate, KFS, eligibility and policy feeds are not connected.

The pass condition is therefore narrower: the same synthetic recommendation identity must remain bound through presentation, review where required, customer authorization, mock fulfilment and reconciliation; support-only and blocked states must expose no executable offer.

## Roles used in local development

Every command below uses `SAARTHI_AUTH_MODE=development`. The API derives the acting identity from these headers:

| Actor | Local header | Demonstrated permissions |
|---|---|---|
| Synthetic customer | `X-Saarthi-Demo-Role: customer` | Own consent, orchestration, offer presentation, authorization and execution |
| Independent reviewer | `X-Saarthi-Demo-Role: reviewer` | Review queue and approve/reject a high-risk recommendation |
| Operator | `X-Saarthi-Demo-Role: ops` | Reconciliation, metrics and request controlled changes |
| Administrator | `X-Saarthi-Demo-Role: admin` | Emergency disable and independently approve controlled changes |
| Auditor | `X-Saarthi-Demo-Role: auditor` | Governance records, aggregate monitoring and audit-integrity verification |

Use a different `X-Saarthi-Demo-Customer` value for the requester and approver when demonstrating a four-eyes control. This is a prototype principal identifier, not a real SBI customer or employee number.

## 1. Clean, deterministic startup

Run from the repository root. The commands require Python 3, Node.js, `curl` and `jq`. Install both runtime and test dependencies once:

```bash
python3 -m pip install -r backend/requirements-dev.txt
mkdir -p tmp/demo-evidence
```

Start the API in terminal A with a new database for every review. High-risk review is explicitly enabled so the two high-risk golden journeys cannot bypass the reviewer:

```bash
export SAARTHI_DB_PATH="tmp/demo-evidence/runbook-$(date +%Y%m%d-%H%M%S).db"
export SAARTHI_AUTH_MODE=development
export SAARTHI_DECISION_SECRET=local-runbook-decision-secret-32-chars
export SAARTHI_AUDIT_SECRET=local-runbook-audit-secret-32-characters
export SAARTHI_HIGH_RISK_REVIEW_MODE=required
export SAARTHI_ALLOWED_ORIGINS=http://localhost:8000
export PORT=5050
python3 -m backend.server
```

Start the browser UI in terminal B:

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

Open [http://localhost:8000](http://localhost:8000), with no query parameter. The status must say `API Connected (Governed Mode)`. `?mode=offline-demo` is a separate simulation and is not acceptable as connected evidence.

In terminal C, define the API base and capture the preflight:

```bash
export API=http://localhost:5050/api/v1
mkdir -p tmp/demo-evidence
curl -fsS "$API/health" | tee tmp/demo-evidence/health.json | jq '{status, deployment_mode, auth_mode, simulated_components}'
curl -fsS "$API/ready" | tee tmp/demo-evidence/readiness.json | jq '{status, dependencies}'
```

Expected result: health is `ok`; readiness is `ready`; the health response visibly lists the locally simulated components. In local memory-stream mode a separate event worker is not required. Do not use that local readiness result as production-readiness evidence.

Run the regression baseline before the walkthrough:

```bash
python3 -m pytest -q
node --test tests/frontend/*.test.mjs
```

Expected result at this snapshot: 142 backend tests plus 108 parameterized subtests pass, and 14 frontend contract tests pass.

## 2. Exact four golden journeys

The four journeys below turn the solution-level scope into four concrete, repeatable fixtures. Execute them against the fresh database from the startup section.

### Golden journey 1 — reviewed debt-comparison action

Fixture: Priya/corporate, `DEBT_OPPORTUNITY`, synthetic action ID `SBI-LOAN-EXP01`. This is a high-risk synthetic comparison path; no live credit eligibility, price, KFS or application submission is demonstrated.

Grant purpose consent and request the decision:

```bash
export C1=SBI-772910
curl -fsS -X POST "$API/consent/grant" \
  -H "X-Saarthi-Demo-Customer: $C1" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -d '{"purpose":"personalization"}' \
  | tee tmp/demo-evidence/gj1-consent.json

curl -fsS -X POST "$API/orchestrate" \
  -H "X-Saarthi-Demo-Customer: $C1" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: gj1-debt-review-001' \
  -d '{"signal":"DEBT_OPPORTUNITY — CC interest ₹4,200/mo exceeds consolidation threshold","details":"Email: priya@example.com | PAN: ABCDE1234F | Aadhaar: 4532 9981 1204","segment":"corporate"}' \
  | tee tmp/demo-evidence/gj1-orchestration.json \
  | jq '{delivery_mode,decision_outcome,review_id,recommendation_id,recommended_product_id,interest_rate,reason_codes,masked_details}'

export GJ1_REC=$(jq -r '.recommendation_id' tmp/demo-evidence/gj1-orchestration.json)
export GJ1_REVIEW=$(jq -r '.review_id' tmp/demo-evidence/gj1-orchestration.json)
```

Expected result: `human_review_required`, `review_required`, a review and recommendation ID, no public product/rate fields, and masked submitted identifiers. Authorization before review returns HTTP `409` with `review_required`:

```bash
curl -sS -o tmp/demo-evidence/gj1-pre-review-authorization.json -w 'HTTP %{http_code}\n' \
  -X POST "$API/decisions/authorize" \
  -H "X-Saarthi-Demo-Customer: $C1" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -d "{\"recommendationId\":\"$GJ1_REC\"}"
cat tmp/demo-evidence/gj1-pre-review-authorization.json | jq '{status}'
```

Use a distinct reviewer identity, approve, and only then present the persisted offer:

```bash
curl -fsS "$API/reviews?review_status=pending" \
  -H 'X-Saarthi-Demo-Customer: SBI-RUNBOOK-REVIEWER-001' -H 'X-Saarthi-Demo-Role: reviewer' \
  | tee tmp/demo-evidence/gj1-review-queue.json | jq --arg id "$GJ1_REVIEW" '.[] | select(.review_id==$id)'

curl -fsS -X POST "$API/reviews/$GJ1_REVIEW/decision" \
  -H 'X-Saarthi-Demo-Customer: SBI-RUNBOOK-REVIEWER-001' -H 'X-Saarthi-Demo-Role: reviewer' \
  -H 'Content-Type: application/json' \
  -d '{"decision":"approved","reason":"Synthetic suitability and disclosure evidence checked"}' \
  | tee tmp/demo-evidence/gj1-review-decision.json | jq '{status,review}'

curl -fsS "$API/recommendations/$GJ1_REC" \
  -H "X-Saarthi-Demo-Customer: $C1" -H 'X-Saarthi-Demo-Role: customer' \
  | tee tmp/demo-evidence/gj1-presentation.json \
  | jq '{status,recommendation_id:.recommendation.recommendation_id,product_id:.recommendation.product_id,presentation:.recommendation.evidence.presentation}'
```

Expected result: the presented product ID is `SBI-LOAN-EXP01`; the presentation is server-owned and has the same product ID. Authorize, execute through the synthetic provider, then reconcile:

```bash
curl -fsS -X POST "$API/decisions/authorize" \
  -H "X-Saarthi-Demo-Customer: $C1" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -d "{\"recommendationId\":\"$GJ1_REC\"}" \
  | tee tmp/demo-evidence/gj1-authorization.json | jq '{status,recommendation_id,product_id}'
export GJ1_TOKEN=$(jq -r '.decision_token' tmp/demo-evidence/gj1-authorization.json)

curl -fsS -X POST "$API/actions/execute" \
  -H "X-Saarthi-Demo-Customer: $C1" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' \
  -d "{\"recommendationId\":\"$GJ1_REC\",\"decisionToken\":\"$GJ1_TOKEN\"}" \
  | tee tmp/demo-evidence/gj1-execution.json | jq '{status,recommendation_id,fulfillment}'

curl -fsS -X POST "$API/fulfillment/reconciliations/$GJ1_REC/run" \
  -H 'X-Saarthi-Demo-Customer: SBI-RUNBOOK-OPS-001' -H 'X-Saarthi-Demo-Role: ops' \
  | tee tmp/demo-evidence/gj1-reconciliation.json | jq '{status,reconciliation}'
```

Expected result: the same recommendation ID is `fulfilled`, the provider is visibly synthetic, and reconciliation is `matched`. In the UI, select Priya and trigger `Opportunity Signal`; the offer remains withheld until the reviewer command completes, after which the browser poll exposes the governed presentation.

### Golden journey 2 — reviewed senior-deposit action

Fixture: Ramesh/pensioner, `FD_OPPORTUNITY`, synthetic action ID `SBI-FD-SENIOR02`. This walkthrough intentionally does not treat a local rate field as a live SBI quote.

```bash
export C2=SBI-881234
curl -fsS -X POST "$API/consent/grant" \
  -H "X-Saarthi-Demo-Customer: $C2" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -d '{"purpose":"personalization"}' \
  | tee tmp/demo-evidence/gj2-consent.json >/dev/null

curl -fsS -X POST "$API/orchestrate" \
  -H "X-Saarthi-Demo-Customer: $C2" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: gj2-senior-review-001' \
  -d '{"signal":"FD_OPPORTUNITY — ₹50,000 idle savings exceeding 90-day liquidity buffer","segment":"pensioner"}' \
  | tee tmp/demo-evidence/gj2-orchestration.json \
  | jq '{delivery_mode,decision_outcome,review_id,recommendation_id,recommended_product_id,interest_rate}'
export GJ2_REC=$(jq -r '.recommendation_id' tmp/demo-evidence/gj2-orchestration.json)
export GJ2_REVIEW=$(jq -r '.review_id' tmp/demo-evidence/gj2-orchestration.json)

curl -fsS -X POST "$API/reviews/$GJ2_REVIEW/decision" \
  -H 'X-Saarthi-Demo-Customer: SBI-RUNBOOK-REVIEWER-002' -H 'X-Saarthi-Demo-Role: reviewer' \
  -H 'Content-Type: application/json' \
  -d '{"decision":"approved","reason":"Synthetic deposit disclosure and suitability evidence checked"}' \
  | tee tmp/demo-evidence/gj2-review-decision.json >/dev/null

curl -fsS "$API/recommendations/$GJ2_REC" \
  -H "X-Saarthi-Demo-Customer: $C2" -H 'X-Saarthi-Demo-Role: customer' \
  | tee tmp/demo-evidence/gj2-presentation.json \
  | jq '{status,recommendation_id:.recommendation.recommendation_id,product_id:.recommendation.product_id,presentation_product_id:.recommendation.evidence.presentation.product_id}'

curl -fsS -X POST "$API/decisions/authorize" \
  -H "X-Saarthi-Demo-Customer: $C2" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -d "{\"recommendationId\":\"$GJ2_REC\"}" \
  | tee tmp/demo-evidence/gj2-authorization.json >/dev/null
export GJ2_TOKEN=$(jq -r '.decision_token' tmp/demo-evidence/gj2-authorization.json)

curl -fsS -X POST "$API/actions/execute" \
  -H "X-Saarthi-Demo-Customer: $C2" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' \
  -d "{\"recommendationId\":\"$GJ2_REC\",\"decisionToken\":\"$GJ2_TOKEN\"}" \
  | tee tmp/demo-evidence/gj2-execution.json | jq '{status,recommendation_id,fulfillment}'

curl -fsS -X POST "$API/fulfillment/reconciliations/$GJ2_REC/run" \
  -H 'X-Saarthi-Demo-Customer: SBI-RUNBOOK-OPS-002' -H 'X-Saarthi-Demo-Role: ops' \
  | tee tmp/demo-evidence/gj2-reconciliation.json | jq '{status,reconciliation}'
```

Expected result: review is mandatory; post-review presentation and authorization both bind to `SBI-FD-SENIOR02`; mock execution is `fulfilled`; synthetic reconciliation is `matched`. In the UI, select Ramesh and trigger `Senior FD Opportunity`; do not describe the fixture as live pricing or approval.

### Golden journey 3 — low-risk branch-to-digital action

Fixture: Rohan/student, branch-friction signal, synthetic action ID `SBI-EDU-DASH13`. The generic fulfilment reference represents a prototype dashboard activation, not a CBS change or measured branch deflection.

```bash
export C3=SBI-554321
curl -fsS -X POST "$API/consent/grant" \
  -H "X-Saarthi-Demo-Customer: $C3" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -d '{"purpose":"personalization"}' >/dev/null

curl -fsS -X POST "$API/orchestrate" \
  -H "X-Saarthi-Demo-Customer: $C3" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: gj3-dashboard-action-001' \
  -d '{"signal":"BRANCH_FRICTION — 2 branch visits for education loan statement queries","segment":"student"}' \
  | tee tmp/demo-evidence/gj3-orchestration.json \
  | jq '{delivery_mode,decision_outcome,recommendation_id,recommended_product_id,customer_presentation}'
export GJ3_REC=$(jq -r '.recommendation_id' tmp/demo-evidence/gj3-orchestration.json)

curl -fsS "$API/recommendations/$GJ3_REC" \
  -H "X-Saarthi-Demo-Customer: $C3" -H 'X-Saarthi-Demo-Role: customer' \
  | tee tmp/demo-evidence/gj3-presentation.json \
  | jq '{status,recommendation_id:.recommendation.recommendation_id,product_id:.recommendation.product_id}'

curl -fsS -X POST "$API/decisions/authorize" \
  -H "X-Saarthi-Demo-Customer: $C3" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -d "{\"recommendationId\":\"$GJ3_REC\"}" \
  | tee tmp/demo-evidence/gj3-authorization.json >/dev/null
export GJ3_TOKEN=$(jq -r '.decision_token' tmp/demo-evidence/gj3-authorization.json)

curl -fsS -X POST "$API/actions/execute" \
  -H "X-Saarthi-Demo-Customer: $C3" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' \
  -d "{\"recommendationId\":\"$GJ3_REC\",\"decisionToken\":\"$GJ3_TOKEN\"}" \
  | tee tmp/demo-evidence/gj3-execution.json | jq '{status,recommendation_id,fulfillment}'

curl -fsS -X POST "$API/fulfillment/reconciliations/$GJ3_REC/run" \
  -H 'X-Saarthi-Demo-Customer: SBI-RUNBOOK-OPS-003' -H 'X-Saarthi-Demo-Role: ops' \
  | tee tmp/demo-evidence/gj3-reconciliation.json | jq '{status,reconciliation}'
```

Expected result: `auto_fire`, `eligible`, and `SBI-EDU-DASH13`; the customer must still explicitly authorize before the synthetic action executes. In the UI, select Rohan and trigger `Education Loan Friction`.

### Golden journey 4 — financial-stress support only

Fixture: Sneha/stressed, missed-EMI stress signal. This path is deliberately non-promotional and non-executable.

```bash
export C4=SBI-991877
curl -fsS -X POST "$API/consent/grant" \
  -H "X-Saarthi-Demo-Customer: $C4" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -d '{"purpose":"personalization"}' >/dev/null

curl -fsS -X POST "$API/orchestrate" \
  -H "X-Saarthi-Demo-Customer: $C4" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: gj4-support-only-001' \
  -d '{"signal":"FINANCIAL_STRESS — Missed EMI (Home Loan) after salary reduction","segment":"stressed"}' \
  | tee tmp/demo-evidence/gj4-support.json \
  | jq '{delivery_mode,decision_outcome,recommendation_id,recommended_product_id,interest_rate,customer_presentation,nudge_budget}'

jq -e '.delivery_mode=="support_mode" and .recommendation_id==null and .recommended_product_id==null and .interest_rate==null and .customer_presentation.support_only==true and .customer_presentation.product_id==null' \
  tmp/demo-evidence/gj4-support.json
```

Expected result: the assertion exits `0`; there is no recommendation, product, rate, token or executable action. The support card consumes no promotional budget. In the UI, select Sneha and trigger `Home Loan Missed EMI`; the card must have no financial or case-management action button.

**Known incompleteness:** this repository does not yet connect the support card to a governed RM/case adapter. The support-only routing is executable; RM case creation and case-status proof for this golden journey are not. The separate operations-case API accepts only a reconciliation mismatch and must not be presented as if the stress journey created a case.

## 3. Consent, revocation, bounded erasure and integrity

Use a separate synthetic identity so privacy evidence does not disturb a golden journey:

```bash
export CP=SBI-RUNBOOK-PRIVACY-001
curl -fsS -X POST "$API/consent/grant" \
  -H "X-Saarthi-Demo-Customer: $CP" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -d '{"purpose":"personalization"}' \
  | tee tmp/demo-evidence/privacy-grant.json >/dev/null

curl -fsS -X POST "$API/orchestrate" \
  -H "X-Saarthi-Demo-Customer: $CP" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: privacy-fixture-001' \
  -d '{"signal":"BRANCH_FRICTION — 2 branch visits for education loan statement queries","details":"Email: private@example.com | PAN: ABCDE1234F | Aadhaar: 4532 9981 1204","segment":"student"}' \
  | tee tmp/demo-evidence/privacy-orchestration.json | jq '{masked_details,delivery_mode}'

curl -fsS "$API/consent/export" \
  -H "X-Saarthi-Demo-Customer: $CP" -H 'X-Saarthi-Demo-Role: customer' \
  | tee tmp/demo-evidence/privacy-export-before.json | jq '{audit_count:(.audit_logs|length),consent_status}'

curl -fsS -X POST "$API/consent/revoke" \
  -H "X-Saarthi-Demo-Customer: $CP" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -d '{"purpose":"personalization"}' \
  | tee tmp/demo-evidence/privacy-revoke.json | jq '{status,purpose,records_updated}'
```

After revocation, the same customer must fail closed before profiling:

```bash
curl -sS -o tmp/demo-evidence/privacy-blocked.json -w 'HTTP %{http_code}\n' \
  -X POST "$API/orchestrate" \
  -H "X-Saarthi-Demo-Customer: $CP" -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: privacy-after-revoke-002' \
  -d '{"signal":"BRANCH_FRICTION — 2 branch visits for education loan statement queries","segment":"student"}'
cat tmp/demo-evidence/privacy-blocked.json | jq '{delivery_mode,compliance_approved,recommendation_id,nudge_budget}'
```

Expected result: HTTP `403`, `consent_required`, no recommendation, and no additional nudge consumption.

Run the explicitly bounded erasure workflow and verify the retained tombstone plus integrity evidence:

```bash
curl -fsS -X POST "$API/consent/erase" \
  -H "X-Saarthi-Demo-Customer: $CP" -H 'X-Saarthi-Demo-Role: customer' \
  | tee tmp/demo-evidence/privacy-erasure.json | jq '{status,scope,retained}'

curl -fsS "$API/consent/export" \
  -H "X-Saarthi-Demo-Customer: $CP" -H 'X-Saarthi-Demo-Role: customer' \
  | tee tmp/demo-evidence/privacy-export-after.json | jq '{audit_count:(.audit_logs|length),consent_status}'

curl -fsS "$API/audit/integrity" \
  -H 'X-Saarthi-Demo-Customer: SBI-RUNBOOK-AUDITOR-001' -H 'X-Saarthi-Demo-Role: auditor' \
  | tee tmp/demo-evidence/audit-integrity.json | jq '{valid,records_checked,failed_sequence,head_hash}'
```

Expected result: erasure reports only `eligible_saarthi_derived_data`, retains `revoked_consent_tombstone` and `integrity_ledger_evidence`, the customer's operational audit export is empty, and the pseudonymous hash-chain remains valid. This does not claim deletion of banking records, backups, legal holds or systems outside Saarthi.

## 4. Explicit fail-closed evidence

The post-revocation HTTP `403` above is the live fail-closed path. The frontend contract separately proves that connected mode never converts an API outage into offline success:

```bash
node --test --test-name-pattern='offline execution is enabled only by an explicit mode' tests/frontend/offer_state.test.mjs
```

Expected result: one test passes. For a visual review, stop terminal A temporarily and reload [http://localhost:8000](http://localhost:8000). The status must read `API Unavailable — No Action`; triggering a scenario must not show an executable offer or success. Restart terminal A with the same exported database path before continuing. Do not add `?mode=offline-demo` during this check.

## 5. Emergency kill switch and four-eyes recovery

Run this after the golden journeys because a global emergency disable immediately contains all subsequent journeys:

```bash
curl -fsS -X POST "$API/governance/rollout-controls/emergency-disable" \
  -H 'X-Saarthi-Demo-Customer: SBI-RUNBOOK-ADMIN-KILL' -H 'X-Saarthi-Demo-Role: admin' \
  -H 'Content-Type: application/json' \
  -d '{"scope_type":"global","scope_value":"*","reason":"Immediate synthetic review containment exercise"}' \
  | tee tmp/demo-evidence/kill-switch.json | jq '{status,control}'

curl -fsS -X POST "$API/orchestrate" \
  -H 'X-Saarthi-Demo-Customer: SBI-RUNBOOK-KILL-CHECK' -H 'X-Saarthi-Demo-Role: customer' \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: kill-switch-check-001' \
  -d '{"signal":"DEBT_OPPORTUNITY — CC interest exceeds consolidation threshold","segment":"corporate"}' \
  | tee tmp/demo-evidence/kill-switch-check.json \
  | jq '{delivery_mode,decision_outcome,recommendation_id,recommended_product_id,nudge_budget}'

curl -fsS "$API/governance/rollout-controls?control_status=active" \
  -H 'X-Saarthi-Demo-Customer: SBI-RUNBOOK-AUDITOR-KILL' -H 'X-Saarthi-Demo-Role: auditor' \
  | tee tmp/demo-evidence/kill-switch-active.json | jq '.'
```

Expected result: the customer request is `rollout_blocked` before profiling, with no recommendation/product and no nudge consumed. Emergency containment is one-person by design; restoration is not. Request recovery as an operator and approve it as a different administrator:

```bash
curl -fsS -X POST "$API/governance/rollout-controls" \
  -H 'X-Saarthi-Demo-Customer: SBI-RUNBOOK-OPS-RECOVERY' -H 'X-Saarthi-Demo-Role: ops' \
  -H 'Content-Type: application/json' \
  -d '{"scope_type":"global","scope_value":"*","mode":"active","cohort_percentage":100,"reason":"Restore synthetic review traffic after containment verification"}' \
  | tee tmp/demo-evidence/recovery-request.json | jq '{status,control}'
export RECOVERY_CONTROL=$(jq -r '.control.control_id' tmp/demo-evidence/recovery-request.json)

curl -fsS -X POST "$API/governance/rollout-controls/$RECOVERY_CONTROL/decision" \
  -H 'X-Saarthi-Demo-Customer: SBI-RUNBOOK-ADMIN-RECOVERY' -H 'X-Saarthi-Demo-Role: admin' \
  -H 'Content-Type: application/json' -d '{"decision":"approved"}' \
  | tee tmp/demo-evidence/recovery-decision.json | jq '{status,control}'
```

Expected result: `approved`, with the new global `active` control effective and the emergency disable superseded. Automated API coverage is in `RolloutApiTests.test_emergency_kill_switch_prevents_profiling_without_requiring_consent`.

## 6. Signed-artifact evidence

The default local server above intentionally has no SBI trust key. Therefore do not submit a made-up signature to it. The repeatable repository evidence uses an ephemeral Ed25519 test key, the real API routes, schema validation, signature verification, independent activation, runtime materialization and metrics:

```bash
python3 -m pytest -q \
  tests/test_governed_artifacts.py::GovernedArtifactApiTests::test_role_gated_signed_activation_updates_catalog_and_metrics
python3 -m pytest -q tests/test_governed_artifacts.py
```

Expected result: the targeted API test passes, followed by all 9 governed-artifact tests. The suite also verifies tamper rejection, untrusted-key rejection, four-eyes activation, restart materialization, version conflicts, concurrency and materialization rollback.

This proves the reference control implementation, not SBI key custody or an SBI-approved artefact release. A live signed-mode rehearsal requires an approved public trust anchor and two signed artefacts (`product_catalog` and `policy_registry`); the private signing key must remain outside Saarthi.

## 7. Evidence matrix

| Review question | Live evidence | Automated evidence | Expected result | Status/limit |
|---|---|---|---|---|
| Is the connected prototype healthy? | `/health`, `/ready`, browser status | `ApiIntegrationTests.test_health_reports_auth_and_migration_state` | Healthy local dependencies; simulated components disclosed | Demonstrated locally only |
| Are all scenario mappings coherent? | Four fixtures above | `DemoJourneyContractTests` | 20 unique cases; 12 actionable, 8 non-actionable; identity chain matches on all actionable cases | Demonstrated on synthetic fixtures |
| Is high-risk content independently reviewed? | Golden journeys 1 and 2 | `ApiIntegrationTests.test_high_risk_recommendation_requires_independent_review` | Pre-review authorization blocked; presentation allowed only after review | Demonstrated; no SBI reviewer directory or KFS feed |
| Is branch-to-digital identity preserved? | Golden journey 3 | `DemoJourneyContractTests.test_all_twenty_routes_and_twelve_action_identity_chains` | `SBI-EDU-DASH13` remains bound through synthetic completion/reconciliation | Demonstrated as mock completion only |
| Does stress suppress selling/action? | Golden journey 4 | Frontend support-action test plus 20-case contract | `support_mode`; no product, rate, recommendation, token or action | Routing demonstrated; RM case creation absent |
| Can consent be revoked and derived data erased narrowly? | Privacy section | `TrustControlTests.test_revocation_and_erasure_are_distinct_operations` | Revocation blocks profiling; bounded erasure retains tombstone/integrity evidence | Demonstrated for local Saarthi data only |
| Is submitted PII kept out of public/audit boundaries? | Masked details and post-erasure audit | `PrivacyMaskingTests` | Supported identifiers replaced recursively before response/event/audit persistence | Demonstrated on test corpus; not enterprise DLP certification |
| Does the UI fail closed on API loss? | API-stop visual check | Frontend explicit-offline-mode test | No silent fallback, action or success | Demonstrated |
| Can an administrator immediately contain traffic? | Kill-switch section | `RolloutApiTests.test_emergency_kill_switch_prevents_profiling_without_requiring_consent` | `rollout_blocked`, no recommendation/budget; four-eyes recovery | Demonstrated locally |
| Are signed configuration updates governed? | Targeted API test | `GovernedArtifactTests` and `GovernedArtifactApiTests` | Signature/tamper checks, independent activation, rollback and durable evidence | Test-harness trust key only; no SBI key/feed |
| Is the audit chain intact? | `/audit/integrity` | high-risk integration and governance tests | `valid=true`; pseudonymous evidence survives eligible-data erasure | Local HMAC ledger, not SBI WORM/SIEM |

## 8. Not demonstrated / not SBI integrated

The following must stay in the SBI-dependent backlog and must not be implied by the walkthrough:

1. InnoHub onboarding, sandbox credentials, certificates, approved OpenAPI/message schemas or any confirmed SBI endpoint name/path.
2. SBI/YONO OIDC tenant integration, customer authentication, employee roles, step-up authentication, device binding or fraud controls.
3. Live CBS, cards, CRM, branch, consent-registry, product catalogue, rate, KFS, eligibility, fulfilment, reversal, notification, case or outcome connections.
4. A live financial transaction, deposit opening, loan application, tax payment, fund transfer, dashboard activation or customer notification. All fulfilment references here are synthetic.
5. RM/case creation from the financial-stress support card. This exact fourth golden journey currently ends safely at non-actionable support presentation.
6. A trained AI classifier, uplift/ranking model, production LLM or population-level performance/fairness result. The current champion is a deterministic 20-fixture rules contract.
7. SBI signing-key custody or a live signed product/policy release. Signed-artifact evidence uses an ephemeral test key.
8. Representative SBI data, production monitoring thresholds, protected-attribute fairness analysis, model-risk approval or measured customer benefit.
9. SBI-scale performance, availability, HA/DR, backup/restore, WORM/SIEM, KMS/HSM, VAPT, DPIA, legal/compliance approval, records-retention approval or operating ownership.
10. Verified Docker/Compose infrastructure in an SBI-like landing zone. Local single-process evidence is not a capacity or resilience result.

## 9. Reviewer sign-off record

Record results without copying raw tokens, signatures or personal data into the review pack:

| Item | Pass/fail | Evidence file/reference | Reviewer note |
|---|---|---|---|
| Clean health/readiness with simulated-component disclosure |  |  |  |
| Golden journey 1: reviewed debt comparison |  |  |  |
| Golden journey 2: reviewed senior-deposit fixture |  |  |  |
| Golden journey 3: low-risk branch-to-digital fixture |  |  |  |
| Golden journey 4: support-only/no action |  |  |  |
| Consent, revocation and bounded erasure |  |  |  |
| API-loss fail closed |  |  |  |
| Kill switch and independent recovery |  |  |  |
| Signed-artifact test evidence |  |  |  |
| Audit integrity |  |  |  |
| Unsupported/SBI-dependent claims acknowledged |  |  |  |

The demo may be accepted for technical review when the applicable rows pass and every limitation remains visible. It must not be labelled SBI-integrated, pilot-ready or production-ready on the strength of this runbook.
