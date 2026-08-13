import json
import time
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen


SEGMENT_DEFAULTS = {
    "corporate": (100000.0, 25000.0, []),
    "pensioner": (45000.0, 10000.0, []),
    "sme": (150000.0, 50000.0, []),
    "stressed": (50000.0, 35000.0, ["financial_stress"]),
    "student": (20000.0, 2000.0, []),
}

DEMO_SEGMENTS = {
    "SBI-772910": "corporate",
    "SBI-881234": "pensioner",
    "SBI-223456": "sme",
    "SBI-991877": "stressed",
    "SBI-554321": "student",
}


class SyntheticCustomerContextProvider:
    """Development-only, explicitly synthetic source for deterministic journeys."""

    mode = "synthetic"

    def get_context(self, customer_id, segment_hint=None):
        segment = DEMO_SEGMENTS.get(customer_id, segment_hint or "corporate")
        income, obligations, flags = SEGMENT_DEFAULTS.get(segment, SEGMENT_DEFAULTS["corporate"])
        return {
            "customer_segment": segment,
            "monthly_income": income,
            "monthly_obligations": obligations,
            "vulnerability_flags": list(flags),
            "verification_status": "synthetic_verified",
            "source_system": "saarthi-synthetic-context",
            "as_of": datetime.now(timezone.utc).isoformat(),
            "context_version": "synthetic-2026.08.1",
        }

    def health(self):
        return {"name": "customer_context", "mode": self.mode, "ready": True, "detail": "development-only synthetic records"}


class SbiCustomerContextClient:
    """Fail-closed adapter for an SBI-owned customer decision-context API."""

    mode = "sbi_api"

    def __init__(self, base_url, service_token, timeout_seconds=3.0):
        if not base_url or not service_token:
            raise RuntimeError("SBI customer context URL and service token are required")
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.timeout_seconds = timeout_seconds

    def _request(self, path):
        request = Request(
            f"{self.base_url}{path}",
            headers={"Authorization": f"Bearer {self.service_token}", "Accept": "application/json"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read())

    def get_context(self, customer_id, segment_hint=None):
        del segment_hint
        payload = self._request(f"/v1/customers/{customer_id}/decision-context")
        required = {
            "customer_segment", "monthly_income", "monthly_obligations", "vulnerability_flags",
            "verification_status", "source_system", "as_of", "context_version",
        }
        if not required.issubset(payload):
            raise RuntimeError("SBI customer context response is incomplete")
        if payload["verification_status"] != "verified":
            raise RuntimeError("SBI customer context is not verified")
        return payload

    def health(self):
        try:
            started = time.time()
            self._request("/health")
            return {"name": "customer_context", "mode": self.mode, "ready": True, "detail": f"{int((time.time() - started) * 1000)}ms"}
        except (OSError, URLError, ValueError, RuntimeError) as error:
            return {"name": "customer_context", "mode": self.mode, "ready": False, "detail": type(error).__name__}


def create_customer_context_provider(settings):
    if settings.customer_context_mode == "sbi_api":
        return SbiCustomerContextClient(settings.customer_context_url, settings.customer_context_token)
    return SyntheticCustomerContextProvider()
