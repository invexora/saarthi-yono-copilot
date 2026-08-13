import json
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode


class SyntheticFulfillmentClient:
    """Development-only deterministic fulfilment simulator."""

    mode = "synthetic"

    def execute(self, recommendation, customer_id, idempotency_key):
        return {
            "status": "completed",
            "reference": f"SYN-{uuid.uuid5(uuid.NAMESPACE_URL, idempotency_key)}",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "provider": "synthetic-fulfillment",
        }

    def get_status(self, fulfillment_reference, recommendation_id):
        expected_reference = f"SYN-{uuid.uuid5(uuid.NAMESPACE_URL, recommendation_id)}"
        return {
            "status": "completed",
            "reference": expected_reference,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "provider": "synthetic-fulfillment",
        }

    def health(self):
        return {"name": "fulfillment", "mode": self.mode, "ready": True, "detail": "development-only simulator"}


class SbiFulfillmentClient:
    """Idempotent adapter for an SBI-owned product fulfilment gateway."""

    mode = "sbi_api"

    def __init__(self, base_url, service_token, timeout_seconds=5.0):
        if not base_url or not service_token:
            raise RuntimeError("SBI fulfilment URL and service token are required")
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

    def execute(self, recommendation, customer_id, idempotency_key):
        result = self._request(
            "/v1/actions/execute",
            method="POST",
            idempotency_key=idempotency_key,
            payload={
                "recommendationId": recommendation["recommendation_id"],
                "customerId": customer_id,
                "productId": recommendation["product_id"],
            },
        )
        if result.get("status") != "completed" or not result.get("reference"):
            raise RuntimeError("SBI fulfilment did not confirm completion")
        return {
            "status": "completed",
            "reference": result["reference"],
            "completed_at": result.get("completed_at"),
            "provider": result.get("provider", "sbi-fulfillment"),
        }

    def get_status(self, fulfillment_reference, recommendation_id):
        query = urlencode({
            "reference": fulfillment_reference,
            "recommendationId": recommendation_id,
        })
        result = self._request(f"/v1/actions/status?{query}")
        provider_status = result.get("status")
        if provider_status not in {"completed", "pending", "processing", "failed", "reversed", "not_found"}:
            raise RuntimeError("SBI fulfilment returned an unsupported reconciliation status")
        if provider_status == "completed" and not result.get("reference"):
            raise RuntimeError("SBI fulfilment status omitted the completion reference")
        return result

    def health(self):
        try:
            self._request("/health")
            return {"name": "fulfillment", "mode": self.mode, "ready": True, "detail": "connected"}
        except (HTTPError, URLError, OSError, ValueError, RuntimeError) as error:
            return {"name": "fulfillment", "mode": self.mode, "ready": False, "detail": type(error).__name__}


def create_fulfillment_client(settings):
    if settings.fulfillment_mode == "sbi_api":
        return SbiFulfillmentClient(settings.fulfillment_url, settings.fulfillment_token)
    return SyntheticFulfillmentClient()
