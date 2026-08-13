import argparse
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

from backend.event_processor import GovernedEventProcessor
from backend.event_worker import EventConsumerWorker
from backend.audit_ledger import AuditLedger
from backend.fulfillment import create_fulfillment_client
from backend.case_management import create_case_management_client
from backend.operations_case_service import OperationsCaseService
from backend.persistence import create_database
from backend.reconciliation_service import FulfillmentReconciliationService
from backend.redis_streams import RedisEventStream
from backend.settings import Settings


LOGGER = logging.getLogger("saarthi.event_worker")
HEARTBEAT_PATH = Path(os.environ.get("SAARTHI_WORKER_HEARTBEAT_PATH", "/tmp/saarthi-event-worker.heartbeat"))


def _write_heartbeat():
    HEARTBEAT_PATH.write_text(str(time.time()))


def healthcheck(settings):
    try:
        last_seen = float(HEARTBEAT_PATH.read_text())
    except (OSError, ValueError):
        return False
    return time.time() - last_seen <= settings.event_worker_heartbeat_timeout_seconds


def create_worker(settings, database=None, event_stream=None):
    database = database or create_database(settings)
    event_stream = event_stream or RedisEventStream(
        mode=settings.event_stream_mode,
        redis_url=settings.redis_url,
    )
    consumer_name = settings.event_consumer_name
    processor = GovernedEventProcessor(
        database,
        settings.audit_secret or settings.decision_secret,
        consumer_name,
        settings.audit_key_version,
    )
    return EventConsumerWorker(
        event_stream,
        processor,
        group_name=settings.event_consumer_group,
        consumer_name=consumer_name,
        max_delivery_attempts=settings.event_max_delivery_attempts,
        min_idle_ms=settings.event_claim_idle_ms,
    )


def run(settings, once=False):
    database = create_database(settings)
    event_stream = RedisEventStream(
        mode=settings.event_stream_mode,
        redis_url=settings.redis_url,
    )
    worker = create_worker(settings, database, event_stream)
    audit_ledger = AuditLedger(
        database,
        settings.audit_secret or settings.decision_secret,
        settings.audit_key_version,
    )
    reconciliation_service = FulfillmentReconciliationService(
        database,
        create_fulfillment_client(settings),
        audit_ledger,
        settings.fulfillment_reconciliation_retry_seconds,
    )
    operations_case_service = OperationsCaseService(
        database,
        create_case_management_client(settings),
        audit_ledger,
        settings.case_retry_seconds,
        settings.case_sync_interval_seconds,
    )
    stopping = False

    def request_stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    if not once:
        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)

    _write_heartbeat()
    while not stopping:
        try:
            result = worker.process_once(
                count=settings.event_worker_batch_size,
                block_ms=settings.event_worker_block_ms,
            )
            reconciliation_results = []
            for recommendation_id in database.list_due_fulfillment_reconciliations(
                settings.fulfillment_reconciliation_batch_size,
            ):
                reconciliation_results.append(
                    reconciliation_service.reconcile(recommendation_id)["status"],
                )
                worker.event_stream.heartbeat_consumer(worker.group_name, worker.consumer_name)
                _write_heartbeat()
            case_results = []
            for case_action in database.list_due_operations_case_actions(
                settings.case_worker_batch_size,
            ):
                case_results.append(
                    operations_case_service.run_action(
                        case_action["case_id"], case_action["action"],
                    )["status"],
                )
                worker.event_stream.heartbeat_consumer(worker.group_name, worker.consumer_name)
                _write_heartbeat()
            _write_heartbeat()
            if result["read"]:
                LOGGER.info(json.dumps({"event": "batch_processed", **result}, sort_keys=True))
            if reconciliation_results:
                LOGGER.info(json.dumps({
                    "event": "reconciliation_batch_processed",
                    "count": len(reconciliation_results),
                    "outcomes": {
                        outcome: reconciliation_results.count(outcome)
                        for outcome in sorted(set(reconciliation_results))
                    },
                }, sort_keys=True))
            if case_results:
                LOGGER.info(json.dumps({
                    "event": "operations_case_batch_processed",
                    "count": len(case_results),
                    "outcomes": {
                        outcome: case_results.count(outcome)
                        for outcome in sorted(set(case_results))
                    },
                }, sort_keys=True))
        except Exception as error:
            LOGGER.error(json.dumps({
                "event": "worker_poll_failed",
                "error_code": type(error).__name__,
            }, sort_keys=True))
            if once:
                raise
            time.sleep(1)
        if once:
            return result
    return {"status": "stopped"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Saarthi governed Redis Streams worker")
    parser.add_argument("--once", action="store_true", help="Process one bounded batch and exit")
    parser.add_argument("--healthcheck", action="store_true", help="Check the worker heartbeat")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    settings.validate_worker()
    if args.healthcheck:
        return 0 if healthcheck(settings) else 1
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(settings, once=args.once)
    return 0


if __name__ == "__main__":
    sys.exit(main())
