import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.database import DatabaseManager
from backend.dpdp_engine import DPDPEngine
from backend.guardrails import OutputGuardian
from backend.orchestrator import SaarthiAgentOrchestrator


class TrustControlTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.temp_dir.name) / "test.db"))
        self.dpdp = DPDPEngine(self.db)
        self.orchestrator = SaarthiAgentOrchestrator(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_trace(self, customer_id, signal, segment="corporate"):
        return self.orchestrator.run_trace(
            signal=signal,
            details="Email: priya@example.com | Aadhaar: 4532 9981 1204 | PAN: ABCDE1234F",
            customer_segment=segment,
            customer_id=customer_id,
        )

    def test_profiling_is_blocked_without_active_consent(self):
        result = self.run_trace("SBI-NOCONSENT", "Branch cash deposit")

        self.assertEqual(result["delivery_mode"], "consent_required")
        self.assertFalse(result["compliance_approved"])
        self.assertNotIn("raw_details", result)
        self.assertEqual(result["nudge_budget"]["used"], 0)

    def test_decision_workflow_is_compiled_with_expected_nodes(self):
        graph = self.orchestrator.graph.get_graph()

        self.assertTrue({
            "input_guardian", "signal_detection", "recommendation", "deterministic_compliance",
        }.issubset(graph.nodes))

    def test_raw_pii_never_crosses_output_boundary(self):
        customer_id = "SBI-PRIVACY"
        self.dpdp.grant_consent(customer_id, "personalization")

        result = self.run_trace(customer_id, "Recurring credit card interest and debt")

        self.assertNotIn("raw_details", result)
        self.assertNotIn("priya@example.com", result["masked_details"])
        self.assertNotIn("ABCDE1234F", result["masked_details"])
        self.assertIn("[MASKED EMAIL]", result["masked_details"])
        self.assertEqual(result["delivery_mode"], "decision_token_required")
        self.assertIsNone(result["decision_token"])

    def test_signal_pii_is_masked_before_event_response_and_audit(self):
        customer_id = "SBI-SIGNAL-PRIVACY"
        self.dpdp.grant_consent(customer_id, "personalization")

        result = self.run_trace(customer_id, "Branch deposit reported by priya@example.com PAN ABCDE1234F")
        event = self.orchestrator.redis_stream.consume_events(1)[0]
        audit = self.db.get_audit_logs(customer_id)[0]

        for value in (result["raw_signal"], event["payload"]["signal"], audit["signal"]):
            self.assertNotIn("priya@example.com", value)
            self.assertNotIn("ABCDE1234F", value)
            self.assertIn("[MASKED", value)

    def test_explicit_authorization_issues_single_use_server_token(self):
        customer_id = "SBI-AUTH"
        self.dpdp.grant_consent(customer_id, "personalization")
        recommendation = self.run_trace(customer_id, "Recurring credit card interest and debt")

        authorized = self.dpdp.authorize_recommendation(recommendation["recommendation_id"], customer_id)
        replay = self.dpdp.authorize_recommendation(recommendation["recommendation_id"], customer_id)

        self.assertEqual(authorized["status"], "authorized")
        self.assertEqual(len(authorized["decision_token"]), 64)
        self.assertEqual(replay["status"], "already_authorized")

    def test_promotional_nudge_budget_is_enforced_atomically(self):
        customer_id = "SBI-BUDGET"
        self.dpdp.grant_consent(customer_id, "personalization")

        first = self.run_trace(customer_id, "Branch cash deposit")
        second = self.run_trace(customer_id, "Branch cash deposit")
        third = self.run_trace(customer_id, "Branch cash deposit")

        self.assertEqual(first["nudge_budget"]["used"], 1)
        self.assertEqual(second["nudge_budget"]["used"], 2)
        self.assertEqual(third["delivery_mode"], "budget_exceeded")
        self.assertEqual(third["nudge_budget"]["used"], 2)

    def test_stress_support_does_not_consume_promotional_budget(self):
        customer_id = "SBI-SUPPORT"
        self.dpdp.grant_consent(customer_id, "personalization")

        result = self.run_trace(customer_id, "Missed EMI after job loss", "stressed")

        self.assertEqual(result["delivery_mode"], "support_mode")
        self.assertEqual(result["nudge_budget"]["used"], 0)

    def test_policy_rejection_does_not_consume_promotional_budget(self):
        class UnsafeRateCatalog:
            def query_eligibility(self, *_):
                return {
                    "product_id": "SBI-UNSAFE",
                    "product": "Unsafe Test Product",
                    "rate": 42.0,
                    "risk_tier": "high",
                }

        customer_id = "SBI-POLICY-REJECT"
        orchestrator = SaarthiAgentOrchestrator(self.db, product_catalog=UnsafeRateCatalog())
        orchestrator.dpdp_engine.grant_consent(customer_id, "personalization")

        result = orchestrator.run_trace("Recurring credit card interest", "", customer_id=customer_id)

        self.assertEqual(result["decision_outcome"], "rejected")
        self.assertIn("RATE_EXCEEDS_SAFETY_CAP", result["reason_codes"])
        self.assertEqual(self.db.get_nudge_budget_status(customer_id)["used"], 0)

    def test_output_guardian_requires_consent_even_when_kfs_is_present(self):
        ok, message = OutputGuardian().verify_compliance(
            "SBI consolidation loan at 20% p.a. Refer to KFS.",
            has_consent=False,
            customer_risk_tier="high",
        )

        self.assertFalse(ok)
        self.assertIn("consent", message.lower())

    def test_revocation_and_erasure_are_distinct_operations(self):
        customer_id = "SBI-ERASURE"
        self.dpdp.grant_consent(customer_id, "personalization")
        self.db.log_audit_event(customer_id, "test", None, None, "low", "none", 1, 1)

        self.dpdp.revoke_consent(customer_id, "personalization")
        self.assertFalse(self.dpdp.verify_purpose_consent(customer_id, "personalization"))
        self.assertEqual(len(self.db.get_audit_logs(customer_id)), 1)

        result = self.dpdp.revoke_consent_and_erase(customer_id)
        self.assertEqual(result["status"], "processed")
        self.assertEqual(result["scope"], "eligible_saarthi_derived_data")
        self.assertIn("revoked_consent_tombstone", result["retained"])
        self.assertIn("integrity_ledger_evidence", result["retained"])
        self.assertEqual(self.db.get_audit_logs(customer_id), [])
        consent_records = self.db.get_consent_status(customer_id)
        self.assertEqual(len(consent_records), 1)
        self.assertEqual(consent_records[0]["consent_status"], 0)
        self.assertEqual(consent_records[0]["erasure_requested"], 1)

    def test_database_migrations_are_versioned_and_idempotent(self):
        expected = ["001_core", "002_recommendations", "003_idempotency", "004_governance", "005_review_evidence", "006_offer_delivery", "007_fulfillment", "008_event_processing", "009_fulfillment_reconciliation", "010_operations_cases", "011_rollout_controls", "012_outcome_monitoring", "013_model_rollout_scope", "014_governed_artifacts"]
        self.assertEqual(self.db.get_applied_migrations(), expected)

        reopened = DatabaseManager(self.db.db_path)
        self.assertEqual(reopened.get_applied_migrations(), expected)

    def test_concurrent_nudge_reservations_never_exceed_budget(self):
        customer_id = "SBI-CONCURRENT-BUDGET"
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: self.db.consume_nudge_budget(customer_id), range(8)))

        self.assertEqual(sum(1 for result in results if result["allowed"]), 2)
        self.assertEqual(self.db.get_nudge_budget_status(customer_id)["used"], 2)

    def test_concurrent_idempotency_claim_has_one_owner(self):
        customer_id = "SBI-CONCURRENT-IDEMPOTENCY"
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(
                lambda _: self.db.claim_idempotency(customer_id, "same-concurrent-request"),
                range(8),
            ))

        self.assertEqual(sum(1 for result in results if result["status"] == "claimed"), 1)
        self.assertEqual(sum(1 for result in results if result["status"] == "in_progress"), 7)

    def test_concurrent_offer_presentation_consumes_budget_once(self):
        customer_id = "SBI-PRESENT-CONCURRENT"
        recommendation_id = "approved-recommendation-001"
        self.db.create_recommendation_with_status(
            recommendation_id, customer_id, "SBI-LOAN-EXP01", 20.0, "high",
            initial_status="approved", evidence={"reason_codes": ["APPROVED"]},
        )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(
                lambda _: self.db.present_recommendation(recommendation_id, customer_id),
                range(8),
            ))

        self.assertEqual(sum(status == "presented" for _, status in results), 1)
        self.assertEqual(sum(status == "already_presented" for _, status in results), 7)
        self.assertEqual(self.db.get_nudge_budget_status(customer_id)["used"], 1)

    def test_expired_reviewed_offer_cannot_be_presented(self):
        customer_id = "SBI-PRESENT-EXPIRED"
        recommendation_id = "expired-recommendation-001"
        self.db.create_recommendation_with_status(
            recommendation_id, customer_id, "SBI-LOAN-EXP01", 20.0, "high",
            initial_status="approved", ttl_seconds=-1,
        )

        recommendation, presentation_status = self.db.present_recommendation(recommendation_id, customer_id)

        self.assertIsNone(recommendation)
        self.assertEqual(presentation_status, "expired")
        self.assertEqual(self.db.get_nudge_budget_status(customer_id)["used"], 0)

    def test_revocation_blocks_later_presentation_and_authorization(self):
        customer_id = "SBI-REVOKED-OFFER"
        self.dpdp.grant_consent(customer_id, "personalization")
        self.db.create_recommendation_with_status(
            "approved-after-revoke-001", customer_id, "SBI-LOAN-EXP01", 20.0, "high",
            initial_status="approved",
        )
        self.db.create_recommendation(
            "presented-after-revoke-001", customer_id, "SBI-LOAN-EXP01", 20.0, "high",
        )
        self.dpdp.revoke_consent(customer_id, "personalization")

        presentation = self.dpdp.present_recommendation("approved-after-revoke-001", customer_id)
        authorization = self.dpdp.authorize_recommendation("presented-after-revoke-001", customer_id)

        self.assertEqual(presentation["status"], "consent_required")
        self.assertEqual(authorization["status"], "consent_required")

    def test_stale_idempotency_claim_can_be_recovered(self):
        customer_id = "SBI-STALE-IDEMPOTENCY"
        self.assertEqual(self.db.claim_idempotency(customer_id, "stale-request")["status"], "claimed")

        recovered = self.db.claim_idempotency(
            customer_id,
            "stale-request",
            processing_timeout_seconds=0,
        )

        self.assertEqual(recovered["status"], "claimed")


if __name__ == "__main__":
    unittest.main()
