import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.case_management import SyntheticCaseManagementClient
from backend.database import DatabaseManager
from backend.fulfillment import SyntheticFulfillmentClient
from backend.settings import Settings


class RecordingSyntheticFulfillmentClient(SyntheticFulfillmentClient):
    def __init__(self):
        self.execute_calls = []
        self.status_calls = []

    def execute(self, recommendation, customer_id, idempotency_key):
        self.execute_calls.append({
            "recommendation_id": recommendation["recommendation_id"],
            "product_id": recommendation["product_id"],
            "customer_id": customer_id,
            "idempotency_key": idempotency_key,
        })
        return super().execute(recommendation, customer_id, idempotency_key)

    def get_status(self, fulfillment_reference, recommendation_id):
        self.status_calls.append({
            "recommendation_id": recommendation_id,
            "fulfillment_reference": fulfillment_reference,
        })
        return super().get_status(fulfillment_reference, recommendation_id)


class RecordingSyntheticCaseClient(SyntheticCaseManagementClient):
    def __init__(self):
        self.create_calls = []
        self.status_calls = []

    def create_case(self, case, idempotency_key):
        self.create_calls.append({"case": dict(case), "idempotency_key": idempotency_key})
        return super().create_case(case, idempotency_key)

    def get_status(self, external_reference, case_id):
        self.status_calls.append({
            "external_reference": external_reference,
            "case_id": case_id,
        })
        return super().get_status(external_reference, case_id)


class GoldenJourneyTests(unittest.TestCase):
    """Repeatable SBI-review demo proofs using development-only providers."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "golden-journeys.db")
        self.database = DatabaseManager(self.db_path)
        self.fulfillment = RecordingSyntheticFulfillmentClient()
        self.cases = RecordingSyntheticCaseClient()
        settings = Settings(
            db_path=self.db_path,
            auth_mode="development",
            decision_secret="golden-journey-decision-secret-32-chars",
            audit_secret="golden-journey-audit-secret-32-chars-long",
            high_risk_review_mode="required",
            allowed_origins=("http://localhost:8000",),
        )
        self.client = TestClient(create_app(
            settings,
            self.database,
            fulfillment_client=self.fulfillment,
            case_management_client=self.cases,
        ))

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    @staticmethod
    def headers(customer_id, role="customer", idempotency_key=None):
        result = {
            "X-Saarthi-Demo-Customer": customer_id,
            "X-Saarthi-Demo-Role": role,
        }
        if idempotency_key:
            result["Idempotency-Key"] = idempotency_key
        return result

    def grant_personalization(self, customer_id):
        response = self.client.post(
            "/api/v1/consent/grant",
            json={"purpose": "personalization"},
            headers=self.headers(customer_id),
        )
        self.assertEqual(response.status_code, 200)

    def orchestrate(self, customer_id, segment, signal, key):
        self.grant_personalization(customer_id)
        return self.client.post(
            "/api/v1/orchestrate",
            json={"signal": signal, "segment": segment},
            headers=self.headers(customer_id, idempotency_key=key),
        )

    def approve_and_present(
        self,
        customer_id,
        result,
        expected_product_id,
        expected_internal_rate,
    ):
        recommendation_id = result["recommendation_id"]
        review_id = result["review_id"]
        self.assertEqual(result["decision_outcome"], "review_required")
        self.assertEqual(result["delivery_mode"], "human_review_required")
        self.assertIsNone(result["customer_presentation"])
        self.assertIsNone(result["recommended_product_id"])
        self.assertIsNone(result["interest_rate"])

        blocked = self.client.post(
            "/api/v1/decisions/authorize",
            json={"recommendationId": recommendation_id},
            headers=self.headers(customer_id),
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["status"], "review_required")

        reviewer_headers = self.headers("SBI-GOLDEN-REVIEWER", "reviewer")
        queue = self.client.get("/api/v1/reviews", headers=reviewer_headers)
        self.assertEqual(queue.status_code, 200)
        review = next(item for item in queue.json() if item["review_id"] == review_id)
        self.assertEqual(review["recommendation_id"], recommendation_id)
        self.assertEqual(review["evidence"]["product_id"], expected_product_id)
        # Synthetic pricing remains available only to the independent reviewer.
        self.assertEqual(review["evidence"]["interest_rate"], expected_internal_rate)

        approval = self.client.post(
            f"/api/v1/reviews/{review_id}/decision",
            json={
                "decision": "approved",
                "reason": "Synthetic evidence and customer disclosure verified",
            },
            headers=reviewer_headers,
        )
        self.assertEqual(approval.status_code, 200)
        self.assertEqual(approval.json()["review"]["recommendation_id"], recommendation_id)

        not_presented = self.client.post(
            "/api/v1/decisions/authorize",
            json={"recommendationId": recommendation_id},
            headers=self.headers(customer_id),
        )
        self.assertEqual(not_presented.status_code, 409)
        self.assertEqual(not_presented.json()["status"], "offer_not_presented")

        presentation_response = self.client.get(
            f"/api/v1/recommendations/{recommendation_id}",
            headers=self.headers(customer_id),
        )
        self.assertEqual(presentation_response.status_code, 200)
        recommendation = presentation_response.json()["recommendation"]
        presentation = recommendation["evidence"]["presentation"]
        self.assertEqual(recommendation["recommendation_id"], recommendation_id)
        self.assertEqual(recommendation["product_id"], expected_product_id)
        self.assertIsNone(recommendation["interest_rate"])
        self.assertEqual(presentation["product_id"], expected_product_id)
        self.assertFalse(presentation["support_only"])
        self.assertIn("Demo catalogue terms are not a live SBI offer", presentation["body"])
        self.assertIn("pricing and disclosures must be checked", presentation["body"])
        self.assertNotIn(str(expected_internal_rate), json.dumps(presentation))
        self.assertNotIn(str(expected_internal_rate), presentation_response.text)
        return recommendation

    def authorize_execute_and_reconcile(self, customer_id, recommendation, product_id):
        recommendation_id = recommendation["recommendation_id"]
        authorization = self.client.post(
            "/api/v1/decisions/authorize",
            json={"recommendationId": recommendation_id},
            headers=self.headers(customer_id),
        )
        self.assertEqual(authorization.status_code, 200)
        self.assertEqual(authorization.json()["recommendation_id"], recommendation_id)
        self.assertEqual(authorization.json()["product_id"], product_id)

        execution = self.client.post(
            "/api/v1/actions/execute",
            json={
                "recommendationId": recommendation_id,
                "decisionToken": authorization.json()["decision_token"],
            },
            headers=self.headers(customer_id),
        )
        self.assertEqual(execution.status_code, 200)
        self.assertEqual(execution.json()["status"], "fulfilled")
        self.assertEqual(execution.json()["recommendation_id"], recommendation_id)
        self.assertEqual(execution.json()["fulfillment"]["provider"], "synthetic-fulfillment")
        fulfillment_reference = execution.json()["fulfillment"]["reference"]
        self.assertEqual(self.fulfillment.execute_calls[-1]["recommendation_id"], recommendation_id)
        self.assertEqual(self.fulfillment.execute_calls[-1]["product_id"], product_id)

        customer_denied = self.client.get(
            "/api/v1/fulfillment/reconciliations",
            headers=self.headers(customer_id),
        )
        self.assertEqual(customer_denied.status_code, 403)

        reconciliation = self.client.post(
            f"/api/v1/fulfillment/reconciliations/{recommendation_id}/run",
            headers=self.headers("SBI-GOLDEN-OPS", "ops"),
        )
        self.assertEqual(reconciliation.status_code, 200)
        self.assertEqual(reconciliation.json()["status"], "matched")
        record = reconciliation.json()["reconciliation"]
        self.assertEqual(record["recommendation_id"], recommendation_id)
        self.assertEqual(record["fulfillment_reference"], fulfillment_reference)
        self.assertEqual(self.fulfillment.status_calls[-1], {
            "recommendation_id": recommendation_id,
            "fulfillment_reference": fulfillment_reference,
        })
        return execution.json(), reconciliation.json()

    def test_reviewed_high_risk_card_debt_action_reconciles_same_identity(self):
        customer_id = "SBI-772910"  # Priya Sharma
        response = self.orchestrate(
            customer_id,
            "corporate",
            "DEBT_OPPORTUNITY — CC interest ₹4,200/mo exceeds consolidation threshold",
            "golden-debt-0001",
        )
        self.assertEqual(response.status_code, 200)
        recommendation = self.approve_and_present(
            customer_id,
            response.json(),
            "SBI-LOAN-EXP01",
            20.0,
        )
        self.authorize_execute_and_reconcile(
            customer_id,
            recommendation,
            "SBI-LOAN-EXP01",
        )

    def test_senior_fd_fails_closed_and_never_customer_presents_synthetic_rate(self):
        customer_id = "SBI-881234"  # Ramesh Kumar
        response = self.orchestrate(
            customer_id,
            "pensioner",
            "FD_OPPORTUNITY — ₹50,000 idle savings exceeding 90-day liquidity buffer",
            "golden-senior-fd-0001",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("6.75", response.text)
        recommendation = self.approve_and_present(
            customer_id,
            response.json(),
            "SBI-FD-SENIOR02",
            6.75,
        )
        execution, reconciliation = self.authorize_execute_and_reconcile(
            customer_id,
            recommendation,
            "SBI-FD-SENIOR02",
        )
        self.assertNotIn("6.75", json.dumps(execution))
        self.assertNotIn("6.75", json.dumps(reconciliation))

        catalog = self.client.get(
            "/api/v1/products",
            headers=self.headers(customer_id),
        )
        self.assertEqual(catalog.status_code, 200)
        senior_fd = next(item for item in catalog.json() if item["product_id"] == "SBI-FD-SENIOR02")
        self.assertIsNone(senior_fd["rate"])

    def test_branch_to_digital_low_risk_tutorial_requires_consent_before_completion(self):
        customer_id = "SBI-554321"  # Rohan Mehta
        response = self.orchestrate(
            customer_id,
            "student",
            "BRANCH_FRICTION — 2 branch visits for education loan statement queries",
            "golden-branch-digital-0001",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["delivery_mode"], "auto_fire")
        self.assertEqual(body["decision_outcome"], "eligible")
        self.assertEqual(body["risk_tier"], "low")
        self.assertEqual(body["recommended_product_id"], "SBI-EDU-DASH13")
        self.assertEqual(body["customer_presentation"]["title"], "Digital Education Loan Dashboard")
        self.assertEqual(body["customer_presentation"]["action_label"], "Review & Continue")
        self.assertIsNone(body["interest_rate"])
        self.assertNotIn("rate", body["neo4j_query"])
        self.assertEqual(self.fulfillment.execute_calls, [])

        presented = self.client.get(
            f"/api/v1/recommendations/{body['recommendation_id']}",
            headers=self.headers(customer_id),
        )
        self.assertEqual(presented.status_code, 200)
        self.assertEqual(presented.json()["status"], "already_presented")
        self.authorize_execute_and_reconcile(
            customer_id,
            presented.json()["recommendation"],
            "SBI-EDU-DASH13",
        )

    def test_stress_support_only_exposes_no_financial_or_operations_case_action(self):
        customer_id = "SBI-991877"  # Sneha Patel
        response = self.orchestrate(
            customer_id,
            "stressed",
            "FINANCIAL_STRESS — Missed EMI (Home Loan) after salary reduction",
            "golden-support-only-0001",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["delivery_mode"], "support_mode")
        self.assertEqual(body["decision_outcome"], "support_only")
        self.assertIsNone(body["recommendation_id"])
        self.assertIsNone(body["recommended_product_id"])
        self.assertIsNone(body["interest_rate"])
        self.assertIsNone(body["neo4j_query"])
        self.assertIsNone(body["policy_evidence"])
        self.assertTrue(body["customer_presentation"]["support_only"])
        self.assertIsNone(body["customer_presentation"]["product_id"])
        self.assertIsNone(body["customer_presentation"]["action_label"])
        self.assertIsNone(body["customer_presentation"]["consent_text"])
        self.assertIsNone(body["customer_presentation"]["success_text"])

        execution = self.client.post(
            "/api/v1/actions/execute",
            json={
                "recommendationId": "support-only-no-recommendation",
                "decisionToken": "0" * 64,
            },
            headers=self.headers(customer_id),
        )
        self.assertEqual(execution.status_code, 404)
        self.assertEqual(self.fulfillment.execute_calls, [])

        # The available case API is intentionally limited to reconciliation
        # mismatches.  A stress/support journey cannot be smuggled into it.
        case_request = self.client.post(
            "/api/v1/operations/cases",
            json={
                "recommendationId": "support-only-no-recommendation",
                "summary": "Request human support without initiating a financial action",
            },
            headers=self.headers("SBI-GOLDEN-OPS", "ops"),
        )
        self.assertEqual(case_request.status_code, 409)
        self.assertEqual(case_request.json()["status"], "mismatch_required")
        self.assertIsNone(case_request.json()["case"])
        self.assertEqual(self.cases.create_calls, [])
        self.assertEqual(self.cases.status_calls, [])
        self.assertEqual(
            self.client.get(
                "/api/v1/operations/cases",
                headers=self.headers("SBI-GOLDEN-OPS", "ops"),
            ).json(),
            [],
        )


if __name__ == "__main__":
    unittest.main()
