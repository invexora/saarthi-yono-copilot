import json
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from backend.database import DatabaseManager
from backend.dpdp_engine import DPDPEngine
from backend.fulfillment import SbiFulfillmentClient, SyntheticFulfillmentClient
from backend.fulfillment_service import FulfillmentService
from backend.reconciliation_service import FulfillmentReconciliationService


class FulfillmentLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.temp_dir.name) / "fulfillment.db"))
        self.dpdp = DPDPEngine(self.db, decision_secret="fulfillment-decision-secret-32-chars-long")
        self.customer_id = "SBI-FULFILL-001"
        self.recommendation_id = "fulfillment-recommendation-001"
        self.dpdp.grant_consent(self.customer_id, "personalization")
        self.db.create_recommendation(self.recommendation_id, self.customer_id, "SBI-TEST", 5.0, "high")
        self.authorization = self.dpdp.authorize_recommendation(self.recommendation_id, self.customer_id)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_execution_is_token_bound_and_replay_returns_same_completion(self):
        service = FulfillmentService(self.db, SyntheticFulfillmentClient(), consent_engine=self.dpdp)

        with sqlite3.connect(self.db.db_path) as conn:
            stored_token = conn.execute(
                "SELECT decision_token FROM recommendations WHERE recommendation_id=?",
                (self.recommendation_id,),
            ).fetchone()[0]
        self.assertNotEqual(stored_token, self.authorization["decision_token"])

        wrong = service.execute(self.recommendation_id, self.customer_id, "0" * 64)
        first = service.execute(self.recommendation_id, self.customer_id, self.authorization["decision_token"])
        replay = service.execute(self.recommendation_id, self.customer_id, self.authorization["decision_token"])

        self.assertEqual(wrong["status"], "invalid_token")
        self.assertEqual(first["status"], "fulfilled")
        self.assertEqual(replay["status"], "already_fulfilled")
        self.assertEqual(first["fulfillment"]["reference"], replay["fulfillment"]["reference"])

    def test_transient_failure_releases_claim_for_safe_retry(self):
        class FlakyClient:
            calls = 0

            def execute(self, recommendation, customer_id, idempotency_key):
                self.calls += 1
                if self.calls == 1:
                    raise ConnectionError("offline")
                return SyntheticFulfillmentClient().execute(recommendation, customer_id, idempotency_key)

        client = FlakyClient()
        service = FulfillmentService(self.db, client, consent_engine=self.dpdp)
        failed = service.execute(self.recommendation_id, self.customer_id, self.authorization["decision_token"])
        retried = service.execute(self.recommendation_id, self.customer_id, self.authorization["decision_token"])

        self.assertEqual(failed["status"], "dependency_unavailable")
        self.assertEqual(retried["status"], "fulfilled")
        self.assertEqual(client.calls, 2)

    def test_provider_response_is_allowlisted_before_storage_and_customer_output(self):
        class VerboseClient:
            def execute(self, *_):
                return {
                    "status": "completed",
                    "reference": "SBI-SAFE-REF-001",
                    "provider": "sbi-test",
                    "completed_at": "2026-08-11T00:00:00Z",
                    "accountNumber": "12345678901",
                    "internalNote": "must not cross boundary",
                }

        result = FulfillmentService(
            self.db, VerboseClient(), consent_engine=self.dpdp,
        ).execute(self.recommendation_id, self.customer_id, self.authorization["decision_token"])

        self.assertEqual(result["status"], "fulfilled")
        self.assertNotIn("accountNumber", str(result))
        self.assertNotIn("internalNote", str(result))
        stored = self.db.claim_execution(
            self.recommendation_id, self.customer_id, self.authorization["decision_token"],
        )[0]["fulfillment_response"]
        self.assertNotIn("accountNumber", stored)

    def test_invalid_provider_completion_is_not_persisted_or_reconciled(self):
        class InvalidClient:
            def execute(self, *_):
                return {"status": "accepted", "reference": ""}

        result = FulfillmentService(
            self.db, InvalidClient(), consent_engine=self.dpdp,
        ).execute(self.recommendation_id, self.customer_id, self.authorization["decision_token"])

        self.assertEqual(result["status"], "dependency_unavailable")
        self.assertIsNone(self.db.get_fulfillment_reconciliation(self.recommendation_id))

    def test_concurrent_execution_has_one_downstream_owner(self):
        class SlowClient:
            def __init__(self):
                self.calls = 0
                self.lock = threading.Lock()

            def execute(self, recommendation, customer_id, idempotency_key):
                with self.lock:
                    self.calls += 1
                time.sleep(0.05)
                return SyntheticFulfillmentClient().execute(recommendation, customer_id, idempotency_key)

        client = SlowClient()
        service = FulfillmentService(self.db, client, consent_engine=self.dpdp)
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(
                lambda _: service.execute(self.recommendation_id, self.customer_id, self.authorization["decision_token"]),
                range(8),
            ))

        self.assertEqual(client.calls, 1)
        self.assertEqual(sum(result["status"] == "fulfilled" for result in results), 1)
        # A waiter may observe the committed result before its turn reaches the
        # claim, in which case the documented idempotent replay is returned.
        self.assertTrue(all(
            result["status"] in {"fulfilled", "in_progress", "already_fulfilled"}
            for result in results
        ))

    def test_expired_action_token_and_cross_customer_are_rejected(self):
        with sqlite3.connect(self.db.db_path) as conn:
            conn.execute("UPDATE recommendations SET authorized_at=? WHERE recommendation_id=?", (time.time() - 301, self.recommendation_id))
            conn.commit()
        service = FulfillmentService(self.db, SyntheticFulfillmentClient(), consent_engine=self.dpdp)

        expired = service.execute(self.recommendation_id, self.customer_id, self.authorization["decision_token"])
        cross_customer = service.execute(self.recommendation_id, "SBI-OTHER-001", self.authorization["decision_token"])

        self.assertEqual(expired["status"], "token_expired")
        self.assertEqual(cross_customer["status"], "not_found")

    def _fulfill(self):
        service = FulfillmentService(self.db, SyntheticFulfillmentClient(), consent_engine=self.dpdp)
        result = service.execute(
            self.recommendation_id, self.customer_id, self.authorization["decision_token"],
        )
        self.assertEqual(result["status"], "fulfilled")
        return result

    def test_completed_fulfillment_is_reconciled_against_provider(self):
        fulfilled = self._fulfill()
        service = FulfillmentReconciliationService(self.db, SyntheticFulfillmentClient())

        result = service.reconcile(self.recommendation_id)
        replay = service.reconcile(self.recommendation_id)

        self.assertEqual(result["status"], "matched")
        self.assertEqual(replay["status"], "already_matched")
        self.assertEqual(result["reconciliation"]["fulfillment_reference"], fulfilled["fulfillment"]["reference"])
        stored = self.db.get_fulfillment_reconciliation(self.recommendation_id)
        self.assertEqual(len(stored["provider_response_digest"]), 64)
        self.assertEqual(stored["attempt_count"], 1)

    def test_reversed_provider_status_creates_acknowledgeable_mismatch(self):
        self._fulfill()

        class ReversedClient:
            def get_status(self, *_):
                return {"status": "reversed", "reason": "provider reversal"}

        service = FulfillmentReconciliationService(self.db, ReversedClient())
        mismatch = service.reconcile(self.recommendation_id)
        acknowledged = service.acknowledge_mismatch(
            self.recommendation_id, "operator-ref-hash", "Escalated by ops@example.com to SBI operations queue",
        )

        self.assertEqual(mismatch["status"], "mismatch")
        self.assertEqual(acknowledged["status"], "acknowledged")
        self.assertEqual(acknowledged["reconciliation"]["status"], "mismatch")
        self.assertIsNotNone(acknowledged["reconciliation"]["acknowledged_at"])
        self.assertNotIn("ops@example.com", acknowledged["reconciliation"]["acknowledgement_note"])
        self.assertIn("[MASKED EMAIL]", acknowledged["reconciliation"]["acknowledgement_note"])
        self.assertEqual(self.db.get_system_metrics()["reconciliation_mismatches"], 1)

    def test_pending_and_provider_failure_remain_retryable(self):
        self._fulfill()

        class StatusClient:
            calls = 0

            def get_status(self, reference, *_):
                self.calls += 1
                if self.calls == 1:
                    return {"status": "pending"}
                if self.calls == 2:
                    raise ConnectionError("offline")
                return {"status": "completed", "reference": reference}

        client = StatusClient()
        service = FulfillmentReconciliationService(self.db, client, retry_seconds=0)
        pending = service.reconcile(self.recommendation_id)
        unavailable = service.reconcile(self.recommendation_id)
        matched = service.reconcile(self.recommendation_id)

        self.assertEqual(pending["status"], "retry")
        self.assertEqual(unavailable["status"], "dependency_unavailable")
        self.assertEqual(unavailable["error_code"], "ConnectionError")
        self.assertEqual(matched["status"], "matched")
        self.assertEqual(client.calls, 3)

    def test_concurrent_reconciliation_has_one_provider_owner(self):
        self._fulfill()

        class SlowStatusClient:
            def __init__(self):
                self.calls = 0
                self.lock = threading.Lock()

            def get_status(self, reference, *_):
                with self.lock:
                    self.calls += 1
                time.sleep(0.05)
                return {"status": "completed", "reference": reference}

        client = SlowStatusClient()
        service = FulfillmentReconciliationService(self.db, client)
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: service.reconcile(self.recommendation_id), range(8)))

        self.assertEqual(client.calls, 1)
        self.assertEqual(sum(result["status"] == "matched" for result in results), 1)
        self.assertTrue(all(result["status"] in {"matched", "in_progress", "already_matched"} for result in results))


class SbiFulfillmentClientTests(unittest.TestCase):
    def test_adapter_sends_downstream_idempotency_key(self):
        result = {"status": "completed", "reference": "SBI-REF-001"}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps(result).encode()

        client = SbiFulfillmentClient("https://fulfillment.example", "service-token")
        with patch("backend.fulfillment.urlopen", return_value=Response()) as request:
            response = client.execute(
                {"recommendation_id": "rec-001", "product_id": "SBI-TEST"},
                "SBI-CUSTOMER-001",
                "rec-001",
            )

        sent_request = request.call_args.args[0]
        self.assertEqual(sent_request.headers["Idempotency-key"], "rec-001")
        self.assertEqual(response["reference"], "SBI-REF-001")

    def test_adapter_queries_and_validates_downstream_status(self):
        result = {"status": "completed", "reference": "SBI-REF-001"}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps(result).encode()

        client = SbiFulfillmentClient("https://fulfillment.example", "service-token")
        with patch("backend.fulfillment.urlopen", return_value=Response()) as request:
            response = client.get_status("SBI-REF-001", "rec-001")

        sent_url = request.call_args.args[0].full_url
        self.assertIn("/v1/actions/status?", sent_url)
        self.assertIn("reference=SBI-REF-001", sent_url)
        self.assertIn("recommendationId=rec-001", sent_url)
        self.assertEqual(response["status"], "completed")


if __name__ == "__main__":
    unittest.main()
