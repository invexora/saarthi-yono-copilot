import hashlib
import json

from backend.guardrails import InputGuardian


class FulfillmentReconciliationService:
    PROVIDER_STATUSES = {"completed", "pending", "processing", "failed", "reversed", "not_found"}
    PUBLIC_FIELDS = (
        "recommendation_id", "fulfillment_reference", "status", "provider_status",
        "attempt_count", "created_at", "last_checked_at", "next_check_at",
        "last_error_code", "acknowledged_at", "acknowledgement_note",
    )

    def __init__(self, database, client, audit_ledger=None, retry_seconds=60):
        self.database = database
        self.client = client
        self.audit_ledger = audit_ledger
        self.retry_seconds = retry_seconds
        self.input_guardian = InputGuardian()

    @classmethod
    def _public(cls, row):
        if not row:
            return None
        return {field: row.get(field) for field in cls.PUBLIC_FIELDS}

    def list(self, reconciliation_status=None, limit=100):
        return [
            self._public(row)
            for row in self.database.list_fulfillment_reconciliations(reconciliation_status, limit)
        ]

    def reconcile(self, recommendation_id):
        claim, claim_status = self.database.claim_fulfillment_reconciliation(recommendation_id)
        if claim_status != "claimed":
            return {"status": claim_status, "reconciliation": self._public(claim)}

        try:
            provider_result = self.client.get_status(
                claim["fulfillment_reference"], recommendation_id,
            )
            if not isinstance(provider_result, dict):
                raise RuntimeError("Fulfilment status response must be an object")
            provider_status = provider_result.get("status")
            if provider_status not in self.PROVIDER_STATUSES:
                raise RuntimeError("Unsupported fulfilment reconciliation status")
            provider_reference = provider_result.get("reference")
            if provider_status == "completed" and not provider_reference:
                raise RuntimeError("Completed fulfilment status requires a reference")
            canonical = json.dumps(
                provider_result, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            )
            reconciliation, outcome = self.database.complete_fulfillment_reconciliation(
                recommendation_id,
                provider_status,
                provider_reference,
                hashlib.sha256(canonical.encode()).hexdigest(),
                self.retry_seconds,
            )
        except Exception as error:
            self.database.fail_fulfillment_reconciliation(
                recommendation_id, type(error).__name__, self.retry_seconds,
            )
            current = self.database.get_fulfillment_reconciliation(recommendation_id)
            return {
                "status": "dependency_unavailable",
                "error_code": type(error).__name__,
                "reconciliation": self._public(current),
            }

        if self.audit_ledger and outcome in {"matched", "mismatch"}:
            self.audit_ledger.append(claim["customer_id"], f"fulfillment_reconciliation_{outcome}", {
                "recommendation_id": recommendation_id,
                "fulfillment_reference": claim["fulfillment_reference"],
                "provider_status": provider_status,
                "attempt": reconciliation["attempt_count"],
            })
        return {"status": outcome, "reconciliation": self._public(reconciliation)}

    def acknowledge_mismatch(self, recommendation_id, operator_ref, note):
        safe_note = self.input_guardian.mask_pii(note)
        reconciliation = self.database.acknowledge_fulfillment_mismatch(
            recommendation_id, operator_ref, safe_note,
        )
        if not reconciliation:
            return {"status": "not_found_or_not_mismatch", "reconciliation": None}
        if self.audit_ledger:
            # The retained ledger stores only a pseudonymous operator reference.
            self.audit_ledger.append("system:fulfillment-reconciliation", "fulfillment_mismatch_acknowledged", {
                "recommendation_id": recommendation_id,
                "operator_ref": operator_ref,
            })
        return {"status": "acknowledged", "reconciliation": self._public(reconciliation)}
