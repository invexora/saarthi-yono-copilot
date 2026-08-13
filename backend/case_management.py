import json
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


CASE_STATUSES = {"open", "in_progress", "resolved", "closed", "rejected"}


class SyntheticCaseManagementClient:
    mode = "synthetic"

    def create_case(self, case, idempotency_key):
        return {
            "status": "open",
            "reference": f"SYN-CASE-{uuid.uuid5(uuid.NAMESPACE_URL, idempotency_key)}",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "provider": "synthetic-case-management",
        }

    def get_status(self, external_reference, case_id):
        return {
            "status": "open",
            "reference": external_reference,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "provider": "synthetic-case-management",
        }

    def health(self):
        return {"name": "case_management", "mode": self.mode, "ready": True, "detail": "development-only simulator"}


class SbiCaseManagementClient:
    """Data-minimized adapter for an SBI-owned incident/case platform."""

    mode = "sbi_api"

    def __init__(self, base_url, service_token, timeout_seconds=5.0):
        if not base_url or not service_token:
            raise RuntimeError("SBI case-management URL and service token are required")
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.timeout_seconds = timeout_seconds

    def _request(self, path, *, method="GET", payload=None, idempotency_key=None):
        headers = {"Authorization": f"Bearer {self.service_token}", "Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, separators=(",", ":")).encode()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read())

    @staticmethod
    def _normalize(result):
        if not isinstance(result, dict):
            raise RuntimeError("SBI case response must be an object")
        status = result.get("status")
        reference = result.get("reference")
        if status not in CASE_STATUSES or not isinstance(reference, str) or not reference or len(reference) > 200:
            raise RuntimeError("SBI case response did not satisfy the approved contract")
        return {
            "status": status,
            "reference": reference,
            "updated_at": result.get("updated_at"),
            "provider": result.get("provider", "sbi-case-management"),
        }

    def create_case(self, case, idempotency_key):
        result = self._request(
            "/v1/cases",
            method="POST",
            idempotency_key=idempotency_key,
            payload={
                "caseId": case["case_id"],
                "recommendationId": case["recommendation_id"],
                "fulfillmentReference": case["fulfillment_reference"],
                "category": "FULFILLMENT_RECONCILIATION_MISMATCH",
                "priority": "HIGH",
                "summary": case["safe_summary"],
            },
        )
        return self._normalize(result)

    def get_status(self, external_reference, case_id):
        query = urlencode({"reference": external_reference, "caseId": case_id})
        return self._normalize(self._request(f"/v1/cases/status?{query}"))

    def health(self):
        try:
            self._request("/health")
            return {"name": "case_management", "mode": self.mode, "ready": True, "detail": "connected"}
        except (HTTPError, URLError, OSError, ValueError, RuntimeError) as error:
            return {"name": "case_management", "mode": self.mode, "ready": False, "detail": type(error).__name__}


def create_case_management_client(settings):
    if settings.case_management_mode == "sbi_api":
        return SbiCaseManagementClient(settings.case_management_url, settings.case_management_token)
    return SyntheticCaseManagementClient()
