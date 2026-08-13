import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from backend.case_management import SbiCaseManagementClient, SyntheticCaseManagementClient
from backend.database import DatabaseManager
from backend.dpdp_engine import DPDPEngine
from backend.fulfillment import SyntheticFulfillmentClient
from backend.fulfillment_service import FulfillmentService
from backend.operations_case_service import OperationsCaseService
from backend.reconciliation_service import FulfillmentReconciliationService


class OperationsCaseLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = DatabaseManager(str(Path(self.temp_dir.name) / "cases.db"))
        self.customer_id = "SBI-CASE-PRIVATE-001"
        self.recommendation_id = "case-recommendation-001"
        self.dpdp = DPDPEngine(
            self.database,
            decision_secret="operations-case-decision-secret-32-chars",
        )
        self.dpdp.grant_consent(self.customer_id, "personalization")
        self.database.create_recommendation(
            self.recommendation_id, self.customer_id, "SBI-TEST", 5.0, "high",
        )
        authorization = self.dpdp.authorize_recommendation(
            self.recommendation_id, self.customer_id,
        )
        fulfilled = FulfillmentService(
            self.database, SyntheticFulfillmentClient(), consent_engine=self.dpdp,
        ).execute(self.recommendation_id, self.customer_id, authorization["decision_token"])
        self.assertEqual(fulfilled["status"], "fulfilled")

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_mismatch(self):
        class ReversedClient:
            def get_status(self, *_):
                return {"status": "reversed"}

        result = FulfillmentReconciliationService(
            self.database, ReversedClient(), retry_seconds=0,
        ).reconcile(self.recommendation_id)
        self.assertEqual(result["status"], "mismatch")

    def request_and_approve(self, client=None):
        self.create_mismatch()
        service = OperationsCaseService(
            self.database, client or SyntheticCaseManagementClient(),
            retry_seconds=0, sync_interval_seconds=1,
        )
        requested = service.request(
            self.recommendation_id,
            "requester-ref-a",
            "Escalate mismatch reported by ops@example.com",
        )
        self.assertEqual(requested["status"], "requested")
        case_id = requested["case"]["case_id"]
        approved = service.approve(case_id, "approver-ref-b")
        self.assertEqual(approved["status"], "approved")
        return service, case_id

    def test_request_is_idempotent_pii_masked_and_requires_a_mismatch(self):
        service = OperationsCaseService(self.database, SyntheticCaseManagementClient())
        rejected = service.request(
            self.recommendation_id, "requester-a", "No discrepancy exists yet",
        )
        self.assertEqual(rejected["status"], "mismatch_required")

        self.create_mismatch()
        first = service.request(
            self.recommendation_id, "requester-a",
            "Contact ops@example.com regarding account 12345678901",
        )
        replay = service.request(
            self.recommendation_id, "requester-c", "A different replay summary",
        )

        self.assertEqual(first["status"], "requested")
        self.assertEqual(replay["status"], "already_requested")
        self.assertEqual(first["case"]["case_id"], replay["case"]["case_id"])
        self.assertIn("[MASKED EMAIL]", first["case"]["safe_summary"])
        self.assertIn("[MASKED ACCOUNT]", first["case"]["safe_summary"])
        self.assertNotIn("requested_by_ref", first["case"])
        self.assertNotIn(self.customer_id, str(first))

    def test_four_eyes_approval_blocks_the_requesting_principal(self):
        self.create_mismatch()
        service = OperationsCaseService(self.database, SyntheticCaseManagementClient())
        requested = service.request(self.recommendation_id, "same-principal", "Escalate verified reversal")

        blocked = service.approve(requested["case"]["case_id"], "same-principal")
        approved = service.approve(requested["case"]["case_id"], "different-principal")

        self.assertEqual(blocked["status"], "four_eyes_required")
        self.assertEqual(approved["status"], "approved")

    def test_submission_is_idempotent_under_concurrency(self):
        class SlowClient(SyntheticCaseManagementClient):
            def __init__(self):
                self.calls = 0
                self.lock = threading.Lock()

            def create_case(self, case, idempotency_key):
                with self.lock:
                    self.calls += 1
                time.sleep(0.05)
                return super().create_case(case, idempotency_key)

        client = SlowClient()
        service, case_id = self.request_and_approve(client)
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: service.submit(case_id), range(8)))

        self.assertEqual(client.calls, 1)
        self.assertEqual(sum(result["status"] == "submitted" for result in results), 1)
        self.assertTrue(all(result["status"] in {"submitted", "in_progress", "invalid_state"} for result in results))
        stored = self.database.get_operations_case(case_id)
        self.assertEqual(stored["status"], "open")
        self.assertEqual(len(stored["provider_response_digest"]), 64)

    def test_submission_retry_reuses_case_id_and_sync_tracks_terminal_status(self):
        class FlakyResolvingClient(SyntheticCaseManagementClient):
            def __init__(self):
                self.create_keys = []

            def create_case(self, case, idempotency_key):
                self.create_keys.append(idempotency_key)
                if len(self.create_keys) == 1:
                    raise ConnectionError("offline")
                return super().create_case(case, idempotency_key)

            def get_status(self, external_reference, case_id):
                return {"status": "resolved", "reference": external_reference}

        client = FlakyResolvingClient()
        service, case_id = self.request_and_approve(client)

        failed = service.submit(case_id)
        submitted = service.submit(case_id)
        synchronized = service.sync(case_id)

        self.assertEqual(failed["status"], "dependency_unavailable")
        self.assertEqual(submitted["status"], "submitted")
        self.assertEqual(client.create_keys, [case_id, case_id])
        self.assertEqual(synchronized["status"], "synchronized")
        self.assertEqual(synchronized["case"]["status"], "resolved")
        self.assertEqual(
            self.database.get_fulfillment_reconciliation(self.recommendation_id)["status"],
            "mismatch",
        )

    def test_erasure_removes_customer_linked_case_and_reconciliation(self):
        service, case_id = self.request_and_approve()
        service.submit(case_id)

        self.database.process_erasure_request(self.customer_id)

        self.assertIsNone(self.database.get_operations_case(case_id))
        self.assertIsNone(self.database.get_fulfillment_reconciliation(self.recommendation_id))


class SbiCaseManagementClientTests(unittest.TestCase):
    def test_create_case_sends_data_minimized_idempotent_contract(self):
        provider_result = {
            "status": "open",
            "reference": "SBI-CASE-REF-001",
            "internalCustomerData": "must-not-return",
        }

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps(provider_result).encode()

        client = SbiCaseManagementClient("https://cases.example", "service-token")
        case = {
            "case_id": "case-001",
            "recommendation_id": "rec-001",
            "fulfillment_reference": "fulfill-ref-001",
            "safe_summary": "Verified reconciliation mismatch",
            "requested_by_ref": "must-not-send",
        }
        with patch("backend.case_management.urlopen", return_value=Response()) as request:
            result = client.create_case(case, "case-001")

        sent_request = request.call_args.args[0]
        sent_payload = json.loads(sent_request.data)
        self.assertEqual(sent_request.headers["Idempotency-key"], "case-001")
        self.assertNotIn("requested_by_ref", sent_payload)
        self.assertNotIn("customerId", sent_payload)
        self.assertNotIn("internalCustomerData", result)
        self.assertEqual(result["reference"], "SBI-CASE-REF-001")

    def test_case_status_query_is_reference_bound_and_allowlisted(self):
        provider_result = {
            "status": "resolved",
            "reference": "SBI-CASE-REF-002",
            "customerPayload": "must-not-return",
        }

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps(provider_result).encode()

        client = SbiCaseManagementClient("https://cases.example", "service-token")
        with patch("backend.case_management.urlopen", return_value=Response()) as request:
            result = client.get_status("SBI-CASE-REF-002", "case-002")

        url = request.call_args.args[0].full_url
        self.assertIn("reference=SBI-CASE-REF-002", url)
        self.assertIn("caseId=case-002", url)
        self.assertNotIn("customerPayload", result)
        self.assertEqual(result["status"], "resolved")


if __name__ == "__main__":
    unittest.main()
