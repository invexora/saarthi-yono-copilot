# Saarthi Operations Runbook

## Rollout safety controls

Use the narrowest scope that contains the risk: exact model version, product, signal, segment, channel, then global. Model scope values must exactly match `model_id:model_version` from the governed signal-model evidence. During an active customer-safety incident, an administrator may call `/api/v1/governance/rollout-controls/emergency-disable`; this takes effect immediately and is recorded in the integrity ledger. Confirm the active control through the list endpoint and verify `saarthi_rollout_controls_disabled` plus a known synthetic journey before declaring containment.

Emergency disable is intentionally one-person for rapid containment. It must never be used to restore activity. Recovery requires an operator or administrator to request an `active` control and a different administrator to approve it. Prefer a conservative cohort percentage, observe shadow evidence and operational metrics, then use additional four-eyes changes to expand exposure.

For planned releases, begin with `shadow` or an `active` control with a small cohort. Shadow decisions must have no recommendation ID, no customer-visible product/rate/policy fields, and no nudge-budget increment. Alert when pending approvals age beyond the governance SLA, when an unexpected disable is active, or when a partial/shadow control remains beyond its approved window. Never edit rollout rows directly; supersession and audit evidence depend on the API transaction.

## Outcome-monitoring alerts

Alert when `saarthi_monitoring_alerts`, `saarthi_outcome_harms`, or `saarthi_outcome_complaints` changes unexpectedly. Retrieve the aggregate report for segment, signal, and product dimensions; do not attempt to identify individual customers from the monitoring view.

1. Confirm the report names the currently approved policy and that the affected group meets its minimum sample size.
2. Validate source-feed freshness and deduplication before treating the rate as a behavioral change.
3. Compare the affected signal/product across other operational segments and windows.
4. Apply the narrowest rollout control if customer harm may be continuing; use emergency disable for active safety incidents.
5. Escalate to SBI model risk, product, compliance, and customer-protection owners under the approved procedure.
6. Record the investigation and remediation outside this aggregate service; changing a threshold is not incident resolution.

Never label an operational segment alert as protected-class discrimination evidence by itself. Protected-class analysis requires SBI legal authorization, approved attributes, privacy controls, statistical methodology, and independent review. Never lower thresholds or minimum samples solely to clear an alert.

## Signal-detector degradation or model change

If readiness reports `signal_detection` unavailable, confirm the SBI detector health and workload identity before retrying traffic. Orchestration fails closed and does not consume promotional budget during the outage. Do not bypass the detector or switch production to the local rules implementation.

Before accepting a new model version, verify `/api/v1/governance/signal-model` shows the SBI-approved evaluation, supported feature schema, adequate per-category support, and documented limitations. Start with a model-scoped shadow or conservative cohort control, then compare outcome-monitoring reports before expansion. Low-confidence or input-binding failures indicate a contract or routing problem, not a reason to reduce the confidence threshold without model-risk approval.

## Signed product and policy artifacts

Before requesting an artifact, generate the canonical envelope with exactly `artifactType`, `version`, and `payload`, then sign that byte string with the current SBI Ed25519 signing key. The submitted `signing_key_id` must match the configured trust anchor. Keep the private key and transport outside Saarthi; the service is only the verifier and activation workflow.

Use `/api/v1/governance/artifacts` to submit a product catalog or policy registry. Verify the returned digest against the release record, then have a different administrator approve it. During approval the artifact enters `materializing`; a second approval attempt should receive `materialization_in_progress`. If runtime application fails, readiness remains on the prior active feed and the artifact returns to `pending` for investigation. Do not update `governed_artifacts` rows directly, because supersession, rollback, and the audit ledger depend on the API transaction.

After approval, confirm `/api/v1/ready` and the `saarthi_governed_artifacts_active` metric. If a deployment restarts in signed mode without both active artifact types, keep it out of service until the missing signed feed is approved or the SBI release manager explicitly rolls forward with a corrected artifact. Trust-key rotation requires an SBI-approved overlap plan: deploy the new public key configuration, submit new artifacts under the new key ID, approve them, and only then retire the old signing key.

## Event delivery

Alert when `saarthi_event_active_consumers` is zero, stream lag or pending entries exceed the configured SLO, or `saarthi_event_dead_letters` is non-zero. Confirm `/api/v1/ready`, then inspect `/api/v1/events/status`. Dead-letter metadata is safe for the operations console; raw stream payloads must remain restricted to approved diagnostic access.

An administrator may replay a dead letter with a unique `Idempotency-Key`. Repeating the same request is safe. Investigate the recorded error class before replaying a contract-invalid event.

## Fulfilment reconciliation

Alert whenever `saarthi_fulfillment_reconciliation_mismatches` is non-zero or the pending gauge breaches the agreed age/volume threshold.

1. List `mismatch` records through `/api/v1/fulfillment/reconciliations`.
2. Compare the recommendation ID and expected provider reference with the SBI fulfilment/settlement system using approved internal tooling.
3. Rerun reconciliation after the provider record is corrected or becomes available.
4. If it still differs, request an operations case with a non-sensitive investigation summary.
5. A different administrator reviews and approves the case. The requesting principal cannot approve its own request.
6. The worker submits the approved case with the internal case ID as the idempotency key and continuously synchronizes its SBI status.
7. An administrator may separately acknowledge the reconciliation escalation. Acknowledgement does not clear the mismatch metric.

Alert on pending case approvals, submission/synchronization retries, and open case age. Provider `resolved` or `closed` status updates the case record but does not automatically mark the underlying reconciliation as matched. Rerun reconciliation against the fulfilment system before treating the discrepancy as cleared.

Never manually change the recommendation or reconciliation database row. Never report a reversal as resolved merely because it was acknowledged. Product-specific refunds, reversals, customer communication, or ledger corrections require SBI-approved compensating procedures and four-eyes authorization outside this reference implementation.

## Dependency recovery

Provider outages place reconciliation into `retry` without losing the expected reference. The worker automatically checks due retries. A worker restart can recover stale event deliveries and stale reconciliation claims. If Redis mode has no live heartbeat, API readiness becomes unhealthy to prevent a partially operational deployment from appearing ready.
