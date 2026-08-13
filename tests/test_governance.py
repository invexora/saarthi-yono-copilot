import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.audit_ledger import AuditLedger
from backend.database import DatabaseManager
from backend.dpdp_engine import DPDPEngine
from backend.policy_catalog import PolicyCatalog


class PolicyGovernanceTests(unittest.TestCase):
    def test_policy_evidence_contains_approved_provenance(self):
        catalog = PolicyCatalog()
        evidence = catalog.retrieve_policy("explicit consent and data minimization")

        self.assertEqual(evidence["approval_status"], "approved")
        self.assertTrue(evidence["approved_by"])
        self.assertEqual(len(evidence["content_sha256"]), 64)
        self.assertTrue(evidence["manifest_version"])
        self.assertTrue(catalog.health()["ready"])

    def test_tampered_policy_manifest_fails_closed(self):
        source = Path(__file__).parents[1] / "backend" / "policies" / "manifest.json"
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "manifest.json"
            manifest = json.loads(source.read_text())
            manifest["policies"][0]["content"] += " unauthorized change"
            target.write_text(json.dumps(manifest))

            with self.assertRaisesRegex(RuntimeError, "integrity check failed"):
                PolicyCatalog(target)


class AuditLedgerGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.temp_dir.name) / "ledger.db"))
        self.ledger = AuditLedger(self.db, "governance-audit-test-secret-32-chars-long")
        self.dpdp = DPDPEngine(self.db, audit_ledger=self.ledger)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ledger_survives_erasure_without_raw_customer_identifier(self):
        customer_id = "SBI-LEDGER-001"
        self.dpdp.grant_consent(customer_id, "personalization")
        self.dpdp.revoke_consent_and_erase(customer_id)

        records = self.db.get_integrity_records()
        self.assertEqual(len(records), 2)
        self.assertTrue(self.ledger.verify()["valid"])
        serialized = json.dumps(records)
        self.assertNotIn(customer_id, serialized)
        self.assertEqual(len(records[0]["customer_ref"]), 64)

    def test_database_rejects_ledger_update_and_delete(self):
        self.ledger.append("SBI-LEDGER-002", "test_event", {"safe": True})

        with sqlite3.connect(self.db.db_path) as conn:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                conn.execute("UPDATE audit_ledger SET event_type='tampered' WHERE sequence=1")
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                conn.execute("DELETE FROM audit_ledger WHERE sequence=1")

        self.assertTrue(self.ledger.verify()["valid"])

    def test_concurrent_appends_preserve_one_valid_chain(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(
                lambda number: self.ledger.append("SBI-LEDGER-003", "parallel_event", {"number": number}),
                range(24),
            ))

        verification = self.ledger.verify()
        self.assertTrue(verification["valid"])
        self.assertEqual(verification["records_checked"], 24)


if __name__ == "__main__":
    unittest.main()
