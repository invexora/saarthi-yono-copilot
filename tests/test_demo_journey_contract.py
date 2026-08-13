import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.database import DatabaseManager
from backend.neo4j_client import Neo4jProductGraph
from backend.settings import Settings
from backend.signal_detection import VersionedRuleSignalDetector


# journey_id, segment, signal, category, product_id, delivery_mode, outcome, actionable
JOURNEYS = (
    ("priya.friction", "corporate", "TAX_FRICTION — Quarterly counter advance tax payment detected", "friction", "SBI-TAX-DIGITAL16", "auto_fire", "eligible", True),
    ("priya.opportunity", "corporate", "DEBT_OPPORTUNITY — CC interest ₹4,200/mo exceeds consolidation threshold", "opportunity", "SBI-LOAN-EXP01", "decision_token_required", "eligible", True),
    ("priya.lifeevent", "corporate", "LIFE_EVENT — 30% salary increase detected over 3 consecutive months", "lifeevent", "SBI-RD-FLEXI12", "decision_token_required", "eligible", True),
    ("priya.stress", "corporate", "OVERDRAFT_ALERT — Overdraft account utilization at 95%", "stress", "SBI-RELIEF-RM15", "support_mode", "support_only", False),
    ("ramesh.friction", "pensioner", "BRANCH_FRICTION — 4 counter deposit visits in the last 30 days", "friction", "SBI-UPI-AUTOPAY04", "auto_fire", "eligible", True),
    ("ramesh.opportunity", "pensioner", "FD_OPPORTUNITY — ₹50,000 idle savings exceeding 90-day liquidity buffer", "opportunity", "SBI-FD-SENIOR02", "decision_token_required", "eligible", True),
    ("ramesh.lifeevent", "pensioner", "LIFE_EVENT — Policy maturity payout credit of ₹3,00,000 detected", "lifeevent", "SBI-SCSS-GOV03", "decision_token_required", "eligible", True),
    ("ramesh.stress", "pensioner", "FINANCIAL_STRESS — High pharmacy/medical merchant cash withdrawals", "stress", "SBI-MED-AAROGYAM14", "support_mode", "support_only", False),
    ("amit.friction", "sme", "BRANCH_FRICTION — 12 counter cash deposits in the last 15 days", "friction", "SBI-SME-QR05", "auto_fire", "eligible", True),
    ("amit.opportunity", "sme", "AUTO_SWEEP_OPPORTUNITY — Idle current account balance of ₹6,40,000", "opportunity", "SBI-SME-SWEEP06", "decision_token_required", "eligible", True),
    ("amit.lifeevent", "sme", "LIFE_EVENT — GST refund credit of ₹1,50,000 detected", "lifeevent", "SBI-SME-PREPAY07", "decision_token_required", "eligible", True),
    ("amit.stress", "sme", "FINANCIAL_STRESS — Delayed accounts receivable, 98% draft utilization", "stress", "SBI-RELIEF-RM15", "support_mode", "support_only", False),
    ("sneha.friction", "stressed", "KYC_FRICTION — KYC compliance alert and 2 physical branch KYC queries", "friction", "SBI-KYC-VIDEO10", "support_mode", "support_only", False),
    ("sneha.opportunity", "stressed", "REPAYMENT_RESTRUCTURING — High credit card balances exceeding stress index", "opportunity", "SBI-EMI-CC08", "support_mode", "rejected", False),
    ("sneha.lifeevent", "stressed", "LIFE_EVENT — Monthly cash savings buffer below threshold", "lifeevent", "SBI-RD-MICRO09", "support_mode", "support_only", False),
    ("sneha.stress", "stressed", "FINANCIAL_STRESS — Missed EMI (Home Loan) after salary reduction", "stress", "SBI-RELIEF-RM15", "support_mode", "support_only", False),
    ("rohan.friction", "student", "BRANCH_FRICTION — 2 branch visits for education loan statement queries", "friction", "SBI-EDU-DASH13", "auto_fire", "eligible", True),
    ("rohan.opportunity", "student", "INVESTMENT_OPPORTUNITY — ₹18,000 stipend with zero investment allocation", "opportunity", "SBI-SIP-MF11", "decision_token_required", "eligible", True),
    ("rohan.lifeevent", "student", "LIFE_EVENT — First salary credit of ₹35,000 detected (new employment)", "lifeevent", "SBI-RD-FLEXI12", "decision_token_required", "eligible", True),
    ("rohan.stress", "student", "FINANCIAL_STRESS — Education loan EMI due with no regular income detected", "stress", "SBI-RELIEF-RM15", "support_mode", "support_only", False),
)


class RecordingFulfillmentClient:
    mode = "synthetic-recording"

    def __init__(self):
        self.calls = []

    def execute(self, recommendation, customer_id, idempotency_key):
        self.calls.append({
            "recommendation_id": recommendation["recommendation_id"],
            "product_id": recommendation["product_id"],
            "customer_id": customer_id,
            "idempotency_key": idempotency_key,
        })
        return {
            "status": "completed",
            "reference": f"DEMO-CONTRACT-{len(self.calls):03d}",
            "provider": self.mode,
        }

    def get_status(self, fulfillment_reference, recommendation_id):
        return {"status": "completed", "reference": fulfillment_reference, "recommendation_id": recommendation_id}

    def health(self):
        return {"name": "fulfillment", "mode": self.mode, "ready": True, "detail": "test recorder"}


class DemoJourneyContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "journey-contract.db")
        self.database = DatabaseManager(self.db_path)
        self.fulfillment = RecordingFulfillmentClient()
        settings = Settings(
            db_path=self.db_path,
            auth_mode="development",
            decision_secret="journey-contract-decision-secret-32-chars",
            allowed_origins=("http://localhost:8000",),
        )
        self.client = TestClient(create_app(settings, self.database, fulfillment_client=self.fulfillment))

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    @staticmethod
    def headers(customer_id, idempotency_key=None):
        headers = {
            "X-Saarthi-Demo-Customer": customer_id,
            "X-Saarthi-Demo-Role": "customer",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def test_fixture_has_five_by_four_shape_and_sixteen_mock_products(self):
        self.assertEqual(len(JOURNEYS), 20)
        self.assertEqual(len({journey[0] for journey in JOURNEYS}), 20)
        self.assertEqual({journey[3] for journey in JOURNEYS}, {"friction", "opportunity", "lifeevent", "stress"})
        self.assertEqual(sum(1 for journey in JOURNEYS if journey[7]), 12)
        self.assertEqual(sum(1 for journey in JOURNEYS if not journey[7]), 8)
        self.assertEqual(len({row["product_id"] for row in Neo4jProductGraph().list_products()}), 16)

    def test_all_twenty_signal_codes_and_catalog_mappings_match(self):
        detector = VersionedRuleSignalDetector()
        catalog = Neo4jProductGraph()
        for journey_id, segment, signal, category, product_id, *_ in JOURNEYS:
            with self.subTest(journey=journey_id):
                evidence = detector.classify(signal)
                self.assertEqual(evidence["category"], category)
                self.assertIn("EXPLICIT_SIGNAL_CONTRACT_MATCH", evidence["reason_codes"])
                self.assertEqual(catalog.query_eligibility(category, segment)["product_id"], product_id)

    def test_all_twenty_routes_and_twelve_action_identity_chains(self):
        for index, journey in enumerate(JOURNEYS, start=1):
            journey_id, segment, signal, category, product_id, delivery_mode, outcome, actionable = journey
            customer_id = f"SBI-JOURNEY-{index:03d}"
            base_headers = self.headers(customer_id)
            with self.subTest(journey=journey_id):
                granted = self.client.post(
                    "/api/v1/consent/grant",
                    json={"purpose": "personalization"},
                    headers=base_headers,
                )
                self.assertEqual(granted.status_code, 200)
                response = self.client.post(
                    "/api/v1/orchestrate",
                    json={"signal": signal, "segment": segment},
                    headers=self.headers(customer_id, f"journey-contract-{index:03d}"),
                )
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["signal_category"], category)
                self.assertEqual(body["delivery_mode"], delivery_mode)
                self.assertEqual(body["decision_outcome"], outcome)

                if not actionable:
                    self.assertIsNone(body["recommendation_id"])
                    self.assertIsNone(body["decision_token"])
                    self.assertIsNone(body["recommended_product_id"])
                    self.assertTrue(body["customer_presentation"]["support_only"])
                    self.assertIsNone(body["customer_presentation"]["product_id"])
                    continue

                recommendation_id = body["recommendation_id"]
                self.assertEqual(body["recommended_product_id"], product_id)
                self.assertEqual(body["customer_presentation"]["product_id"], product_id)

                presented = self.client.get(
                    f"/api/v1/recommendations/{recommendation_id}",
                    headers=base_headers,
                )
                self.assertEqual(presented.status_code, 200)
                recommendation = presented.json()["recommendation"]
                self.assertEqual(recommendation["recommendation_id"], recommendation_id)
                self.assertEqual(recommendation["product_id"], product_id)
                self.assertEqual(recommendation["evidence"]["presentation"], body["customer_presentation"])
                self.assertEqual(recommendation["evidence"]["presentation"]["product_id"], product_id)

                authorized = self.client.post(
                    "/api/v1/decisions/authorize",
                    json={"recommendationId": recommendation_id},
                    headers=base_headers,
                )
                self.assertEqual(authorized.status_code, 200)
                authorization = authorized.json()
                self.assertEqual(authorization["recommendation_id"], recommendation_id)
                self.assertEqual(authorization["product_id"], product_id)

                executed = self.client.post(
                    "/api/v1/actions/execute",
                    json={
                        "recommendationId": recommendation_id,
                        "decisionToken": authorization["decision_token"],
                    },
                    headers=base_headers,
                )
                self.assertEqual(executed.status_code, 200)
                self.assertEqual(executed.json()["recommendation_id"], recommendation_id)
                self.assertEqual(self.fulfillment.calls[-1]["recommendation_id"], recommendation_id)
                self.assertEqual(self.fulfillment.calls[-1]["product_id"], product_id)


if __name__ == "__main__":
    unittest.main()
