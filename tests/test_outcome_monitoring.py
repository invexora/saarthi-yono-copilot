import json
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.audit_ledger import AuditLedger
from backend.database import DatabaseManager
from backend.outcome_monitoring import OutcomeMonitoringError, OutcomeMonitoringService
from backend.postgres_database import PostgresDatabaseManager
from backend.settings import Settings


class OutcomeMonitoringTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.temp_dir.name) / "outcomes.db"))
        self.ledger = AuditLedger(self.db, "outcome-ledger-secret-at-least-32-characters")
        self.service = OutcomeMonitoringService(
            self.db,
            "outcome-source-secret-at-least-32-characters",
            self.ledger,
            policy_id="test-approved-policy-v1",
            policy_status="approved",
            minimum_sample_size=2,
            maximum_complaint_rate=0.20,
            maximum_harm_rate=0.20,
            minimum_conversion_ratio=0.80,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _recommendation(self, suffix, segment):
        recommendation_id = f"outcome-recommendation-{suffix}"
        self.db.create_recommendation_with_status(
            recommendation_id,
            f"SBI-OUTCOME-{suffix}",
            "SBI-LOAN-EXP01",
            10.0,
            "high",
            initial_status="presented",
            evidence={"customer_segment": segment, "signal_category": "opportunity"},
        )
        return recommendation_id

    def _record(self, recommendation_id, event_id, outcome_type, impact_score=None):
        return self.service.record(
            recommendation_id,
            event_id,
            outcome_type,
            "analytics",
            "a" * 64,
            time.time(),
            impact_score,
        )

    def test_idempotent_observations_are_pseudonymous_and_conflicts_fail(self):
        recommendation_id = self._recommendation("001", "corporate")
        first = self._record(recommendation_id, "SBI-SOURCE-EVENT-001", "benefit", 0.7)
        replay = self.service.record(
            recommendation_id,
            "SBI-SOURCE-EVENT-001",
            "benefit",
            "analytics",
            "a" * 64,
            first["observation"]["occurred_at"],
            0.7,
        )
        conflict = self.service.record(
            recommendation_id,
            "SBI-SOURCE-EVENT-001",
            "harm",
            "analytics",
            "b" * 64,
            first["observation"]["occurred_at"],
            -0.5,
        )

        self.assertEqual(first["status"], "recorded")
        self.assertEqual(replay["status"], "replay")
        self.assertEqual(conflict["status"], "idempotency_conflict")
        self.assertEqual(first["observation"], replay["observation"])
        self.assertNotIn("source_event", json.dumps(first))
        with sqlite3.connect(self.db.db_path) as connection:
            stored_ref = connection.execute(
                "SELECT source_event_ref FROM recommendation_outcomes"
            ).fetchone()[0]
            self.assertEqual(len(stored_ref), 64)
            self.assertNotEqual(stored_ref, "SBI-SOURCE-EVENT-001")
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM recommendation_outcomes").fetchone()[0],
                1,
            )

    def test_concurrent_source_event_ingestion_records_once(self):
        recommendation_id = self._recommendation("CONCURRENT", "sme")
        occurred_at = time.time()

        def ingest(_):
            return self.service.record(
                recommendation_id, "CONCURRENT-SOURCE-EVENT-001", "converted",
                "analytics", "f" * 64, occurred_at,
            )["status"]

        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes = list(executor.map(ingest, range(8)))

        self.assertEqual(outcomes.count("recorded"), 1)
        self.assertEqual(outcomes.count("replay"), 7)
        self.assertEqual(self.db.get_system_metrics()["outcome_observations"], 1)

    def test_report_detects_harm_complaint_and_conversion_disparity(self):
        corporate = [self._recommendation(f"CORP-{index}", "corporate") for index in range(2)]
        student = [self._recommendation(f"STUDENT-{index}", "student") for index in range(2)]
        for index, recommendation_id in enumerate(corporate):
            self._record(recommendation_id, f"CORP-CONVERTED-{index}", "converted")
        self._record(student[0], "STUDENT-COMPLAINT", "complaint")
        self._record(student[1], "STUDENT-HARM", "harm", -0.8)

        report = self.service.report(30, "segment")
        groups = {group["group"]: group for group in report["groups"]}
        self.assertEqual(groups["corporate"]["rates"]["converted_rate"], 1.0)
        self.assertEqual(groups["student"]["rates"]["complaint_rate"], 0.5)
        self.assertEqual(groups["student"]["rates"]["harm_rate"], 0.5)
        self.assertEqual(
            {alert["alert_type"] for alert in report["alerts"]},
            {"complaint_rate", "harm_rate", "conversion_disparity"},
        )
        self.assertIn("not protected-class analysis", report["limitations"][0])

    def test_validation_export_and_erasure_cover_outcomes(self):
        recommendation_id = self._recommendation("ERASURE", "stressed")
        customer_id = "SBI-OUTCOME-ERASURE"
        recorded = self._record(recommendation_id, "ERASURE-EVENT-001", "opt_out")
        self.assertEqual(recorded["status"], "recorded")
        exported = self.db.export_customer_data(customer_id)
        self.assertEqual(len(exported["outcomes"]), 1)
        self.assertNotIn("source_event_ref", exported["outcomes"][0])
        self.assertNotIn("evidence_digest", exported["outcomes"][0])

        self.db.process_erasure_request(customer_id)
        self.assertEqual(self.db.get_customer_outcomes(customer_id), [])
        with sqlite3.connect(self.db.db_path) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM recommendation_outcomes").fetchone()[0],
                0,
            )

        with self.assertRaisesRegex(OutcomeMonitoringError, "harm_impact"):
            self.service.record(
                "missing-recommendation", "invalid-harm-event", "harm", "analytics",
                "a" * 64, time.time(), 0.5,
            )

    def test_sqlalchemy_portable_contract_supports_monitoring(self):
        database_url = f"sqlite+pysqlite:///{Path(self.temp_dir.name) / 'portable-outcomes.db'}"
        database = PostgresDatabaseManager(database_url)
        service = OutcomeMonitoringService(
            database, "portable-outcome-secret-at-least-32-characters",
            minimum_sample_size=1,
        )
        database.create_recommendation_with_status(
            "portable-outcome-recommendation",
            "SBI-PORTABLE-OUTCOME",
            "SBI-LOAN-EXP01",
            10.0,
            "high",
            evidence={"customer_segment": "corporate", "signal_category": "opportunity"},
        )
        result = service.record(
            "portable-outcome-recommendation", "portable-source-event-001",
            "complaint", "complaints", "c" * 64, time.time(), -0.2,
        )
        self.assertEqual(result["status"], "recorded")
        self.assertEqual(service.report()["groups"][0]["outcome_counts"]["complaint"], 1)


class OutcomeMonitoringApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "outcome-api.db")
        self.db = DatabaseManager(db_path)
        settings = Settings(
            db_path=db_path,
            auth_mode="development",
            decision_secret="outcome-api-decision-secret-at-least-32-chars",
            monitoring_policy_id="api-test-policy-v1",
            monitoring_policy_status="approved",
            monitoring_minimum_sample_size=1,
            monitoring_maximum_complaint_rate=0.0,
        )
        self.client = TestClient(create_app(settings, self.db))
        self.recommendation_id = "outcome-api-recommendation-001"
        self.db.create_recommendation_with_status(
            self.recommendation_id,
            "SBI-OUTCOME-API-CUSTOMER",
            "SBI-LOAN-EXP01",
            10.0,
            "high",
            evidence={"customer_segment": "corporate", "signal_category": "opportunity"},
        )

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    @staticmethod
    def headers(customer_id, role="customer"):
        return {
            "X-Saarthi-Demo-Customer": customer_id,
            "X-Saarthi-Demo-Role": role,
        }

    def test_role_gated_ingestion_reporting_and_metrics(self):
        payload = {
            "recommendationId": self.recommendation_id,
            "sourceEventId": "complaint-feed-event-001",
            "outcomeType": "complaint",
            "sourceSystem": "complaints",
            "evidenceDigest": "d" * 64,
            "occurredAt": time.time(),
            "impactScore": -0.4,
        }
        denied = self.client.post(
            "/api/v1/monitoring/outcomes",
            json=payload,
            headers=self.headers("SBI-CUSTOMER-DENIED"),
        )
        self.assertEqual(denied.status_code, 403)
        ops_headers = self.headers("SBI-OPS-MONITORING", "ops")
        recorded = self.client.post(
            "/api/v1/monitoring/outcomes", json=payload, headers=ops_headers,
        )
        replay = self.client.post(
            "/api/v1/monitoring/outcomes", json=payload, headers=ops_headers,
        )
        conflict = self.client.post(
            "/api/v1/monitoring/outcomes",
            json={**payload, "outcomeType": "converted"},
            headers=ops_headers,
        )
        self.assertEqual(recorded.status_code, 201)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(conflict.status_code, 409)
        self.assertNotIn("sourceEventId", recorded.text)
        self.assertNotIn("evidenceDigest", recorded.text)

        report = self.client.get(
            "/api/v1/monitoring/report?window_days=30&dimension=segment",
            headers=self.headers("SBI-AUDITOR-MONITORING", "auditor"),
        )
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json()["policy_status"], "approved")
        self.assertEqual(report.json()["alerts"][0]["alert_type"], "complaint_rate")
        metrics = self.client.get("/api/v1/metrics", headers=ops_headers)
        self.assertIn("saarthi_outcome_observations 1", metrics.text)
        self.assertIn("saarthi_monitoring_alerts 1", metrics.text)


if __name__ == "__main__":
    unittest.main()
