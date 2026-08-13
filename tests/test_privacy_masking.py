import copy
import json
import tempfile
import unittest
from pathlib import Path

from backend.audit_ledger import AuditLedger
from backend.database import DatabaseManager
from backend.guardrails import InputGuardian
from backend.orchestrator import SaarthiAgentOrchestrator


RAW_IDENTIFIERS = {
    "pan": "ABCDE1234F",
    "aadhaar": "4532 9981 1204",
    "email": "priya.sharma@example.com",
    "mobile": "+91 98765 43210",
    "account": "12345678901",
    "card": "4111 1111 1111 1111",
    "upi": "priya.sharma@oksbi",
    "passport": "K1234567",
}


class InputGuardianMaskingTests(unittest.TestCase):
    def setUp(self):
        self.guardian = InputGuardian()

    def test_masks_supported_identifiers_with_stable_tokens(self):
        payload = " | ".join(f"{name}: {value}" for name, value in RAW_IDENTIFIERS.items())

        masked = self.guardian.mask_pii(payload)

        for name, raw_value in RAW_IDENTIFIERS.items():
            self.assertNotIn(raw_value, masked)
            self.assertIn(InputGuardian.MASKS[name], masked)
        self.assertEqual(self.guardian.mask_pii(masked), masked)

    def test_recursively_masks_structured_payload_without_mutating_input(self):
        payload = {
            "customer": {
                "PAN": RAW_IDENTIFIERS["pan"],
                "contacts": [
                    {"emailAddress": RAW_IDENTIFIERS["email"]},
                    {"mobileNumber": 9876543210},
                    f"Alternative phone {RAW_IDENTIFIERS['mobile']}",
                ],
                "accounts": [
                    {
                        "accountNumber": 12345678901,
                        "payment": {"vpa": "customer@unlistedbank"},
                    },
                ],
                "documents": ({"passportNo": RAW_IDENTIFIERS["passport"]},),
            },
            "card_number": RAW_IDENTIFIERS["card"],
            "safe": {"balance": 92000, "status": "ACTIVE", "email_verified": True},
        }
        original = copy.deepcopy(payload)

        masked = self.guardian.mask_pii(payload)

        self.assertEqual(payload, original)
        self.assertEqual(masked["customer"]["PAN"], "[MASKED PAN]")
        self.assertEqual(masked["customer"]["contacts"][0]["emailAddress"], "[MASKED EMAIL]")
        self.assertEqual(masked["customer"]["contacts"][1]["mobileNumber"], "[MASKED MOBILE]")
        self.assertIn("[MASKED MOBILE]", masked["customer"]["contacts"][2])
        self.assertEqual(masked["customer"]["accounts"][0]["accountNumber"], "[MASKED ACCOUNT]")
        self.assertEqual(masked["customer"]["accounts"][0]["payment"]["vpa"], "[MASKED UPI]")
        self.assertEqual(masked["customer"]["documents"][0]["passportNo"], "[MASKED PASSPORT]")
        self.assertEqual(masked["card_number"], "[MASKED CARD]")
        self.assertEqual(masked["safe"], payload["safe"])

    def test_obvious_non_identifiers_and_longer_embedded_values_are_preserved(self):
        payload = (
            "Rate 7.80%; order 1234567890123; long card-like 41111111111111111; "
            "embedded XABCDE1234FZ; passport-like AA1234567; support@home; "
            "email_verified=true"
        )

        self.assertEqual(self.guardian.mask_pii(payload), payload)


class AuditLedgerMaskingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.temp_dir.name) / "privacy-ledger.db"))
        self.ledger = AuditLedger(self.db, "privacy-ledger-test-secret-at-least-32-chars")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_nested_audit_payload_is_masked_before_hashing_and_persistence(self):
        customer_id = "SBI-PRIVACY-LEDGER-001"
        payload = {
            "contact": {
                "email": RAW_IDENTIFIERS["email"],
                "mobile": RAW_IDENTIFIERS["mobile"],
            },
            "identifiers": [
                RAW_IDENTIFIERS["pan"],
                RAW_IDENTIFIERS["aadhaar"],
                RAW_IDENTIFIERS["account"],
                RAW_IDENTIFIERS["card"],
                RAW_IDENTIFIERS["upi"],
                RAW_IDENTIFIERS["passport"],
            ],
        }

        self.ledger.append(customer_id, "privacy_boundary_test", payload)

        records = self.db.get_integrity_records()
        serialized = json.dumps(records, ensure_ascii=False)
        self.assertNotIn(customer_id, serialized)
        for raw_value in RAW_IDENTIFIERS.values():
            self.assertNotIn(raw_value, serialized)
        persisted_payload = json.loads(records[0]["payload_json"])
        for marker in InputGuardian.MASKS.values():
            self.assertIn(marker, json.dumps(persisted_payload))
        self.assertTrue(self.ledger.verify()["valid"])


class OrchestrationPrivacyBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.temp_dir.name) / "privacy-orchestration.db"))
        self.ledger = AuditLedger(self.db, "privacy-orchestration-audit-secret-32-chars")
        self.orchestrator = SaarthiAgentOrchestrator(self.db, audit_ledger=self.ledger)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_public_result_event_and_audits_do_not_echo_submitted_identifiers(self):
        customer_id = "SBI-PRIVACY-ORCHESTRATION-001"
        self.orchestrator.dpdp_engine.grant_consent(customer_id, "personalization")
        signal = (
            f"Branch deposit for {RAW_IDENTIFIERS['email']} with PAN {RAW_IDENTIFIERS['pan']} "
            f"and UPI {RAW_IDENTIFIERS['upi']}"
        )
        details = " | ".join(f"{name}: {value}" for name, value in RAW_IDENTIFIERS.items())

        result = self.orchestrator.run_trace(
            signal=signal,
            details=details,
            customer_segment="corporate",
            customer_id=customer_id,
            idempotency_key="privacy-orchestration-001",
        )

        event = self.orchestrator.redis_stream.consume_events(1)[0]
        audit_logs = self.db.get_audit_logs(customer_id)
        integrity_records = self.db.get_integrity_records()
        boundary_values = {
            "public response": json.dumps(result, ensure_ascii=False),
            "event payload": json.dumps(event["payload"], ensure_ascii=False),
            "operational audit": json.dumps(audit_logs, ensure_ascii=False),
            "integrity audit": json.dumps(integrity_records, ensure_ascii=False),
        }

        for boundary, serialized in boundary_values.items():
            for raw_value in RAW_IDENTIFIERS.values():
                self.assertNotIn(raw_value, serialized, boundary)

        self.assertNotIn("raw_details", result)
        for marker in InputGuardian.MASKS.values():
            self.assertIn(marker, result["masked_details"])
        self.assertIn("[MASKED EMAIL]", result["raw_signal"])
        self.assertIn("[MASKED PAN]", result["raw_signal"])
        self.assertIn("[MASKED UPI]", result["raw_signal"])
        self.assertIn("[MASKED EMAIL]", event["payload"]["signal"])
        self.assertIn("[MASKED PAN]", audit_logs[0]["signal"])
        self.assertTrue(self.ledger.verify()["valid"])


if __name__ == "__main__":
    unittest.main()
