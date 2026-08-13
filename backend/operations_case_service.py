import hashlib
import json
import uuid

from backend.case_management import CASE_STATUSES
from backend.guardrails import InputGuardian


class OperationsCaseService:
    PUBLIC_FIELDS = (
        "case_id", "recommendation_id", "status", "safe_summary",
        "requested_at", "approved_at", "attempt_count",
        "external_case_reference", "provider_status", "last_synced_at",
        "next_action_at", "last_error_code",
    )

    def __init__(self, database, client, audit_ledger=None, retry_seconds=60, sync_interval_seconds=300):
        self.database = database
        self.client = client
        self.audit_ledger = audit_ledger
        self.retry_seconds = retry_seconds
        self.sync_interval_seconds = sync_interval_seconds
        self.input_guardian = InputGuardian()

    @classmethod
    def _public(cls, row):
        if not row:
            return None
        return {field: row.get(field) for field in cls.PUBLIC_FIELDS}

    @staticmethod
    def _normalized_provider_result(result, expected_reference=None):
        if not isinstance(result, dict):
            raise RuntimeError("Case-management response must be an object")
        status = result.get("status")
        reference = result.get("reference")
        if status not in CASE_STATUSES or not isinstance(reference, str) or not reference or len(reference) > 200:
            raise RuntimeError("Case-management response violated the approved contract")
        if expected_reference and reference != expected_reference:
            raise RuntimeError("Case-management reference changed during synchronization")
        return {
            "status": status,
            "reference": reference,
            "updated_at": result.get("updated_at"),
            "provider": result.get("provider"),
        }

    @staticmethod
    def _digest(result):
        canonical = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def list(self, case_status=None, limit=100):
        return [self._public(row) for row in self.database.list_operations_cases(case_status, limit)]

    def request(self, recommendation_id, requester_ref, summary):
        case_id = str(uuid.uuid4())
        safe_summary = self.input_guardian.mask_pii(summary)
        case, request_status = self.database.create_operations_case(
            case_id, recommendation_id, requester_ref, safe_summary,
        )
        if self.audit_ledger and request_status == "requested":
            self.audit_ledger.append("system:operations-case", "operations_case_requested", {
                "case_id": case_id,
                "recommendation_id": recommendation_id,
                "requester_ref": requester_ref,
            })
        return {"status": request_status, "case": self._public(case)}

    def approve(self, case_id, approver_ref):
        case, approval_status = self.database.approve_operations_case(case_id, approver_ref)
        if self.audit_ledger and approval_status == "approved":
            self.audit_ledger.append("system:operations-case", "operations_case_approved", {
                "case_id": case_id,
                "approver_ref": approver_ref,
            })
        return {"status": approval_status, "case": self._public(case)}

    def submit(self, case_id):
        case, claim_status = self.database.claim_operations_case_submission(case_id)
        if claim_status != "claimed":
            return {"status": claim_status, "case": self._public(case)}
        try:
            provider_result = self._normalized_provider_result(
                self.client.create_case(case, case_id),
            )
            completed = self.database.complete_operations_case_submission(
                case_id,
                provider_result["status"],
                provider_result["reference"],
                self._digest(provider_result),
                self.sync_interval_seconds,
            )
            if not completed:
                return {"status": "claim_lost", "case": None}
        except Exception as error:
            self.database.fail_operations_case_action(
                case_id, "submit", type(error).__name__, self.retry_seconds,
            )
            return {
                "status": "dependency_unavailable",
                "error_code": type(error).__name__,
                "case": self._public(self.database.get_operations_case(case_id)),
            }
        if self.audit_ledger:
            self.audit_ledger.append("system:operations-case", "operations_case_submitted", {
                "case_id": case_id,
                "external_case_reference": provider_result["reference"],
                "provider_status": provider_result["status"],
            })
        return {"status": "submitted", "case": self._public(completed)}

    def sync(self, case_id):
        case, claim_status = self.database.claim_operations_case_sync(case_id)
        if claim_status != "claimed":
            return {"status": claim_status, "case": self._public(case)}
        try:
            provider_result = self._normalized_provider_result(
                self.client.get_status(case["external_case_reference"], case_id),
                expected_reference=case["external_case_reference"],
            )
            completed = self.database.complete_operations_case_sync(
                case_id,
                provider_result["status"],
                self._digest(provider_result),
                self.sync_interval_seconds,
            )
            if not completed:
                return {"status": "claim_lost", "case": None}
        except Exception as error:
            self.database.fail_operations_case_action(
                case_id, "sync", type(error).__name__, self.retry_seconds,
            )
            return {
                "status": "dependency_unavailable",
                "error_code": type(error).__name__,
                "case": self._public(self.database.get_operations_case(case_id)),
            }
        if self.audit_ledger and provider_result["status"] in {"resolved", "closed", "rejected"}:
            self.audit_ledger.append("system:operations-case", "operations_case_terminal_status", {
                "case_id": case_id,
                "provider_status": provider_result["status"],
            })
        return {"status": "synchronized", "case": self._public(completed)}

    def run_action(self, case_id, action):
        if action == "submit":
            return self.submit(case_id)
        if action == "sync":
            return self.sync(case_id)
        raise ValueError("Unsupported operations case action")
