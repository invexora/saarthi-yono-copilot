import unittest
from datetime import datetime, timezone

from backend.decision_policy import DeterministicDecisionPolicy


class DeterministicDecisionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = DeterministicDecisionPolicy()
        self.state = {
            "neo4j_query": {"product_id": "SBI-TEST"},
            "recommended_product_id": "SBI-TEST",
            "policy_evidence": {"approval_status": "approved", "content_sha256": "a" * 64},
            "interest_rate": 12.0,
            "signal_category": "opportunity",
            "signal_evidence": {
                "category": "opportunity",
                "confidence": 0.95,
                "model_id": "test-signal-model",
                "model_version": "test-v1",
                "input_digest": "b" * 64,
                "evaluation_status": "approved",
            },
            "risk_tier": "high",
            "customer_segment": "corporate",
            "customer_context": {
                "customer_segment": "corporate",
                "monthly_income": 100000,
                "monthly_obligations": 25000,
                "vulnerability_flags": [],
                "verification_status": "verified",
                "source_system": "test-cbs",
                "as_of": datetime.now(timezone.utc).isoformat(),
                "context_version": "test-v1",
            },
        }

    def test_high_risk_item_routes_to_review_when_enforced(self):
        result = self.policy.evaluate(self.state, high_risk_review_required=True)

        self.assertEqual(result["outcome"], "review_required")
        self.assertIn("HIGH_RISK_HUMAN_REVIEW_REQUIRED", result["reason_codes"])

    def test_financial_stress_can_only_route_to_support(self):
        result = self.policy.evaluate({
            **self.state,
            "signal_category": "stress",
            "signal_evidence": {**self.state["signal_evidence"], "category": "stress"},
            "risk_tier": "support",
        }, True)

        self.assertEqual(result["outcome"], "support_only")
        self.assertIn("FINANCIAL_STRESS_SUPPORT_ONLY", result["reason_codes"])

    def test_rate_above_safety_cap_is_rejected(self):
        result = self.policy.evaluate({**self.state, "interest_rate": 42.0}, True)

        self.assertEqual(result["outcome"], "rejected")
        self.assertIn("RATE_EXCEEDS_SAFETY_CAP", result["reason_codes"])

    def test_missing_approved_policy_or_product_is_rejected(self):
        invalid = {
            **self.state,
            "neo4j_query": None,
            "recommended_product_id": "NO_PRODUCT",
            "policy_evidence": {"approval_status": "draft"},
        }
        result = self.policy.evaluate(invalid, True)

        self.assertEqual(result["outcome"], "rejected")
        self.assertIn("NO_ELIGIBLE_PRODUCT", result["reason_codes"])
        self.assertIn("POLICY_EVIDENCE_INVALID", result["reason_codes"])

    def test_missing_signal_provenance_is_rejected(self):
        result = self.policy.evaluate({**self.state, "signal_evidence": None}, True)

        self.assertEqual(result["outcome"], "rejected")
        self.assertIn("SIGNAL_EVIDENCE_INVALID", result["reason_codes"])

    def test_stale_customer_context_is_rejected(self):
        stale = {**self.state, "customer_context": {**self.state["customer_context"], "as_of": "2025-01-01T00:00:00+00:00"}}
        result = self.policy.evaluate(stale, True)

        self.assertEqual(result["outcome"], "rejected")
        self.assertIn("CUSTOMER_CONTEXT_UNVERIFIED_OR_STALE", result["reason_codes"])

    def test_credit_commitment_uses_total_debt_service_ratio(self):
        constrained = {
            **self.state,
            "neo4j_query": {
                "product_id": "SBI-TEST",
                "product_type": "credit",
                "monthly_commitment": 30000,
                "max_dsti": 0.5,
            },
        }
        result = self.policy.evaluate(constrained, True)

        self.assertEqual(result["outcome"], "rejected")
        self.assertIn("AFFORDABILITY_LIMIT_EXCEEDED", result["reason_codes"])


if __name__ == "__main__":
    unittest.main()
