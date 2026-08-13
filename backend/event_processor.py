import hashlib
import json

from backend.audit_ledger import AuditLedger


class EventContractError(ValueError):
    """Raised when a stream event does not match an approved internal contract."""


class GovernedEventProcessor:
    """Validate internal events and persist exactly-once, data-minimized receipts."""

    SUPPORTED_EVENT_TYPES = {"ORCHESTRATOR_TRACE"}
    TRACE_FIELDS = {"signal", "segment"}

    def __init__(self, database, secret, consumer_name, key_version="v1"):
        self.database = database
        self.consumer_name = consumer_name
        self.identity = AuditLedger(database, secret, key_version)

    @staticmethod
    def _required_text(value, name, max_length):
        if not isinstance(value, str) or not value.strip() or len(value) > max_length:
            raise EventContractError(f"invalid_{name}")
        return value

    def _validate(self, event):
        if not isinstance(event, dict):
            raise EventContractError("invalid_event")
        event_id = self._required_text(event.get("event_id"), "event_id", 100)
        event_type = self._required_text(event.get("event_type"), "event_type", 100)
        customer_id = self._required_text(event.get("customer_id"), "customer_id", 128)
        if event_type not in self.SUPPORTED_EVENT_TYPES:
            raise EventContractError("unsupported_event_type")
        payload = event.get("payload")
        if not isinstance(payload, dict) or set(payload) != self.TRACE_FIELDS:
            raise EventContractError("invalid_trace_payload")
        self._required_text(payload.get("signal"), "signal", 1000)
        self._required_text(payload.get("segment"), "segment", 100)
        return event_id, event_type, customer_id, payload

    def __call__(self, event):
        event_id, event_type, customer_id, payload = self._validate(event)
        canonical_payload = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        )
        return self.database.record_processed_event(
            event_id=event_id,
            event_type=event_type,
            customer_ref=self.identity.customer_ref(customer_id),
            payload_digest=hashlib.sha256(canonical_payload.encode()).hexdigest(),
            consumer_name=self.consumer_name,
        )
