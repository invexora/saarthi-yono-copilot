import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.database import DatabaseManager
from backend.settings import Settings
from backend.customer_context import SbiCustomerContextClient


class FixedContextProvider:
    def __init__(self, *, segment="corporate", income=100000, obligations=25000, flags=None):
        self.segment = segment
        self.income = income
        self.obligations = obligations
        self.flags = flags or []

    def get_context(self, customer_id, segment_hint=None):
        return {
            "customer_segment": self.segment,
            "monthly_income": self.income,
            "monthly_obligations": self.obligations,
            "vulnerability_flags": self.flags,
            "verification_status": "verified",
            "source_system": "test-cbs",
            "as_of": datetime.now(timezone.utc).isoformat(),
            "context_version": "test-context-v1",
        }

    def health(self):
        return {"name": "customer_context", "mode": "test", "ready": True, "detail": "fixed"}


class CustomerContextIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.temp_dir.name) / "context.db"))
        self.settings = Settings(
            db_path=self.db.db_path,
            auth_mode="development",
            decision_secret="context-integration-decision-secret-32-chars",
            allowed_origins=("http://localhost:8000",),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def headers(customer_id, key=None):
        result = {"X-Saarthi-Demo-Customer": customer_id, "X-Saarthi-Demo-Role": "customer"}
        if key:
            result["Idempotency-Key"] = key
        return result

    def _grant(self, client, customer_id):
        client.post("/api/v1/consent/grant", json={"purpose": "personalization"}, headers=self.headers(customer_id))

    def test_known_demo_identity_cannot_forge_segment(self):
        customer_id = "SBI-554321"
        with TestClient(create_app(self.settings, self.db)) as client:
            self._grant(client, customer_id)
            response = client.post(
                "/api/v1/orchestrate",
                json={"signal": "Recurring credit card interest", "segment": "corporate"},
                headers=self.headers(customer_id, "segment-binding-001"),
            )

        payload = response.json()
        self.assertEqual(payload["customer_segment"], "student")
        self.assertEqual(payload["recommended_product_id"], "SBI-SIP-MF11")
        self.assertIn("SERVER_SEGMENT_BOUND", payload["reason_codes"])
        self.assertNotIn("monthly_income", response.text)
        self.assertNotIn("monthly_obligations", response.text)

    def test_affordability_failure_rejects_offer_without_budget_use(self):
        customer_id = "SBI-AFFORD-001"
        provider = FixedContextProvider(income=20000, obligations=15000)
        with TestClient(create_app(self.settings, self.db, customer_context_provider=provider)) as client:
            self._grant(client, customer_id)
            response = client.post(
                "/api/v1/orchestrate",
                json={"signal": "Recurring credit card interest", "segment": "corporate"},
                headers=self.headers(customer_id, "affordability-001"),
            )

        payload = response.json()
        self.assertEqual(payload["decision_outcome"], "rejected")
        self.assertIn("AFFORDABILITY_LIMIT_EXCEEDED", payload["reason_codes"])
        self.assertIsNone(payload["recommendation_id"])
        self.assertEqual(self.db.get_nudge_budget_status(customer_id)["used"], 0)

    def test_verified_vulnerability_suppresses_promotional_offer(self):
        customer_id = "SBI-VULNERABLE-001"
        provider = FixedContextProvider(flags=["financial_stress"])
        with TestClient(create_app(self.settings, self.db, customer_context_provider=provider)) as client:
            self._grant(client, customer_id)
            response = client.post(
                "/api/v1/orchestrate",
                json={"signal": "Recurring credit card interest", "segment": "corporate"},
                headers=self.headers(customer_id, "vulnerability-001"),
            )

        payload = response.json()
        self.assertEqual(payload["decision_outcome"], "support_only")
        self.assertEqual(payload["delivery_mode"], "support_mode")
        self.assertIsNone(payload["recommendation_id"])
        self.assertEqual(self.db.get_nudge_budget_status(customer_id)["used"], 0)

    def test_customer_context_outage_fails_closed_and_releases_retry_key(self):
        class OutageProvider:
            calls = 0

            def get_context(self, *_):
                self.calls += 1
                raise ConnectionError("offline")

            def health(self):
                return {"name": "customer_context", "mode": "test", "ready": True, "detail": "flaky"}

        customer_id = "SBI-CONTEXT-DOWN"
        provider = OutageProvider()
        with TestClient(create_app(self.settings, self.db, customer_context_provider=provider)) as client:
            self._grant(client, customer_id)
            responses = [client.post(
                "/api/v1/orchestrate",
                json={"signal": "Branch cash deposit", "segment": "corporate"},
                headers=self.headers(customer_id, "context-outage-001"),
            ) for _ in range(2)]

        self.assertEqual([response.status_code for response in responses], [503, 503])
        self.assertEqual(provider.calls, 2)


class SbiCustomerContextClientTests(unittest.TestCase):
    def test_adapter_requires_verified_complete_response_and_ignores_hint(self):
        payload = {
            "customer_segment": "pensioner",
            "monthly_income": 50000,
            "monthly_obligations": 10000,
            "vulnerability_flags": [],
            "verification_status": "verified",
            "source_system": "sbi-cbs-read-model",
            "as_of": datetime.now(timezone.utc).isoformat(),
            "context_version": "cbs-v4",
        }

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                import json
                return json.dumps(payload).encode()

        client = SbiCustomerContextClient("https://internal.example", "service-token")
        with patch("backend.customer_context.urlopen", return_value=Response()) as request:
            result = client.get_context("SBI-REMOTE-001", "corporate")

        self.assertEqual(result["customer_segment"], "pensioner")
        sent_request = request.call_args.args[0]
        self.assertEqual(sent_request.headers["Authorization"], "Bearer service-token")


if __name__ == "__main__":
    unittest.main()
