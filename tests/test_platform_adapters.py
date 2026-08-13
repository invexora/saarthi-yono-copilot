import tempfile
import unittest
import shutil
import socket
import subprocess
import time
import os
import sqlite3
from pathlib import Path

from backend.database import DatabaseManager
from backend.audit_ledger import AuditLedger
from backend.dpdp_engine import DPDPEngine
from backend.neo4j_client import CATALOG_VERSION, Neo4jProductGraph
from backend.orchestrator import SaarthiAgentOrchestrator
from backend.postgres_database import PostgresDatabaseManager
from backend.postgres_database import AUDIT_LEDGER, METADATA
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from backend.redis_streams import RedisEventStream
from backend.event_worker import EventConsumerWorker
from backend.event_processor import GovernedEventProcessor
from backend.fulfillment import SyntheticFulfillmentClient
from backend.case_management import SyntheticCaseManagementClient
from backend.operations_case_service import OperationsCaseService
from backend.reconciliation_service import FulfillmentReconciliationService


class FakeRedis:
    def __init__(self):
        self.eval_calls = []

    def ping(self):
        return True

    def eval(self, *args):
        self.eval_calls.append(args)
        return ["1786463000000-0", "0"]


class RedisEventStreamTests(unittest.TestCase):
    def test_memory_mode_deduplicates_by_idempotency_key(self):
        stream = RedisEventStream(mode="memory")

        first = stream.publish_event("TEST", "SBI-REDIS-001", {"amount": 100}, "same-request")
        replay = stream.publish_event("TEST", "SBI-REDIS-001", {"amount": 100}, "same-request")

        self.assertEqual(first["event_id"], replay["event_id"])
        self.assertFalse(first["deduplicated"])
        self.assertTrue(replay["deduplicated"])
        self.assertEqual(stream.get_stream_info()["length"], 1)

    def test_redis_mode_uses_atomic_lua_xadd(self):
        client = FakeRedis()
        stream = RedisEventStream(mode="redis", client=client)

        event = stream.publish_event("TEST", "SBI-REDIS-002", {"safe": True}, "redis-request")

        self.assertEqual(event["event_id"], "1786463000000-0")
        self.assertEqual(len(client.eval_calls), 1)
        self.assertIn("XADD", client.eval_calls[0][0])
        self.assertTrue(stream.health()["ready"])

    def test_memory_consumer_retries_dead_letters_and_replays_idempotently(self):
        stream = RedisEventStream(mode="memory")
        stream.publish_event("FAIL_TEST", "SBI-DLQ-001", {"secret": "internal"}, "dlq-source-001")
        worker = EventConsumerWorker(
            stream,
            lambda _: (_ for _ in ()).throw(ValueError("do not persist this detail")),
            max_delivery_attempts=3,
            min_idle_ms=0,
        )

        results = [worker.process_once() for _ in range(3)]
        self.assertEqual([result["dead_lettered"] for result in results], [0, 0, 1])
        self.assertEqual(stream.get_consumer_group_info("saarthi-workers")["pending"], 0)
        dead_letter = stream.list_dead_letters()[0]
        self.assertNotIn("customer_id", dead_letter)
        self.assertNotIn("payload", dead_letter)
        first = stream.replay_dead_letter(dead_letter["dead_letter_id"], "replay-key-001")
        replay = stream.replay_dead_letter(dead_letter["dead_letter_id"], "replay-key-001")
        self.assertTrue(first["replayed"])
        self.assertFalse(first["deduplicated"])
        self.assertTrue(replay["deduplicated"])
        self.assertEqual(first["event_id"], replay["event_id"])

    def test_stale_pending_event_is_recovered_by_another_consumer(self):
        stream = RedisEventStream(mode="memory")
        stream.publish_event("RECOVER", "SBI-RECOVER-001", {}, "recover-source-001")
        stream.ensure_consumer_group("recovery")
        original = stream.read_group("recovery", "worker-a", 1)
        recovered = stream.claim_stale("recovery", "worker-b", min_idle_ms=0, count=1)

        self.assertEqual(recovered[0]["event_id"], original[0]["event_id"])
        self.assertEqual(recovered[0]["delivery_count"], 2)
        self.assertEqual(stream.ack_event("recovery", recovered[0]["event_id"]), 1)


@unittest.skipUnless(shutil.which("redis-server"), "redis-server is not installed")
class RedisLiveConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.process = subprocess.Popen(
            [
                shutil.which("redis-server"), "--bind", "127.0.0.1", "--port", str(self.port),
                "--save", "", "--appendonly", "no", "--dir", self.temp_dir.name,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import redis
        client = redis.Redis(host="127.0.0.1", port=self.port, decode_responses=True)
        for _ in range(50):
            try:
                if client.ping():
                    break
            except redis.RedisError:
                time.sleep(0.02)
        else:
            self.fail("temporary Redis server did not start")
        self.stream = RedisEventStream(mode="redis", client=client, stream_name="test:consumer-events")

    def tearDown(self):
        self.process.terminate()
        self.process.wait(timeout=5)
        self.temp_dir.cleanup()

    def test_real_redis_consumer_dead_letter_and_replay(self):
        self.stream.ensure_consumer_group("live-workers")
        published = self.stream.publish_event("LIVE_FAIL", "SBI-LIVE-001", {"safe": True}, "live-source-001")
        worker = EventConsumerWorker(
            self.stream,
            lambda _: (_ for _ in ()).throw(RuntimeError("failed")),
            group_name="live-workers",
            max_delivery_attempts=2,
            min_idle_ms=0,
        )

        worker.process_once()
        terminal = worker.process_once()
        self.assertEqual(terminal["dead_lettered"], 1)
        duplicate_move = self.stream.dead_letter_event("live-workers", published["event_id"], "RuntimeError")
        self.assertFalse(duplicate_move["moved"])
        self.assertEqual(len(self.stream.list_dead_letters()), 1)
        dead_letter = self.stream.list_dead_letters()[0]
        first = self.stream.replay_dead_letter(dead_letter["dead_letter_id"], "live-replay-001")
        replay = self.stream.replay_dead_letter(dead_letter["dead_letter_id"], "live-replay-001")
        self.assertTrue(first["replayed"])
        self.assertTrue(replay["deduplicated"])
        self.assertEqual(first["event_id"], replay["event_id"])

    def test_worker_entrypoint_processes_event_and_writes_durable_receipt(self):
        stream = RedisEventStream(mode="redis", client=self.stream.client)
        published = stream.publish_event(
            "ORCHESTRATOR_TRACE",
            "SBI-LIVE-WORKER-PRIVATE",
            {"signal": "Branch cash deposit", "segment": "corporate"},
            "live-worker-entrypoint-001",
        )
        db_path = str(Path(self.temp_dir.name) / "worker.db")
        heartbeat_path = str(Path(self.temp_dir.name) / "worker.heartbeat")
        worker_database = DatabaseManager(db_path)
        reconciliation_customer = "SBI-WORKER-RECON-PRIVATE"
        reconciliation_id = "worker-reconciliation-001"
        dpdp = DPDPEngine(
            worker_database,
            decision_secret="live-worker-decision-secret-at-least-32-chars",
        )
        dpdp.grant_consent(reconciliation_customer, "personalization")
        worker_database.create_recommendation(
            reconciliation_id, reconciliation_customer, "SBI-TEST", 5.0, "high",
        )
        authorization = dpdp.authorize_recommendation(reconciliation_id, reconciliation_customer)
        recommendation, claim_status = worker_database.claim_execution(
            reconciliation_id, reconciliation_customer, authorization["decision_token"],
        )
        self.assertEqual(claim_status, "claimed")
        worker_database.complete_execution(
            reconciliation_id,
            reconciliation_customer,
            SyntheticFulfillmentClient().execute(
                recommendation, reconciliation_customer, reconciliation_id,
            ),
        )
        case_customer = "SBI-WORKER-CASE-PRIVATE"
        case_recommendation_id = "worker-case-reconciliation-001"
        dpdp.grant_consent(case_customer, "personalization")
        worker_database.create_recommendation(
            case_recommendation_id, case_customer, "SBI-TEST", 5.0, "high",
        )
        case_authorization = dpdp.authorize_recommendation(
            case_recommendation_id, case_customer,
        )
        case_recommendation, case_claim = worker_database.claim_execution(
            case_recommendation_id, case_customer, case_authorization["decision_token"],
        )
        self.assertEqual(case_claim, "claimed")
        worker_database.complete_execution(
            case_recommendation_id,
            case_customer,
            SyntheticFulfillmentClient().execute(
                case_recommendation, case_customer, case_recommendation_id,
            ),
        )

        class ReversedStatusClient:
            def get_status(self, *_):
                return {"status": "reversed"}

        FulfillmentReconciliationService(
            worker_database, ReversedStatusClient(), retry_seconds=0,
        ).reconcile(case_recommendation_id)
        case_service = OperationsCaseService(
            worker_database, SyntheticCaseManagementClient(),
        )
        requested_case = case_service.request(
            case_recommendation_id, "worker-requester-ref", "Worker-submitted SBI escalation",
        )
        operations_case_id = requested_case["case"]["case_id"]
        self.assertEqual(
            case_service.approve(operations_case_id, "worker-approver-ref")["status"],
            "approved",
        )
        environment = {
            **os.environ,
            "SAARTHI_AUTH_MODE": "development",
            "SAARTHI_DECISION_SECRET": "live-worker-decision-secret-at-least-32-chars",
            "SAARTHI_AUDIT_SECRET": "live-worker-audit-secret-at-least-32-chars",
            "SAARTHI_DB_PATH": db_path,
            "SAARTHI_EVENT_STREAM_MODE": "redis",
            "SAARTHI_REDIS_URL": f"redis://127.0.0.1:{self.port}/0",
            "SAARTHI_EVENT_CONSUMER_GROUP": "live-entrypoint-workers",
            "SAARTHI_EVENT_CONSUMER_NAME": "entrypoint-worker-1",
            "SAARTHI_EVENT_CLAIM_IDLE_MS": "0",
            "SAARTHI_EVENT_WORKER_BLOCK_MS": "100",
            "SAARTHI_WORKER_HEARTBEAT_PATH": heartbeat_path,
        }

        completed = subprocess.run(
            ["python3", "-m", "backend.worker", "--once"],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        receipt = DatabaseManager(db_path).get_processed_event(published["event_id"])
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["consumer_name"], "entrypoint-worker-1")
        self.assertNotIn("SBI-LIVE-WORKER-PRIVATE", str(receipt))
        self.assertTrue(Path(heartbeat_path).exists())
        reconciliation = DatabaseManager(db_path).get_fulfillment_reconciliation(reconciliation_id)
        self.assertEqual(reconciliation["status"], "matched")
        self.assertNotIn(reconciliation_customer, str(reconciliation))
        operations_case = DatabaseManager(db_path).get_operations_case(operations_case_id)
        self.assertEqual(operations_case["status"], "open")
        self.assertTrue(operations_case["external_case_reference"].startswith("SYN-CASE-"))
        self.assertNotIn(case_customer, str(operations_case))

    def test_malformed_json_is_bounded_and_dead_lettered(self):
        stream = RedisEventStream(
            mode="redis", client=self.stream.client, stream_name="test:poison-events",
        )
        stream.ensure_consumer_group("poison-workers")
        stream.client.xadd(stream.stream_name, {
            "event_type": "ORCHESTRATOR_TRACE",
            "customer_id": "SBI-POISON-PRIVATE",
            "timestamp": "2026-08-11T00:00:00Z",
            "payload": "{malformed-json",
        })
        database = DatabaseManager(str(Path(self.temp_dir.name) / "poison.db"))
        processor = GovernedEventProcessor(
            database, "poison-event-secret-at-least-32-characters", "poison-worker",
        )
        worker = EventConsumerWorker(
            stream, processor, group_name="poison-workers", consumer_name="poison-worker",
            max_delivery_attempts=1, min_idle_ms=0,
        )

        result = worker.process_once()

        self.assertEqual(result["dead_lettered"], 1)
        self.assertEqual(stream.get_consumer_group_info("poison-workers")["pending"], 0)
        self.assertEqual(stream.list_dead_letters()[0]["error_code"], "EventContractError")


class FakeNeo4jResult:
    def __init__(self, record=None, records=None):
        self.record = record
        self.records = records or []

    def consume(self):
        return None

    def single(self):
        return self.record

    def __iter__(self):
        return iter(self.records)


class FakeNeo4jSession:
    def __init__(self, driver):
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def run(self, query, **params):
        self.driver.calls.append((query, params))
        if "LIMIT 1" in query:
            return FakeNeo4jResult(self.driver.query_record)
        return FakeNeo4jResult(records=self.driver.list_records)


class FakeNeo4jDriver:
    def __init__(self):
        self.calls = []
        self.verify_calls = 0
        self.closed = False
        self.query_record = {
            "product_id": "SBI-TEST-01",
            "product": "Test Product",
            "rate": 5.0,
            "risk_tier": "low",
            "catalog_version": CATALOG_VERSION,
            "effective_from": "2026-01-01T00:00:00Z",
            "effective_to": None,
        }
        self.list_records = []

    def verify_connectivity(self):
        self.verify_calls += 1

    def session(self, **_):
        return FakeNeo4jSession(self)

    def close(self):
        self.closed = True


class ProductCatalogTests(unittest.TestCase):
    def test_memory_catalog_is_versioned_and_effective_dated(self):
        catalog = Neo4jProductGraph(mode="memory")

        product = catalog.query_eligibility("opportunity", "corporate")

        self.assertEqual(product["product_id"], "SBI-LOAN-EXP01")
        self.assertEqual(product["catalog_version"], CATALOG_VERSION)
        self.assertTrue(product["effective_from"])
        self.assertEqual(len(catalog.list_products()), 20)

    def test_neo4j_catalog_seeds_and_uses_bound_parameters(self):
        driver = FakeNeo4jDriver()
        catalog = Neo4jProductGraph(mode="neo4j", driver=driver, seed_catalog=True)

        product = catalog.query_eligibility("opportunity' OR true", "corporate")

        self.assertEqual(product["product_id"], "SBI-TEST-01")
        query, params = driver.calls[-1]
        self.assertNotIn("opportunity' OR true", query)
        self.assertEqual(params["trigger"], "opportunity' OR true")
        self.assertGreaterEqual(driver.verify_calls, 1)
        self.assertTrue(any("UNWIND $rules" in call[0] for call in driver.calls))


class DependencyFailureTests(unittest.TestCase):
    def test_catalog_failure_does_not_consume_nudge_budget(self):
        class FailingCatalog:
            def query_eligibility(self, *_):
                raise ConnectionError("catalog unavailable")

        with tempfile.TemporaryDirectory() as temp_dir:
            db = DatabaseManager(str(Path(temp_dir) / "failure.db"))
            DPDPEngine(db).grant_consent("SBI-FAILURE-001", "personalization")
            orchestrator = SaarthiAgentOrchestrator(
                db,
                event_stream=RedisEventStream(mode="memory"),
                product_catalog=FailingCatalog(),
            )

            result = orchestrator.run_trace(
                "Branch cash deposit",
                "Email: safe@example.com",
                "corporate",
                "SBI-FAILURE-001",
                "failure-request-001",
            )

            self.assertEqual(result["delivery_mode"], "dependency_unavailable")
            self.assertEqual(db.get_nudge_budget_status("SBI-FAILURE-001")["used"], 0)


class PostgresPersistenceContractTests(unittest.TestCase):
    def test_sqlalchemy_sqlite_upgrade_preserves_existing_rollout_controls_and_adds_model_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "rollout-upgrade.db"
            with sqlite3.connect(database_path) as connection:
                connection.execute('''
                    CREATE TABLE rollout_controls (
                        control_id TEXT PRIMARY KEY,
                        scope_type TEXT NOT NULL CHECK(scope_type IN (
                            'global', 'channel', 'segment', 'signal', 'product'
                        )),
                        scope_value TEXT NOT NULL,
                        mode TEXT NOT NULL CHECK(mode IN ('active', 'shadow', 'disabled')),
                        cohort_percentage INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        requested_by_ref TEXT NOT NULL,
                        requested_at REAL NOT NULL,
                        decided_by_ref TEXT,
                        decided_at REAL,
                        effective_at REAL
                    )
                ''')
                connection.execute('''
                    INSERT INTO rollout_controls (
                        control_id, scope_type, scope_value, mode, cohort_percentage,
                        status, reason, requested_by_ref, requested_at
                    ) VALUES ('legacy-control', 'product', 'SBI-LEGACY', 'active', 100,
                              'active', 'Legacy control', 'requester-ref', 1.0)
                ''')
                connection.commit()

            database = PostgresDatabaseManager(f"sqlite+pysqlite:///{database_path}")
            self.assertEqual(database.get_rollout_control("legacy-control")["status"], "active")
            model, status = database.request_rollout_control(
                "model-control", "model", "detector:v2", "disabled", 0,
                "Model containment", "requester-ref",
            )
            self.assertEqual(status, "requested")
            self.assertEqual(model["scope_type"], "model")

    def test_sqlalchemy_persistence_contract_on_test_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_url = f"sqlite+pysqlite:///{Path(temp_dir) / 'portable.db'}"
            db = PostgresDatabaseManager(database_url)
            dpdp = DPDPEngine(db, decision_secret="portable-persistence-secret-at-least-32")
            customer_id = "SBI-PORTABLE-001"

            dpdp.grant_consent(customer_id, "personalization")
            self.assertTrue(dpdp.verify_purpose_consent(customer_id, "personalization"))
            self.assertEqual(db.consume_nudge_budget(customer_id)["used"], 1)

            db.create_recommendation("portable-rec-001", customer_id, "SBI-TEST", 5.0, "high")
            authorized = dpdp.authorize_recommendation("portable-rec-001", customer_id)
            self.assertEqual(authorized["status"], "authorized")
            execution, execution_status = db.claim_execution(
                "portable-rec-001", customer_id, authorized["decision_token"],
            )
            self.assertEqual(execution_status, "claimed")
            db.complete_execution(
                "portable-rec-001",
                customer_id,
                SyntheticFulfillmentClient().execute(execution, customer_id, "portable-rec-001"),
            )
            reconciliation, reconciliation_status = db.claim_fulfillment_reconciliation("portable-rec-001")
            self.assertEqual(reconciliation_status, "claimed")
            mismatch, mismatch_status = db.complete_fulfillment_reconciliation(
                "portable-rec-001", "reversed", None, "d" * 64,
            )
            self.assertEqual(mismatch_status, "mismatch")
            case_record, case_status = db.create_operations_case(
                "portable-case-001", "portable-rec-001", "requester-ref", "Portable escalation",
            )
            self.assertEqual(case_status, "requested")
            self.assertEqual(
                db.approve_operations_case("portable-case-001", "requester-ref")[1],
                "four_eyes_required",
            )
            self.assertEqual(
                db.approve_operations_case("portable-case-001", "approver-ref")[1],
                "approved",
            )
            claimed_case, claimed_case_status = db.claim_operations_case_submission("portable-case-001")
            self.assertEqual(claimed_case_status, "claimed")
            db.complete_operations_case_submission(
                "portable-case-001", "open", "SBI-CASE-PORTABLE-001", "e" * 64,
            )
            self.assertEqual(db.get_operations_case("portable-case-001")["status"], "open")

            self.assertEqual(db.claim_idempotency(customer_id, "portable-request-001")["status"], "claimed")
            db.complete_idempotency(customer_id, "portable-request-001", {"ok": True}, 200)
            replay = db.claim_idempotency(customer_id, "portable-request-001")
            self.assertEqual(replay, {"status": "replay", "response": {"ok": True}, "http_status": 200})

            self.assertEqual(db.claim_idempotency(customer_id, "stale-portable")["status"], "claimed")
            self.assertEqual(
                db.claim_idempotency(customer_id, "stale-portable", processing_timeout_seconds=0)["status"],
                "claimed",
            )

            self.assertEqual(db.get_applied_migrations(), ["011_governed_artifacts_schema"])
            self.assertTrue(db.health()["ready"])

            self.assertTrue(db.record_processed_event(
                "portable-event-001", "ORCHESTRATOR_TRACE", "a" * 64, "b" * 64, "portable-worker",
            ))
            self.assertFalse(db.record_processed_event(
                "portable-event-001", "ORCHESTRATOR_TRACE", "a" * 64, "b" * 64, "portable-worker",
            ))
            self.assertEqual(db.get_processed_event("portable-event-001")["consumer_name"], "portable-worker")

            ledger = AuditLedger(db, "portable-audit-ledger-secret-32-chars-long")
            ledger.append(customer_id, "portable_event", {"safe": True})
            self.assertTrue(ledger.verify()["valid"])
            with self.assertRaises(IntegrityError):
                with db.engine.begin() as conn:
                    conn.execute(update(AUDIT_LEDGER).values(event_type="tampered"))

            reviewed_customer = "SBI-PORTABLE-REVIEWED"
            dpdp.grant_consent(reviewed_customer, "personalization")
            db.create_recommendation_with_status(
                "portable-reviewed-001", reviewed_customer, "SBI-TEST", 5.0, "high",
                initial_status="approved", evidence={"decision_context": {"context_version": "test"}},
            )
            presented, presentation_status = db.present_recommendation("portable-reviewed-001", reviewed_customer)
            self.assertEqual(presentation_status, "presented")
            self.assertEqual(presented["status"], "presented")
            self.assertEqual(dpdp.authorize_recommendation("portable-reviewed-001", reviewed_customer)["status"], "authorized")

            dpdp.revoke_consent_and_erase(customer_id)
            self.assertEqual(db.get_nudge_budget_status(customer_id)["used"], 0)
            self.assertIsNone(db.get_operations_case("portable-case-001"))

    def test_all_portable_tables_compile_for_postgresql(self):
        dialect = postgresql.dialect()
        compiled = {
            table.name: str(CreateTable(table).compile(dialect=dialect))
            for table in METADATA.sorted_tables
        }

        self.assertEqual(
            set(compiled),
            {"schema_migrations", "audit_logs", "audit_ledger", "dpdp_consent", "event_processing_receipts", "fulfillment_reconciliations", "human_reviews", "nudge_budgets", "operations_cases", "recommendations", "request_idempotency", "rollout_controls", "recommendation_outcomes", "governed_artifacts"},
        )
        self.assertIn("JSON", compiled["request_idempotency"])


if __name__ == "__main__":
    unittest.main()
