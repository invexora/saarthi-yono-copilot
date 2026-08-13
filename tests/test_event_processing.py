import tempfile
import unittest
from pathlib import Path

from backend.database import DatabaseManager
from backend.event_processor import EventContractError, GovernedEventProcessor
from backend.event_worker import EventConsumerWorker
from backend.redis_streams import RedisEventStream


class GovernedEventProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = DatabaseManager(str(Path(self.temp_dir.name) / "events.db"))
        self.secret = "event-processing-test-secret-at-least-32-chars"

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def valid_event(event_id="1700000000000-0"):
        return {
            "event_id": event_id,
            "event_type": "ORCHESTRATOR_TRACE",
            "customer_id": "SBI-PRIVATE-001",
            "payload": {"signal": "Branch cash deposit", "segment": "corporate"},
        }

    def test_receipt_is_exactly_once_and_contains_no_raw_customer_data(self):
        processor = GovernedEventProcessor(self.database, self.secret, "worker-a")

        self.assertTrue(processor(self.valid_event()))
        self.assertFalse(processor(self.valid_event()))

        receipt = self.database.get_processed_event("1700000000000-0")
        self.assertEqual(receipt["event_type"], "ORCHESTRATOR_TRACE")
        self.assertEqual(len(receipt["customer_ref"]), 64)
        self.assertEqual(len(receipt["payload_digest"]), 64)
        self.assertNotIn("SBI-PRIVATE-001", str(receipt))
        self.assertNotIn("Branch cash deposit", str(receipt))
        self.assertEqual(self.database.get_system_metrics()["processed_events"], 1)

    def test_invalid_contract_retries_then_moves_to_dead_letter(self):
        stream = RedisEventStream(mode="memory")
        stream.publish_event(
            "UNAPPROVED_EVENT", "SBI-PRIVATE-002", {"raw": "not allowed"}, "invalid-event-001",
        )
        processor = GovernedEventProcessor(self.database, self.secret, "worker-contract")
        worker = EventConsumerWorker(
            stream, processor, consumer_name="worker-contract",
            max_delivery_attempts=2, min_idle_ms=0,
        )

        first = worker.process_once()
        terminal = worker.process_once()

        self.assertEqual(first["failed"], 1)
        self.assertEqual(terminal["dead_lettered"], 1)
        self.assertEqual(stream.list_dead_letters()[0]["error_code"], "EventContractError")
        self.assertEqual(self.database.get_system_metrics()["processed_events"], 0)

    def test_restart_after_receipt_before_ack_does_not_duplicate_projection(self):
        stream = RedisEventStream(mode="memory")
        published = stream.publish_event(
            "ORCHESTRATOR_TRACE",
            "SBI-PRIVATE-003",
            {"signal": "Salary credit increase", "segment": "corporate"},
            "restart-event-001",
        )
        stream.ensure_consumer_group("restart-workers")
        delivered = stream.read_group("restart-workers", "worker-before-crash", 1)[0]
        before_crash = GovernedEventProcessor(self.database, self.secret, "worker-before-crash")
        self.assertTrue(before_crash(delivered))

        after_restart = GovernedEventProcessor(self.database, self.secret, "worker-after-restart")
        worker = EventConsumerWorker(
            stream, after_restart, group_name="restart-workers",
            consumer_name="worker-after-restart", min_idle_ms=0,
        )
        result = worker.process_once()

        self.assertEqual(result["processed"], 1)
        self.assertEqual(stream.get_consumer_group_info("restart-workers")["pending"], 0)
        self.assertEqual(self.database.get_system_metrics()["processed_events"], 1)
        self.assertEqual(self.database.get_processed_event(published["event_id"])["consumer_name"], "worker-before-crash")

    def test_contract_rejects_extra_fields_and_empty_identifiers(self):
        processor = GovernedEventProcessor(self.database, self.secret, "worker-a")
        event = self.valid_event()
        event["payload"]["unexpected"] = True
        with self.assertRaises(EventContractError):
            processor(event)

        event = self.valid_event("")
        with self.assertRaises(EventContractError):
            processor(event)


if __name__ == "__main__":
    unittest.main()
