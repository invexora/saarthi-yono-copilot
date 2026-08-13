import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.audit_ledger import AuditLedger
from backend.database import DatabaseManager
from backend.dpdp_engine import DPDPEngine
from backend.fulfillment_service import FulfillmentService
from backend.rollout import RolloutControlService
from backend.settings import Settings
from backend.signal_detection import MODEL_ID, MODEL_VERSION


class RolloutControlTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.temp_dir.name) / "rollout.db"))
        self.ledger = AuditLedger(self.db, "rollout-audit-secret-at-least-32-characters")
        self.service = RolloutControlService(
            self.db, "rollout-cohort-secret-at-least-32-characters", self.ledger,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _approve(self, scope_type, scope_value, mode, cohort=100):
        requested = self.service.request(
            scope_type, scope_value, mode, cohort,
            "Required for a governed rollout safety test", "requester-ref",
        )
        return self.service.decide(
            requested["control"]["control_id"], "approved", "approver-ref",
        )

    def test_four_eyes_activation_masking_and_emergency_override(self):
        requested = self.service.request(
            "global", "*", "shadow", 20,
            "Contact rollout.owner@example.com before activating this control",
            "requester-ref",
        )
        self.assertEqual(requested["status"], "requested")
        self.assertNotIn("requested_by_ref", requested["control"])
        self.assertNotIn("rollout.owner@example.com", requested["control"]["reason"])
        self.assertEqual(requested["control"]["cohort_percentage"], 100)

        same_actor = self.service.decide(
            requested["control"]["control_id"], "approved", "requester-ref",
        )
        self.assertEqual(same_actor["status"], "four_eyes_required")
        approved = self.service.decide(
            requested["control"]["control_id"], "approved", "approver-ref",
        )
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(self.service.evaluate("SBI-ROLLOUT-001")["mode"], "shadow")

        disabled = self.service.emergency_disable(
            "global", "*", "Immediate safety stop due to an operational incident", "admin-ref",
        )
        self.assertEqual(disabled["status"], "disabled")
        self.assertEqual(self.service.evaluate("SBI-ROLLOUT-001")["mode"], "disabled")
        self.assertEqual(approved["control"]["status"], "active")
        self.assertEqual(
            self.db.get_rollout_control(approved["control"]["control_id"])["status"],
            "superseded",
        )

        restored = self._approve("global", "*", "active", 100)
        self.assertEqual(restored["status"], "approved")
        self.assertEqual(self.service.evaluate("SBI-ROLLOUT-001")["mode"], "live")

    def test_hierarchy_and_deterministic_cohort_exclusion(self):
        cohort = self._approve("product", "SBI-LOAN-EXP01", "active", 0)
        first = self.service.evaluate(
            "SBI-COHORT-001", product="SBI-LOAN-EXP01",
        )
        second = self.service.evaluate(
            "SBI-COHORT-001", product="SBI-LOAN-EXP01",
        )
        self.assertEqual(first, second)
        self.assertEqual(first["mode"], "shadow")
        self.assertIn(cohort["control"]["control_id"], first["control_ids"])

        self.service.emergency_disable(
            "global", "*", "Disable all journeys during incident containment", "admin-ref",
        )
        evaluation = self.service.evaluate(
            "SBI-COHORT-001", product="SBI-LOAN-EXP01",
        )
        self.assertEqual(evaluation["mode"], "disabled")
        self.assertEqual(evaluation["reason_codes"], ["ROLLOUT_SCOPE_DISABLED"])

    def test_model_scope_matches_only_the_exact_detector_version(self):
        model_scope = f"{MODEL_ID}:{MODEL_VERSION}"
        self.service.emergency_disable(
            "model", model_scope,
            "Contain this exact detector version after evaluation drift", "admin-ref",
        )
        matching = self.service.evaluate("SBI-MODEL-001", model=model_scope)
        other = self.service.evaluate("SBI-MODEL-001", model=f"{MODEL_ID}:future-version")
        self.assertEqual(matching["mode"], "disabled")
        self.assertEqual(other["mode"], "live")

    def test_concurrent_requests_leave_one_pending_change(self):
        def request(_):
            return self.service.request(
                "segment", "sme", "active", 50,
                "Gradually enable the SME rollout cohort safely", "requester-ref",
            )["status"]

        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes = list(executor.map(request, range(8)))

        self.assertEqual(outcomes.count("requested"), 1)
        self.assertEqual(outcomes.count("already_pending"), 7)
        self.assertEqual(len(self.service.list("pending")), 1)

    def test_existing_recommendation_cannot_bypass_control_and_fulfilled_replay_is_safe(self):
        class CountingClient:
            def __init__(self):
                self.calls = 0

            def execute(self, *_):
                self.calls += 1
                return {"status": "completed", "reference": "SBI-FULFILLED-001"}

        customer_id = "SBI-ROLLOUT-EXEC-001"
        recommendation_id = "rollout-recommendation-001"
        dpdp = DPDPEngine(
            self.db,
            decision_secret="rollout-decision-secret-at-least-32-chars",
            audit_ledger=self.ledger,
            rollout_control=self.service,
        )
        dpdp.grant_consent(customer_id, "personalization")
        self.db.create_recommendation_with_status(
            recommendation_id, customer_id, "SBI-LOAN-EXP01", 10.0, "high",
            initial_status="presented",
            evidence={
                "customer_segment": "corporate",
                "signal_category": "opportunity",
                "signal_detection": {"model_id": MODEL_ID, "model_version": MODEL_VERSION},
            },
        )
        authorization = dpdp.authorize_recommendation(recommendation_id, customer_id)
        self.assertEqual(authorization["status"], "authorized")

        self.service.emergency_disable(
            "model", f"{MODEL_ID}:{MODEL_VERSION}",
            "Disable execution while this detector version is investigated", "admin-ref",
        )
        self.assertEqual(
            dpdp.present_recommendation(recommendation_id, customer_id)["status"],
            "rollout_blocked",
        )
        client = CountingClient()
        fulfillment = FulfillmentService(
            self.db, client, self.ledger, dpdp, self.service,
        )
        blocked = fulfillment.execute(
            recommendation_id, customer_id, authorization["decision_token"],
        )
        self.assertEqual(blocked["status"], "rollout_blocked")
        self.assertEqual(client.calls, 0)

        self._approve("model", f"{MODEL_ID}:{MODEL_VERSION}", "active", 100)
        fulfilled = fulfillment.execute(
            recommendation_id, customer_id, authorization["decision_token"],
        )
        self.assertEqual(fulfilled["status"], "fulfilled")
        self.assertEqual(client.calls, 1)
        self.service.emergency_disable(
            "model", f"{MODEL_ID}:{MODEL_VERSION}",
            "Disable future actions while preserving completed replay safety", "admin-ref",
        )
        replay = fulfillment.execute(
            recommendation_id, customer_id, authorization["decision_token"],
        )
        self.assertEqual(replay["status"], "already_fulfilled")
        self.assertEqual(client.calls, 1)


class RolloutApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "rollout-api.db")
        self.db = DatabaseManager(db_path)
        self.settings = Settings(
            db_path=db_path,
            auth_mode="development",
            decision_secret="rollout-api-decision-secret-at-least-32-chars",
        )
        self.client = TestClient(create_app(self.settings, self.db))

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    @staticmethod
    def headers(customer_id, role="customer"):
        return {
            "X-Saarthi-Demo-Customer": customer_id,
            "X-Saarthi-Demo-Role": role,
        }

    def test_emergency_kill_switch_prevents_profiling_without_requiring_consent(self):
        denied = self.client.post(
            "/api/v1/governance/rollout-controls/emergency-disable",
            json={
                "scope_type": "global", "scope_value": "*",
                "reason": "Immediate stop during an active safety incident",
            },
            headers=self.headers("SBI-CUSTOMER-001"),
        )
        self.assertEqual(denied.status_code, 403)

        disabled = self.client.post(
            "/api/v1/governance/rollout-controls/emergency-disable",
            json={
                "scope_type": "global", "scope_value": "*",
                "reason": "Immediate stop during an active safety incident",
            },
            headers=self.headers("SBI-ADMIN-001", "admin"),
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertNotIn("requested_by_ref", disabled.text)

        customer_id = "SBI-NO-CONSENT-001"
        result = self.client.post(
            "/api/v1/orchestrate",
            json={"signal": "credit card interest", "segment": "corporate"},
            headers={
                **self.headers(customer_id),
                "Idempotency-Key": "rollout-kill-switch-001",
            },
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["delivery_mode"], "rollout_blocked")
        self.assertEqual(result.json()["decision_outcome"], "rollout_blocked")
        self.assertEqual(self.db.get_nudge_budget_status(customer_id)["used"], 0)

    def test_shadow_mode_is_non_customer_visible_and_consumes_no_budget(self):
        requester = self.headers("SBI-OPS-001", "ops")
        requested = self.client.post(
            "/api/v1/governance/rollout-controls",
            json={
                "scope_type": "global", "scope_value": "*", "mode": "shadow",
                "cohort_percentage": 10,
                "reason": "Validate the decision journey without customer exposure",
            },
            headers=requester,
        )
        self.assertEqual(requested.status_code, 201)
        control_id = requested.json()["control"]["control_id"]
        same_actor = self.client.post(
            f"/api/v1/governance/rollout-controls/{control_id}/decision",
            json={"decision": "approved"},
            headers=self.headers("SBI-OPS-001", "admin"),
        )
        self.assertEqual(same_actor.status_code, 409)
        approved = self.client.post(
            f"/api/v1/governance/rollout-controls/{control_id}/decision",
            json={"decision": "approved"},
            headers=self.headers("SBI-ADMIN-002", "admin"),
        )
        self.assertEqual(approved.status_code, 200)

        customer_id = "SBI-SHADOW-001"
        self.client.post(
            "/api/v1/consent/grant",
            json={"purpose": "personalization"},
            headers=self.headers(customer_id),
        )
        result = self.client.post(
            "/api/v1/orchestrate",
            json={
                "signal": "Recurring credit card interest and debt",
                "details": "Email: private@example.com | PAN: ABCDE1234F",
                "segment": "corporate",
            },
            headers={
                **self.headers(customer_id),
                "Idempotency-Key": "rollout-shadow-mode-001",
            },
        )
        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertEqual(body["delivery_mode"], "shadow_mode")
        self.assertEqual(body["decision_outcome"], "shadow_only")
        self.assertIsNone(body["recommended_product_id"])
        self.assertIsNone(body["interest_rate"])
        self.assertIsNone(body["nudge_output"])
        self.assertIsNone(body["policy_evidence"])
        self.assertIsNone(body["recommendation_id"])
        self.assertEqual(self.db.get_nudge_budget_status(customer_id)["used"], 0)
        with sqlite3.connect(self.db.db_path) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM recommendations WHERE customer_id=?", (customer_id,),
                ).fetchone()[0],
                0,
            )
        metrics = self.client.get(
            "/api/v1/metrics", headers=self.headers("SBI-OPS-METRICS", "ops"),
        )
        self.assertIn("saarthi_rollout_controls_shadow 1", metrics.text)
        self.assertNotIn("private@example.com", json.dumps(self.db.get_integrity_records()))

    def test_product_kill_switch_blocks_after_internal_selection_without_persisting_offer(self):
        disabled = self.client.post(
            "/api/v1/governance/rollout-controls/emergency-disable",
            json={
                "scope_type": "product", "scope_value": "SBI-LOAN-EXP01",
                "reason": "Contain this product journey while policy evidence is reviewed",
            },
            headers=self.headers("SBI-ADMIN-PRODUCT", "admin"),
        )
        self.assertEqual(disabled.status_code, 200)
        customer_id = "SBI-PRODUCT-BLOCK-001"
        self.client.post(
            "/api/v1/consent/grant",
            json={"purpose": "personalization"},
            headers=self.headers(customer_id),
        )
        result = self.client.post(
            "/api/v1/orchestrate",
            json={
                "signal": "Recurring credit card interest and debt",
                "segment": "corporate",
            },
            headers={
                **self.headers(customer_id),
                "Idempotency-Key": "product-kill-switch-001",
            },
        )
        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertEqual(body["delivery_mode"], "rollout_blocked")
        self.assertIsNone(body["recommended_product_id"])
        self.assertIsNone(body["recommendation_id"])
        self.assertEqual(self.db.get_nudge_budget_status(customer_id)["used"], 0)
        with sqlite3.connect(self.db.db_path) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM recommendations WHERE customer_id=?", (customer_id,),
                ).fetchone()[0],
                0,
            )

    def test_model_kill_switch_blocks_new_decision_after_classification(self):
        disabled = self.client.post(
            "/api/v1/governance/rollout-controls/emergency-disable",
            json={
                "scope_type": "model",
                "scope_value": f"{MODEL_ID}:{MODEL_VERSION}",
                "reason": "Contain the active detector version during drift investigation",
            },
            headers=self.headers("SBI-ADMIN-MODEL", "admin"),
        )
        self.assertEqual(disabled.status_code, 200)
        customer_id = "SBI-MODEL-BLOCK-001"
        self.client.post(
            "/api/v1/consent/grant",
            json={"purpose": "personalization"},
            headers=self.headers(customer_id),
        )
        result = self.client.post(
            "/api/v1/orchestrate",
            json={"signal": "Recurring credit card interest", "segment": "corporate"},
            headers={
                **self.headers(customer_id),
                "Idempotency-Key": "model-kill-switch-001",
            },
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["delivery_mode"], "rollout_blocked")
        self.assertIsNone(result.json()["recommended_product_id"])
        self.assertEqual(self.db.get_nudge_budget_status(customer_id)["used"], 0)


if __name__ == "__main__":
    unittest.main()
