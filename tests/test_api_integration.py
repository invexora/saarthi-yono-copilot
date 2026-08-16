import tempfile
import time
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.database import DatabaseManager
from backend.settings import Settings
from backend.redis_streams import RedisEventStream
from backend.event_worker import EventConsumerWorker
from backend.neo4j_client import Neo4jProductGraph
from backend.dpdp_engine import DPDPEngine
from backend.fulfillment import SyntheticFulfillmentClient


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "api.db")
        self.settings = Settings(
            db_path=self.db_path,
            auth_mode="development",
            decision_secret="integration-test-decision-secret-32-chars",
            allowed_origins=("http://localhost:8000",),
        )
        self.database = DatabaseManager(self.db_path)
        self.client = TestClient(create_app(self.settings, self.database))

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    @staticmethod
    def identity_headers(customer_id="SBI-API-001", role="customer"):
        return {
            "X-Saarthi-Demo-Customer": customer_id,
            "X-Saarthi-Demo-Role": role,
        }

    @staticmethod
    def with_idempotency(headers, key):
        return {**headers, "Idempotency-Key": key}

    def test_consent_recommendation_authorization_lifecycle(self):
        headers = self.identity_headers()
        orchestrate_payload = {
            "signal": "Recurring credit card interest and debt",
            "details": "Email: api@example.com | PAN: ABCDE1234F",
            "segment": "corporate",
        }

        blocked = self.client.post(
            "/api/v1/orchestrate",
            json=orchestrate_payload,
            headers=self.with_idempotency(headers, "no-consent-0001"),
        )
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["delivery_mode"], "consent_required")

        granted = self.client.post(
            "/api/v1/consent/grant",
            json={"purpose": "personalization"},
            headers=headers,
        )
        self.assertEqual(granted.status_code, 200)

        recommendation_headers = self.with_idempotency(headers, "recommendation-0001")
        response = self.client.post("/api/v1/orchestrate", json=orchestrate_payload, headers=recommendation_headers)
        self.assertEqual(response.status_code, 200)
        recommendation = response.json()
        self.assertEqual(recommendation["delivery_mode"], "decision_token_required")
        self.assertNotIn("raw_details", recommendation)
        self.assertIsNone(recommendation["decision_token"])

        replayed = self.client.post("/api/v1/orchestrate", json=orchestrate_payload, headers=recommendation_headers)
        self.assertEqual(replayed.status_code, 200)
        self.assertEqual(replayed.headers["Idempotency-Replayed"], "true")
        self.assertEqual(replayed.json(), recommendation)
        self.assertEqual(replayed.content, response.content)
        self.assertEqual(self.database.get_nudge_budget_status("SBI-API-001")["used"], 1)

        authorization_payload = {"recommendationId": recommendation["recommendation_id"]}
        cross_customer = self.client.post(
            "/api/v1/decisions/authorize",
            json=authorization_payload,
            headers=self.identity_headers("SBI-API-OTHER"),
        )
        self.assertEqual(cross_customer.status_code, 404)

        authorized = self.client.post("/api/v1/decisions/authorize", json=authorization_payload, headers=headers)
        self.assertEqual(authorized.status_code, 200)
        self.assertEqual(authorized.json()["status"], "authorized")
        self.assertEqual(len(authorized.json()["decision_token"]), 64)

        replay = self.client.post("/api/v1/decisions/authorize", json=authorization_payload, headers=headers)
        self.assertEqual(replay.status_code, 409)
        self.assertEqual(replay.json()["status"], "already_authorized")

        execution_payload = {
            "recommendationId": recommendation["recommendation_id"],
            "decisionToken": authorized.json()["decision_token"],
        }
        wrong_token = self.client.post(
            "/api/v1/actions/execute",
            json={**execution_payload, "decisionToken": "0" * 64},
            headers=headers,
        )
        self.assertEqual(wrong_token.status_code, 403)
        executed = self.client.post("/api/v1/actions/execute", json=execution_payload, headers=headers)
        executed_again = self.client.post("/api/v1/actions/execute", json=execution_payload, headers=headers)
        self.assertEqual(executed.status_code, 200)
        self.assertEqual(executed.json()["status"], "fulfilled")
        self.assertEqual(executed_again.json()["status"], "already_fulfilled")
        self.assertEqual(executed.json()["fulfillment"]["reference"], executed_again.json()["fulfillment"]["reference"])

        revoked = self.client.post(
            "/api/v1/consent/revoke",
            json={"purpose": "personalization"},
            headers=headers,
        )
        self.assertEqual(revoked.status_code, 200)
        blocked_again = self.client.post(
            "/api/v1/orchestrate",
            json=orchestrate_payload,
            headers=self.with_idempotency(headers, "no-consent-0002"),
        )
        self.assertEqual(blocked_again.status_code, 403)

    def test_identity_is_required_and_cannot_be_overridden_by_body(self):
        no_identity = self.client.get("/api/v1/consent")
        self.assertEqual(no_identity.status_code, 401)

        forged_body = self.client.post(
            "/api/v1/orchestrate",
            json={
                "customerId": "SBI-SOMEONE-ELSE",
                "signal": "Branch cash deposit",
                "segment": "corporate",
            },
            headers=self.with_idempotency(self.identity_headers("SBI-BOUND-IDENTITY"), "forged-request-0001"),
        )
        self.assertEqual(forged_body.status_code, 422)

        missing_idempotency = self.client.post(
            "/api/v1/orchestrate",
            json={"signal": "Branch cash deposit", "segment": "corporate"},
            headers=self.identity_headers("SBI-BOUND-IDENTITY"),
        )
        self.assertEqual(missing_idempotency.status_code, 422)
        self.assertTrue(any(error["loc"][-1] == "Idempotency-Key" for error in missing_idempotency.json()["detail"]))

    def test_operational_endpoints_require_an_operational_role(self):
        denied = self.client.get("/api/v1/metrics", headers=self.identity_headers())
        allowed = self.client.get("/api/v1/metrics", headers=self.identity_headers(role="ops"))

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertIn("saarthi_dpdp_consents_active", allowed.text)

    def test_event_operations_are_role_gated_safe_and_replay_idempotently(self):
        stream = RedisEventStream(mode="memory")
        stream.publish_event(
            "SENSITIVE_FAILURE",
            "SBI-PRIVATE-CUSTOMER-001",
            {"secret": "must-not-leak"},
            "event-operations-source-001",
        )
        worker = EventConsumerWorker(
            stream,
            lambda _: (_ for _ in ()).throw(ValueError("private failure detail")),
            group_name=self.settings.event_consumer_group,
            max_delivery_attempts=3,
            min_idle_ms=0,
        )
        for _ in range(3):
            worker.process_once()

        with TestClient(create_app(self.settings, self.database, event_stream=stream)) as client:
            customer_headers = self.identity_headers("SBI-CUSTOMER-001")
            self.assertEqual(client.get("/api/v1/events/status", headers=customer_headers).status_code, 403)
            self.assertEqual(client.get("/api/v1/events/dead-letters", headers=customer_headers).status_code, 403)

            ops_headers = self.identity_headers("SBI-OPS-001", "ops")
            status_response = client.get("/api/v1/events/status", headers=ops_headers)
            dead_letters_response = client.get("/api/v1/events/dead-letters", headers=ops_headers)
            metrics_response = client.get("/api/v1/metrics", headers=ops_headers)

            self.assertEqual(status_response.status_code, 200)
            self.assertEqual(status_response.json()["dead_letters"], 1)
            self.assertFalse(status_response.json()["within_slo"])
            self.assertEqual(dead_letters_response.status_code, 200)
            serialized = dead_letters_response.text
            self.assertNotIn("SBI-PRIVATE-CUSTOMER-001", serialized)
            self.assertNotIn("must-not-leak", serialized)
            self.assertNotIn("private failure detail", serialized)
            self.assertIn("saarthi_event_dead_letters 1", metrics_response.text)

            admin_headers = self.with_idempotency(
                self.identity_headers("SBI-ADMIN-001", "admin"),
                "event-replay-001",
            )
            dead_letter_id = dead_letters_response.json()[0]["dead_letter_id"]
            first = client.post(
                f"/api/v1/events/dead-letters/{dead_letter_id}/replay",
                headers=admin_headers,
            )
            replay = client.post(
                f"/api/v1/events/dead-letters/{dead_letter_id}/replay",
                headers=admin_headers,
            )
            self.assertEqual(first.status_code, 200)
            self.assertFalse(first.json()["deduplicated"])
            self.assertTrue(replay.json()["deduplicated"])
            self.assertEqual(first.json()["event_id"], replay.json()["event_id"])
            self.assertEqual(client.get("/api/v1/events/status", headers=ops_headers).json()["dead_letters"], 0)

    def test_fulfillment_reconciliation_is_role_gated_and_preserves_mismatch(self):
        class ReversedSyntheticClient(SyntheticFulfillmentClient):
            def get_status(self, *_):
                return {"status": "reversed", "providerReason": "downstream reversal"}

        customer_id = "SBI-RECONCILIATION-PRIVATE"
        recommendation_id = "reconciliation-recommendation-001"
        dpdp = DPDPEngine(
            self.database,
            decision_secret=self.settings.decision_secret,
        )
        dpdp.grant_consent(customer_id, "personalization")
        self.database.create_recommendation(
            recommendation_id, customer_id, "SBI-TEST", 5.0, "high",
        )
        authorization = dpdp.authorize_recommendation(recommendation_id, customer_id)
        app = create_app(
            self.settings,
            self.database,
            fulfillment_client=ReversedSyntheticClient(),
        )

        with TestClient(app) as client:
            executed = client.post(
                "/api/v1/actions/execute",
                json={
                    "recommendationId": recommendation_id,
                    "decisionToken": authorization["decision_token"],
                },
                headers=self.identity_headers(customer_id),
            )
            customer_list = client.get(
                "/api/v1/fulfillment/reconciliations",
                headers=self.identity_headers(customer_id),
            )
            ops_headers = self.identity_headers("SBI-OPS-RECON-001", "ops")
            pending = client.get(
                "/api/v1/fulfillment/reconciliations?reconciliation_status=pending",
                headers=ops_headers,
            )
            reconciled = client.post(
                f"/api/v1/fulfillment/reconciliations/{recommendation_id}/run",
                headers=ops_headers,
            )
            requested_case = client.post(
                "/api/v1/operations/cases",
                json={
                    "recommendationId": recommendation_id,
                    "summary": "Escalate via ops@example.com for account 12345678901",
                },
                headers=ops_headers,
            )
            case_id = requested_case.json()["case"]["case_id"]
            customer_cases = client.get(
                "/api/v1/operations/cases",
                headers=self.identity_headers(customer_id),
            )
            ops_approval = client.post(
                f"/api/v1/operations/cases/{case_id}/approve",
                headers=ops_headers,
            )
            admin_headers = self.identity_headers("SBI-ADMIN-RECON-001", "admin")
            approved_case = client.post(
                f"/api/v1/operations/cases/{case_id}/approve",
                headers=admin_headers,
            )
            submitted_case = client.post(
                f"/api/v1/operations/cases/{case_id}/submit",
                headers=ops_headers,
            )
            ops_acknowledge = client.post(
                f"/api/v1/fulfillment/reconciliations/{recommendation_id}/acknowledge",
                json={"note": "Escalated to operations"},
                headers=ops_headers,
            )
            admin_acknowledge = client.post(
                f"/api/v1/fulfillment/reconciliations/{recommendation_id}/acknowledge",
                json={"note": "Escalated to SBI settlement operations"},
                headers=admin_headers,
            )
            metrics = client.get("/api/v1/metrics", headers=ops_headers)

        self.assertEqual(executed.status_code, 200)
        self.assertEqual(customer_list.status_code, 403)
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(len(pending.json()), 1)
        self.assertNotIn(customer_id, pending.text)
        self.assertEqual(reconciled.status_code, 200)
        self.assertEqual(reconciled.json()["status"], "mismatch")
        self.assertEqual(reconciled.json()["reconciliation"]["provider_status"], "reversed")
        self.assertNotIn("providerReason", reconciled.text)
        self.assertEqual(requested_case.status_code, 201)
        self.assertIn("[MASKED EMAIL]", requested_case.json()["case"]["safe_summary"])
        self.assertIn("[MASKED ACCOUNT]", requested_case.json()["case"]["safe_summary"])
        self.assertNotIn(customer_id, requested_case.text)
        self.assertEqual(customer_cases.status_code, 403)
        self.assertEqual(ops_approval.status_code, 403)
        self.assertEqual(approved_case.status_code, 200)
        self.assertEqual(submitted_case.status_code, 200)
        self.assertEqual(submitted_case.json()["case"]["status"], "open")
        self.assertNotIn("requested_by_ref", submitted_case.text)
        self.assertNotIn("approved_by_ref", submitted_case.text)
        self.assertEqual(ops_acknowledge.status_code, 403)
        self.assertEqual(admin_acknowledge.status_code, 200)
        self.assertEqual(admin_acknowledge.json()["reconciliation"]["status"], "mismatch")
        self.assertIn("saarthi_fulfillment_reconciliation_mismatches 1", metrics.text)
        self.assertIn("saarthi_operations_cases_open 1", metrics.text)

    def test_health_reports_auth_and_migration_state(self):
        response = self.client.get("/api/v1/health")
        readiness = self.client.get("/api/v1/ready")

        self.assertEqual(response.status_code, 200)
        health = response.json()
        self.assertEqual(health["auth_mode"], "development")
        self.assertEqual(health["applied_migrations"], ["001_core", "002_recommendations", "003_idempotency", "004_governance", "005_review_evidence", "006_offer_delivery", "007_fulfillment", "008_event_processing", "009_fulfillment_reconciliation", "010_operations_cases", "011_rollout_controls", "012_outcome_monitoring", "013_model_rollout_scope", "014_governed_artifacts"])
        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(readiness.json()["status"], "ready")
        self.assertTrue(all(item["ready"] for item in readiness.json()["dependencies"]))

    def test_product_catalog_exposes_governance_metadata(self):
        response = self.client.get("/api/v1/products", headers=self.identity_headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 20)
        self.assertTrue(all(product["catalog_version"] for product in response.json()))
        self.assertTrue(all(product["effective_from"] for product in response.json()))

    def test_high_risk_recommendation_requires_independent_review(self):
        governed_settings = Settings(
            db_path=self.db_path,
            auth_mode="development",
            decision_secret="integration-test-decision-secret-32-chars",
            audit_secret="integration-test-audit-secret-32-chars-long",
            allowed_origins=("http://localhost:8000",),
            high_risk_review_mode="required",
        )
        customer_headers = self.identity_headers("SBI-REVIEW-001")
        app = create_app(governed_settings, self.database)
        with TestClient(app) as client:
            client.post("/api/v1/consent/grant", json={"purpose": "personalization"}, headers=customer_headers)
            result = client.post(
                "/api/v1/orchestrate",
                json={"signal": "Recurring credit card interest and debt", "segment": "corporate"},
                headers=self.with_idempotency(customer_headers, "human-review-0001"),
            ).json()
            self.assertEqual(result["delivery_mode"], "human_review_required")
            self.assertEqual(result["decision_outcome"], "review_required")
            self.assertIn("HIGH_RISK_HUMAN_REVIEW_REQUIRED", result["reason_codes"])
            self.assertIsNotNone(result["review_id"])
            self.assertIsNone(result["recommended_product_id"])
            self.assertIsNone(result["interest_rate"])
            self.assertIsNone(result["neo4j_query"])
            self.assertEqual(result["policy_evidence"]["approval_status"], "approved")
            self.assertEqual(self.database.get_nudge_budget_status("SBI-REVIEW-001")["used"], 0)

            blocked = client.post(
                "/api/v1/decisions/authorize",
                json={"recommendationId": result["recommendation_id"]},
                headers=customer_headers,
            )
            self.assertEqual(blocked.status_code, 409)
            self.assertEqual(blocked.json()["status"], "review_required")

            reviewer_headers = self.identity_headers("SBI-REVIEWER-001", "reviewer")
            queue = client.get("/api/v1/reviews", headers=reviewer_headers)
            self.assertEqual(queue.status_code, 200)
            self.assertEqual(queue.json()[0]["review_id"], result["review_id"])
            self.assertEqual(queue.json()[0]["evidence"]["policy"]["policy_id"], result["policy_evidence"]["policy_id"])
            approved = client.post(
                f"/api/v1/reviews/{result['review_id']}/decision",
                json={"decision": "approved", "reason": "KFS and suitability evidence checked"},
                headers=reviewer_headers,
            )
            self.assertEqual(approved.status_code, 200)

            not_presented = client.post(
                "/api/v1/decisions/authorize",
                json={"recommendationId": result["recommendation_id"]},
                headers=customer_headers,
            )
            self.assertEqual(not_presented.status_code, 409)
            self.assertEqual(not_presented.json()["status"], "offer_not_presented")

            cross_customer = client.get(
                f"/api/v1/recommendations/{result['recommendation_id']}",
                headers=self.identity_headers("SBI-OTHER-001"),
            )
            self.assertEqual(cross_customer.status_code, 404)

            presented = client.get(
                f"/api/v1/recommendations/{result['recommendation_id']}",
                headers=customer_headers,
            )
            self.assertEqual(presented.status_code, 200)
            self.assertEqual(presented.json()["recommendation"]["product_id"], queue.json()[0]["evidence"]["product_id"])
            self.assertEqual(self.database.get_nudge_budget_status("SBI-REVIEW-001")["used"], 1)

            authorized = client.post(
                "/api/v1/decisions/authorize",
                json={"recommendationId": result["recommendation_id"]},
                headers=customer_headers,
            )
            self.assertEqual(authorized.status_code, 200)

            integrity = client.get("/api/v1/audit/integrity", headers=self.identity_headers(role="auditor"))
            self.assertTrue(integrity.json()["valid"])
            self.assertGreaterEqual(integrity.json()["records_checked"], 4)

    def test_readiness_fails_when_a_required_dependency_is_unhealthy(self):
        class UnhealthyCatalog:
            def health(self):
                return {"name": "product_catalog", "mode": "test", "ready": False, "detail": "offline"}

            def close(self):
                return None

            def list_products(self):
                return []

            def query_eligibility(self, *_):
                raise ConnectionError("offline")

        app = create_app(
            self.settings,
            self.database,
            event_stream=RedisEventStream(mode="memory"),
            product_catalog=UnhealthyCatalog(),
        )
        with TestClient(app) as client:
            response = client.get("/api/v1/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "not_ready")

    def test_redis_mode_readiness_requires_a_live_consumer_heartbeat(self):
        redis_settings = Settings(
            db_path=self.db_path,
            auth_mode="development",
            decision_secret="integration-test-decision-secret-32-chars",
            allowed_origins=("http://localhost:8000",),
            event_stream_mode="redis",
        )
        stream = RedisEventStream(mode="memory")
        app = create_app(redis_settings, self.database, event_stream=stream)

        with TestClient(app) as client:
            missing_worker = client.get("/api/v1/ready")
            EventConsumerWorker(stream, lambda _: None).process_once()
            live_worker = client.get("/api/v1/ready")

        self.assertEqual(missing_worker.status_code, 503)
        self.assertEqual(live_worker.status_code, 200)
        consumer = next(item for item in live_worker.json()["dependencies"] if item["name"] == "event_consumer")
        self.assertEqual(consumer["detail"], "active_consumers=1")

    def test_dependency_failure_can_retry_same_idempotency_key_without_duplicate_event(self):
        class FlakyCatalog:
            def __init__(self):
                self.delegate = Neo4jProductGraph(mode="memory")
                self.calls = 0

            def health(self):
                return {"name": "product_catalog", "mode": "test", "ready": True, "detail": "flaky"}

            def close(self):
                return None

            def list_products(self):
                return self.delegate.list_products()

            def query_eligibility(self, *args):
                self.calls += 1
                if self.calls == 1:
                    raise ConnectionError("transient outage")
                return self.delegate.query_eligibility(*args)

        customer_id = "SBI-RETRY-001"
        headers = self.with_idempotency(self.identity_headers(customer_id), "retry-same-key-001")
        stream = RedisEventStream(mode="memory")
        app = create_app(self.settings, self.database, event_stream=stream, product_catalog=FlakyCatalog())
        payload = {"signal": "Branch cash deposit", "segment": "corporate"}

        with TestClient(app) as client:
            client.post(
                "/api/v1/consent/grant",
                json={"purpose": "personalization"},
                headers=self.identity_headers(customer_id),
            )
            failed = client.post("/api/v1/orchestrate", json=payload, headers=headers)
            retried = client.post("/api/v1/orchestrate", json=payload, headers=headers)

        self.assertEqual(failed.status_code, 503)
        self.assertEqual(retried.status_code, 200)
        self.assertNotIn("Idempotency-Replayed", retried.headers)
        self.assertEqual(stream.get_stream_info()["length"], 1)
        self.assertEqual(self.database.get_nudge_budget_status(customer_id)["used"], 1)


class JwtAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "jwt.db")
        self.secret = "jwt-integration-secret-at-least-32-characters"
        self.settings = Settings(
            db_path=db_path,
            auth_mode="jwt",
            jwt_secret=self.secret,
            jwt_issuer="test-sbi-identity",
            jwt_audience="test-saarthi-api",
            decision_secret="decision-integration-secret-at-least-32",
            allowed_origins=("http://localhost:8000",),
        )
        self.database = DatabaseManager(db_path)
        self.client = TestClient(create_app(self.settings, self.database))

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def token(self, **overrides):
        now = int(time.time())
        claims = {
            "sub": "sbi-user-123",
            "customer_id": "SBI-JWT-001",
            "roles": ["customer"],
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
            "iat": now,
            "exp": now + 300,
        }
        claims.update(overrides)
        return jwt.encode(claims, self.secret, algorithm="HS256")

    def test_valid_signed_identity_is_accepted(self):
        headers = {
            "Authorization": f"Bearer {self.token()}",
            "X-Saarthi-Demo-Customer": "SBI-HEADER-MUST-NOT-WIN",
        }
        response = self.client.post(
            "/api/v1/consent/grant",
            json={"purpose": "personalization"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.database.get_consent_status("SBI-JWT-001")), 1)
        self.assertEqual(self.database.get_consent_status("SBI-HEADER-MUST-NOT-WIN"), [])

    def test_expired_or_wrongly_signed_identity_is_rejected(self):
        expired = self.token(exp=int(time.time()) - 1)
        wrong_signature = jwt.encode(
            {
                "sub": "attacker",
                "customer_id": "SBI-JWT-001",
                "iss": self.settings.jwt_issuer,
                "aud": self.settings.jwt_audience,
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
            },
            "wrong-secret-at-least-32-characters-long",
            algorithm="HS256",
        )

        for token in (expired, wrong_signature):
            response = self.client.get(
                "/api/v1/consent",
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(response.status_code, 401)


class SettingsSecurityTests(unittest.TestCase):
    def test_jwt_mode_fails_closed_without_strong_secrets(self):
        with self.assertRaises(RuntimeError):
            Settings(auth_mode="jwt", decision_secret="short").validate()

        with self.assertRaises(RuntimeError):
            Settings(
                auth_mode="jwt",
                jwt_secret="short",
                decision_secret="long-enough-decision-secret-for-tests",
            ).validate()

    def test_live_adapter_modes_fail_closed_without_credentials(self):
        with self.assertRaises(RuntimeError):
            Settings(
                auth_mode="development",
                decision_secret="long-enough-decision-secret-for-tests",
                product_catalog_mode="neo4j",
            ).validate()

        with self.assertRaises(RuntimeError):
            Settings(
                auth_mode="development",
                decision_secret="long-enough-decision-secret-for-tests",
                deployment_mode="production",
                audit_secret="long-enough-audit-secret-for-tests-123",
                customer_context_mode="synthetic",
            ).validate()

        Settings(
            auth_mode="development",
            decision_secret="long-enough-decision-secret-for-tests",
            signal_detection_mode="model",
        ).validate()

    def test_oidc_rejects_symmetric_algorithms_and_production_requires_oidc(self):
        with self.assertRaises(RuntimeError):
            Settings(
                auth_mode="oidc",
                oidc_jwks_url="https://identity.example/jwks",
                oidc_algorithms=("HS256",),
                decision_secret="long-enough-decision-secret-for-tests",
            ).validate()

        valid_production = Settings(
            auth_mode="oidc",
            oidc_jwks_url="https://identity.example/jwks",
            oidc_algorithms=("RS256",),
            decision_secret="long-enough-decision-secret-for-tests",
            deployment_mode="production",
            audit_secret="long-enough-audit-secret-for-tests-123",
            database_url="postgresql+psycopg://example",
            event_stream_mode="redis",
            product_catalog_mode="neo4j",
            neo4j_password="secret",
            high_risk_review_mode="required",
            artifact_feed_mode="signed",
            artifact_signing_public_key="test-public-key",
            artifact_signing_key_id="test-key-id",
            signal_detection_mode="sbi_api",
            signal_detection_url="https://signals.example",
            signal_detection_token="token",
            data_residency="India",
            customer_context_mode="sbi_api",
            customer_context_url="https://context.example",
            customer_context_token="token",
            fulfillment_mode="sbi_api",
            fulfillment_url="https://fulfillment.example",
            fulfillment_token="token",
            case_management_mode="sbi_api",
            case_management_url="https://cases.example",
            case_management_token="token",
            monitoring_policy_id="sbi-approved-outcomes-v1",
            monitoring_policy_status="approved",
        )
        valid_production.validate()
        with self.assertRaisesRegex(RuntimeError, "signed product and policy artifacts"):
            replace(
                valid_production,
                artifact_feed_mode="local",
            ).validate()

        with self.assertRaisesRegex(RuntimeError, "public key and key ID"):
            replace(
                valid_production,
                artifact_signing_public_key=None,
                artifact_signing_key_id=None,
            ).validate()

        with self.assertRaisesRegex(RuntimeError, "signal detection"):
            replace(
                valid_production,
                signal_detection_mode="rules",
                signal_detection_url=None,
                signal_detection_token=None,
            ).validate()

        with self.assertRaises(RuntimeError):
            Settings(
                auth_mode="jwt",
                jwt_secret="long-enough-jwt-secret-for-tests-123",
                decision_secret="long-enough-decision-secret-for-tests",
                deployment_mode="production",
                audit_secret="long-enough-audit-secret-for-tests-123",
                database_url="postgresql+psycopg://example",
                event_stream_mode="redis",
                product_catalog_mode="neo4j",
                neo4j_password="secret",
                high_risk_review_mode="required",
                data_residency="India",
                customer_context_mode="sbi_api",
                customer_context_url="https://context.example",
                customer_context_token="token",
            ).validate()

    def test_production_worker_validates_only_its_owned_dependencies(self):
        worker_settings = Settings(
            deployment_mode="production",
            data_residency="India",
            database_url="postgresql+psycopg://example",
            event_stream_mode="redis",
            decision_secret="long-enough-decision-secret-for-tests",
            audit_secret="long-enough-audit-secret-for-tests-123",
            fulfillment_mode="sbi_api",
            fulfillment_url="https://fulfillment.example",
            fulfillment_token="workload-token",
            case_management_mode="sbi_api",
            case_management_url="https://cases.example",
            case_management_token="workload-token",
        )
        worker_settings.validate_worker()

        with self.assertRaises(RuntimeError):
            Settings(
                deployment_mode="production",
                data_residency="India",
                database_url="postgresql+psycopg://example",
                event_stream_mode="redis",
                decision_secret="long-enough-decision-secret-for-tests",
                audit_secret="long-enough-audit-secret-for-tests-123",
                fulfillment_mode="sbi_api",
                fulfillment_url="https://fulfillment.example",
                fulfillment_token="workload-token",
                case_management_mode="synthetic",
            ).validate_worker()

        with self.assertRaises(RuntimeError):
            Settings(
                deployment_mode="production",
                data_residency="India",
                database_url="postgresql+psycopg://example",
                event_stream_mode="redis",
                decision_secret="long-enough-decision-secret-for-tests",
                audit_secret="long-enough-audit-secret-for-tests-123",
                fulfillment_mode="synthetic",
            ).validate_worker()



class OidcAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "oidc.db")
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.settings = Settings(
            db_path=db_path,
            auth_mode="oidc",
            oidc_jwks_url="https://identity.example/.well-known/jwks.json",
            oidc_algorithms=("RS256",),
            jwt_issuer="test-sbi-oidc",
            jwt_audience="test-saarthi-api",
            decision_secret="oidc-decision-secret-at-least-32-characters",
            allowed_origins=("http://localhost:8000",),
        )
        self.database = DatabaseManager(db_path)
        self.client = TestClient(create_app(self.settings, self.database))

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def token(self, key=None, **overrides):
        now = int(time.time())
        claims = {
            "sub": "sbi-oidc-user-123",
            "customer_id": "SBI-OIDC-001",
            "roles": ["customer", "ops"],
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
            "iat": now,
            "exp": now + 300,
        }
        claims.update(overrides)
        return jwt.encode(claims, key or self.private_key, algorithm="RS256", headers={"kid": "test-key-1"})

    def test_valid_asymmetric_identity_and_roles_are_accepted(self):
        with patch.object(jwt.PyJWKClient, "get_signing_key_from_jwt", return_value=SimpleNamespace(key=self.private_key.public_key())):
            consent = self.client.post(
                "/api/v1/consent/grant",
                json={"purpose": "personalization"},
                headers={"Authorization": f"Bearer {self.token()}"},
            )
            metrics = self.client.get(
                "/api/v1/metrics",
                headers={"Authorization": f"Bearer {self.token()}"},
            )

        self.assertEqual(consent.status_code, 200)
        self.assertEqual(metrics.status_code, 200)

    def test_wrong_audience_signature_and_missing_required_claim_are_rejected(self):
        tokens = (
            self.token(aud="wrong-audience"),
            self.token(key=self.other_private_key),
            self.token(customer_id=None),
        )
        with patch.object(jwt.PyJWKClient, "get_signing_key_from_jwt", return_value=SimpleNamespace(key=self.private_key.public_key())):
            responses = [self.client.get("/api/v1/consent", headers={"Authorization": f"Bearer {token}"}) for token in tokens]

        self.assertEqual([response.status_code for response in responses], [401, 401, 401])

if __name__ == "__main__":
    unittest.main()
