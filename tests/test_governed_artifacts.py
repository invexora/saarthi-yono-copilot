import base64
import copy
import hashlib
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.audit_ledger import AuditLedger
from backend.database import DatabaseManager
from backend.governed_artifacts import (
    ArtifactMaterializationError,
    GovernedArtifactError,
    GovernedArtifactService,
)
from backend.neo4j_client import Neo4jProductGraph
from backend.policy_catalog import PolicyCatalog
from backend.postgres_database import PostgresDatabaseManager
from backend.settings import Settings


class GovernedArtifactFixture(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.temp_dir.name) / "artifacts.db"))
        self.private_key = Ed25519PrivateKey.generate()
        public_bytes = self.private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        self.public_key_base64 = base64.b64encode(public_bytes).decode()
        self.key_id = "sbi-governance-key-2026-01"
        self.ledger = AuditLedger(self.db, "artifact-ledger-secret-at-least-32-characters")
        self.service = GovernedArtifactService(
            self.db,
            self.public_key_base64,
            self.key_id,
            self.ledger,
        )
        self.products = Neo4jProductGraph(mode="memory")
        self.policies = PolicyCatalog()
        self.service.configure_materializers(self.products, self.policies)

    def tearDown(self):
        self.temp_dir.cleanup()

    def product_payload(self, version="2026.09.1", product_name="Governed Consolidation Loan"):
        rules = copy.deepcopy(Neo4jProductGraph(mode="memory").catalog)
        for rule in rules:
            rule["catalog_version"] = version
            if rule["trigger"] == "opportunity" and rule["segment"] == "corporate":
                rule["product"] = product_name
                rule["rate"] = 11.5
        return {"catalog_version": version, "rules": rules}

    def policy_payload(self, version="2026.09.1", marker="governed provenance marker"):
        source = Path(__file__).parents[1] / "backend" / "policies" / "manifest.json"
        payload = json.loads(source.read_text())
        payload["manifest_version"] = version
        payload["policies"][0]["content"] += f" {marker}"
        payload["policies"][0]["content_sha256"] = hashlib.sha256(
            payload["policies"][0]["content"].encode()
        ).hexdigest()
        return payload

    def sign(self, artifact_type, version, payload, private_key=None):
        signature = (private_key or self.private_key).sign(
            GovernedArtifactService.canonical_envelope(artifact_type, version, payload)
        )
        return base64.b64encode(signature).decode()

    def request(self, artifact_type, version, payload, requester="requester-ref"):
        return self.service.request(
            artifact_type,
            version,
            payload,
            self.sign(artifact_type, version, payload),
            self.key_id,
            requester,
        )

    def approve(self, requested, approver="approver-ref"):
        return self.service.decide(
            requested["artifact"]["artifact_id"], "approved", approver,
        )


class GovernedArtifactTests(GovernedArtifactFixture):
    def test_signature_tampering_and_untrusted_key_fail_before_persistence(self):
        payload = self.product_payload()
        signature = self.sign("product_catalog", "2026.09.1", payload)
        tampered = copy.deepcopy(payload)
        tampered["rules"][0]["rate"] = 99.0

        with self.assertRaisesRegex(GovernedArtifactError, "signature_invalid"):
            self.service.request(
                "product_catalog", "2026.09.1", tampered,
                signature, self.key_id, "requester-ref",
            )
        with self.assertRaisesRegex(GovernedArtifactError, "key_not_trusted"):
            self.service.request(
                "product_catalog", "2026.09.1", payload,
                signature, "unknown-key", "requester-ref",
            )
        self.assertEqual(self.service.list(), [])

    def test_four_eyes_activation_changes_runtime_catalog_and_hides_sensitive_fields(self):
        payload = self.product_payload(product_name="SBI Governed Loan V2")
        requested = self.request("product_catalog", "2026.09.1", payload)
        self.assertEqual(requested["status"], "requested")
        serialized = json.dumps(requested)
        self.assertNotIn("signature", serialized)
        self.assertNotIn("envelope", serialized)
        self.assertNotIn("requested_by_ref", serialized)

        same_actor = self.service.decide(
            requested["artifact"]["artifact_id"], "approved", "requester-ref",
        )
        self.assertEqual(same_actor["status"], "four_eyes_required")
        self.assertNotEqual(
            self.products.query_eligibility("opportunity", "corporate")["product"],
            "SBI Governed Loan V2",
        )

        approved = self.approve(requested)
        self.assertEqual(approved["status"], "approved")
        product = self.products.query_eligibility("opportunity", "corporate")
        self.assertEqual(product["product"], "SBI Governed Loan V2")
        self.assertEqual(product["catalog_version"], "2026.09.1")
        self.assertEqual(self.service.health()["detail"].split(";")[0].split("=")[1], "fallback")

    def test_policy_activation_and_restart_materialization_are_durable(self):
        product = self.request("product_catalog", "2026.09.1", self.product_payload())
        policy_payload = self.policy_payload(marker="unique-restart-governance-token")
        policy = self.request("policy_registry", "2026.09.1", policy_payload)
        self.approve(product)
        self.approve(policy)
        self.assertEqual(
            self.policies.retrieve_policy("unique restart governance token")["manifest_version"],
            "2026.09.1",
        )

        restarted_products = Neo4jProductGraph(mode="memory")
        restarted_policies = PolicyCatalog()
        restarted = GovernedArtifactService(
            self.db, self.public_key_base64, self.key_id, required=True,
        )
        restarted.configure_materializers(restarted_products, restarted_policies)
        self.assertEqual(
            restarted.materialize_active(),
            ["policy_registry", "product_catalog"],
        )
        self.assertEqual(
            restarted_products.query_eligibility("opportunity", "corporate")["catalog_version"],
            "2026.09.1",
        )
        self.assertEqual(restarted_policies.manifest_version, "2026.09.1")
        self.assertTrue(restarted.health()["ready"])

    def test_replay_version_conflict_and_concurrent_pending_are_deterministic(self):
        payload = self.product_payload("2026.09.1")
        first = self.request("product_catalog", "2026.09.1", payload)
        replay = self.request("product_catalog", "2026.09.1", payload)
        conflicting = self.product_payload("2026.09.1", "Conflicting Same Version")
        conflict = self.request("product_catalog", "2026.09.1", conflicting)
        self.assertEqual(first["status"], "requested")
        self.assertEqual(replay["status"], "already_requested")
        self.assertEqual(conflict["status"], "version_conflict")

        self.service.decide(first["artifact"]["artifact_id"], "rejected", "approver-ref")

        def submit(index):
            version = f"2026.10.{index}"
            return self.request(
                "product_catalog", version, self.product_payload(version),
                requester=f"requester-{index}",
            )["status"]

        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes = list(executor.map(submit, range(8)))
        self.assertEqual(outcomes.count("requested"), 1)
        self.assertEqual(outcomes.count("already_pending"), 7)

    def test_materialization_failure_leaves_artifact_pending_and_current_runtime_intact(self):
        class FailingProductCatalog:
            def apply_governed_feed(self, _):
                raise ConnectionError("neo4j unavailable")

        payload = self.product_payload()
        requested = self.request("product_catalog", "2026.09.1", payload)
        previous = self.products.query_eligibility("opportunity", "corporate")
        self.service.configure_materializers(FailingProductCatalog(), self.policies)
        with self.assertRaises(ArtifactMaterializationError):
            self.approve(requested)
        stored = self.db.get_governed_artifact(requested["artifact"]["artifact_id"])
        self.assertEqual(stored["status"], "pending")
        self.assertEqual(
            previous,
            self.products.query_eligibility("opportunity", "corporate"),
        )

    def test_activation_claim_allows_exactly_one_materializer(self):
        class BlockingCatalog:
            def __init__(self):
                self.calls = 0
                self.started = threading.Event()
                self.release = threading.Event()

            def apply_governed_feed(self, _):
                self.calls += 1
                self.started.set()
                self.release.wait(timeout=5)

        catalog = BlockingCatalog()
        self.service.configure_materializers(catalog, self.policies)
        requested = self.request("product_catalog", "2026.09.1", self.product_payload())
        artifact_id = requested["artifact"]["artifact_id"]
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                self.service.decide, artifact_id, "approved", "approver-one",
            )
            self.assertTrue(catalog.started.wait(timeout=2))
            competing = self.service.decide(artifact_id, "approved", "approver-two")
            catalog.release.set()
            completed = first.result(timeout=5)

        self.assertEqual(competing["status"], "materialization_in_progress")
        self.assertEqual(completed["status"], "approved")
        self.assertEqual(catalog.calls, 1)

    def test_artifacts_are_governance_records_not_customer_erasure_data(self):
        requested = self.request("product_catalog", "2026.09.1", self.product_payload())
        self.db.process_erasure_request("SBI-UNRELATED-CUSTOMER")
        self.assertIsNotNone(self.db.get_governed_artifact(requested["artifact"]["artifact_id"]))

    def test_sqlalchemy_portable_artifact_lifecycle(self):
        database = PostgresDatabaseManager(
            f"sqlite+pysqlite:///{Path(self.temp_dir.name) / 'portable-artifacts.db'}"
        )
        service = GovernedArtifactService(
            database, self.public_key_base64, self.key_id,
        )
        products = Neo4jProductGraph(mode="memory")
        service.configure_materializers(products, PolicyCatalog())
        payload = self.product_payload()
        requested = service.request(
            "product_catalog", "2026.09.1", payload,
            self.sign("product_catalog", "2026.09.1", payload),
            self.key_id, "requester-ref",
        )
        approved = service.decide(
            requested["artifact"]["artifact_id"], "approved", "approver-ref",
        )
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(database.get_system_metrics()["governed_artifacts_active"], 1)


class GovernedArtifactApiTests(GovernedArtifactFixture):
    @staticmethod
    def headers(customer_id, role="customer"):
        return {
            "X-Saarthi-Demo-Customer": customer_id,
            "X-Saarthi-Demo-Role": role,
        }

    def test_role_gated_signed_activation_updates_catalog_and_metrics(self):
        settings = Settings(
            db_path=self.db.db_path,
            auth_mode="development",
            decision_secret="artifact-api-decision-secret-at-least-32-characters",
        )
        payload = self.product_payload(product_name="API Governed Product")
        request_payload = {
            "artifactType": "product_catalog",
            "version": "2026.09.1",
            "payload": payload,
            "signature": self.sign("product_catalog", "2026.09.1", payload),
            "signingKeyId": self.key_id,
        }
        with TestClient(create_app(settings, self.db, artifact_service=self.service)) as client:
            denied = client.post(
                "/api/v1/governance/artifacts",
                json=request_payload,
                headers=self.headers("SBI-CUSTOMER-ARTIFACT"),
            )
            requested = client.post(
                "/api/v1/governance/artifacts",
                json=request_payload,
                headers=self.headers("SBI-OPS-ARTIFACT", "ops"),
            )
            artifact_id = requested.json()["artifact"]["artifact_id"]
            self_approval = client.post(
                f"/api/v1/governance/artifacts/{artifact_id}/decision",
                json={"decision": "approved"},
                headers=self.headers("SBI-OPS-ARTIFACT", "admin"),
            )
            approved = client.post(
                f"/api/v1/governance/artifacts/{artifact_id}/decision",
                json={"decision": "approved"},
                headers=self.headers("SBI-ADMIN-ARTIFACT", "admin"),
            )
            products = client.get(
                "/api/v1/products",
                headers=self.headers("SBI-CUSTOMER-PRODUCTS"),
            )
            listed = client.get(
                "/api/v1/governance/artifacts?artifact_status=active",
                headers=self.headers("SBI-AUDITOR-ARTIFACT", "auditor"),
            )
            metrics = client.get(
                "/api/v1/metrics",
                headers=self.headers("SBI-OPS-METRICS", "ops"),
            )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(requested.status_code, 201)
        self.assertEqual(self_approval.status_code, 409)
        self.assertEqual(approved.status_code, 200)
        self.assertTrue(any(row["product"] == "API Governed Product" for row in products.json()))
        self.assertEqual(listed.json()[0]["version"], "2026.09.1")
        self.assertNotIn("signature", listed.text)
        self.assertIn("saarthi_governed_artifacts_active 1", metrics.text)


if __name__ == "__main__":
    unittest.main()
