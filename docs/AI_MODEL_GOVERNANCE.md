# Saarthi AI and Model Governance

Status: pilot-design baseline, 13 August 2026. This document does not claim SBI model approval or production validation.

## Current truth

Saarthi does not currently contain a trained customer-scoring model or a production LLM. The executable champion is the deterministic, versioned detector `saarthi-signal-rules:2026.08.3` followed by policy, consent, affordability, vulnerability and rollout gates.

The integrated demo contract contains 20 synthetic journeys: five personas by four signal families. The governance endpoint reports the executable 20-row regression result and its limitation. Passing this corpus proves demo-contract consistency only; it does not establish population accuracy, calibration, fairness, drift resistance or customer benefit.

## Governed decision cascade

1. Accept a purpose-authorized event and resolve the customer through SBI-controlled identity.
2. Convert source data to a versioned, privacy-minimized feature contract.
3. Detect friction, opportunity, life-event or stress, with confidence and abstention.
4. Apply deterministic eligibility, affordability, suitability, vulnerability and prohibited-action rules.
5. Rank only the remaining eligible actions using customer-benefit evidence.
6. Withhold uncertainty, credit, investment and vulnerable-customer cases for support or human review.
7. Generate customer wording only from versioned product, price, KFS and policy evidence.
8. Require action-specific consent and step-up authentication before a downstream adapter is invoked.
9. Reconcile the downstream outcome and feed privacy-minimized observations back into monitoring.

An LLM may later explain an approved decision in controlled multilingual language. It must not determine eligibility, pricing, sanction, KYC status, consent, vulnerability handling or money movement.

## Model inventory

| Component | Current status | Production requirement |
|---|---|---|
| Signal detector | Versioned deterministic rules; 20 synthetic contract rows | SBI-approved representative dataset, calibrated probability model or approved rules, abstention, model-risk validation |
| Eligibility and safety | Deterministic prototype policy | Signed SBI product/policy artifacts and independent control-owner approval |
| Next-best action | Fixed graph lookup | Outcome-labelled uplift or incremental-benefit model after eligibility; customer benefit and harm in objective |
| Explanation | Approved template strings | SBI-hosted controlled templates or LLM grounded only in signed evidence |
| Outcome monitoring | Aggregate operational segments and minimum samples | SBI-approved definitions, feeds, thresholds, protected-attribute governance and remediation ownership |

## Required SBI data before training

The data owner must approve purpose, fields, observation window, labels, retention and access before extraction. Candidate inputs are engineered aggregates such as counts, ratios, trends, volatility, recency and categorical flags. Do not train on raw PAN, Aadhaar, names, contact data, full account or card identifiers, free transaction narration, documents or authentication secrets.

Required label families include:

- verified signal occurrence and time;
- action eligibility at decision time;
- offer exposure, acceptance and fulfilment;
- measurable customer benefit;
- false-positive, complaint, opt-out, hardship, support escalation and other harm outcomes;
- channel, policy and model version used for the decision.

Synthetic personas are suitable for contract and safety testing, not model fitting or production performance claims.

## Evaluation and approval gates

Every deployable model version needs:

- immutable model, feature-schema, dataset and evaluation identifiers;
- training/validation time windows and leakage analysis;
- precision, recall, calibration and abstention by signal and approved operating segment;
- cost-weighted false-positive and false-negative analysis, with stress/vulnerability harm treated separately;
- stability and drift checks across time, channel and relevant segments;
- uplift and customer-benefit measurement for next-best action, not conversion alone;
- disparate-outcome and protected-class review under an SBI-approved lawful attribute process;
- robustness, privacy, explainability, human-override and failure-mode evidence;
- independent model-risk, product, compliance, privacy and security approvals.

Numeric thresholds are not hard-coded here because SBI control owners must set them from risk appetite and representative evidence. Unknown, stale, out-of-distribution or below-threshold cases must abstain or route to review, never default to a promotional action.

## Runtime controls already represented in the prototype

- model ID, version, feature-schema version, confidence, reason codes and input digest on every classification;
- executable evaluation envelope exposed to governance roles;
- exact model-version rollout controls, shadow mode, deterministic cohorts and emergency disable;
- re-checks before presentation, authorization and fulfilment;
- action-specific consent, single-use authorization and idempotent fulfilment;
- aggregate outcome and harm monitoring without a customer-level operator listing;
- support-only routing for vulnerable or stressed journeys.

These are reference controls. Production still needs SBI identity, data, policy, model registry, KMS/HSM, WORM audit, monitoring and incident-management services.

## Change lifecycle

1. Register the proposed dataset, features, model and intended-use statement.
2. Reproduce offline evaluation and independent validation.
3. Obtain four-eyes model and policy approval.
4. Deploy in non-customer-visible shadow mode.
5. Compare benefit, harm, calibration and drift against the champion.
6. Expand through deterministic cohorts only after approval.
7. Monitor continuously and retain evidence for every version.
8. Disable the narrowest affected scope immediately when a safety or data-quality threshold is breached.
9. Roll back without changing historical decision evidence.

## Pilot exit criteria

- All 20 demo contracts remain green and displayed product identity matches authorization and fulfilment identity.
- The SBI field and label inventory is approved; no raw identifier reaches a model, prompt, response, trace or analytics record.
- At least one representative SBI holdout evaluation and one shadow evaluation are independently reviewed.
- Product, policy, rate and KFS inputs are versioned SBI-owned evidence rather than demo fixtures.
- Human-review ownership, SLAs, customer recourse and kill-switch drills are approved and tested.
- No production claim is made until privacy, security, legal, records, outsourcing and model-risk approvals are complete.
