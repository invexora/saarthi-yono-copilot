import hashlib
import hmac
import json
import time
import uuid

from backend.guardrails import InputGuardian


GENESIS_HASH = "0" * 64


class AuditLedger:
    """Pseudonymous, HMAC-protected hash chain for retained governance evidence."""

    def __init__(self, db, secret, key_version="v1"):
        self.db = db
        self.secret = secret.encode()
        self.key_version = key_version
        self.input_guardian = InputGuardian()

    def customer_ref(self, customer_id):
        return hmac.new(self.secret, f"customer:{customer_id}".encode(), hashlib.sha256).hexdigest()

    def principal_ref(self, subject):
        return hmac.new(self.secret, f"principal:{subject}".encode(), hashlib.sha256).hexdigest()

    def _record_hash(self, record):
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hmac.new(self.secret, canonical.encode(), hashlib.sha256).hexdigest()

    def append(self, customer_id, event_type, payload=None):
        safe_payload = self.input_guardian.mask_pii(payload or {})
        base = {
            "event_id": str(uuid.uuid4()),
            "occurred_at": str(time.time()),
            "customer_ref": self.customer_ref(customer_id),
            "event_type": event_type,
            "payload_json": json.dumps(safe_payload, sort_keys=True, separators=(",", ":")),
            "key_version": self.key_version,
        }

        def build(previous_hash):
            record = {**base, "previous_hash": previous_hash or GENESIS_HASH}
            return {**record, "record_hash": self._record_hash(record)}

        return self.db.append_integrity_record(build)

    def verify(self):
        previous = GENESIS_HASH
        records = self.db.get_integrity_records()
        for record in records:
            unsigned = {key: record[key] for key in (
                "event_id", "occurred_at", "customer_ref", "event_type",
                "payload_json", "key_version", "previous_hash",
            )}
            if record["previous_hash"] != previous or not hmac.compare_digest(record["record_hash"], self._record_hash(unsigned)):
                return {"valid": False, "records_checked": record["sequence"] - 1, "failed_sequence": record["sequence"]}
            previous = record["record_hash"]
        return {"valid": True, "records_checked": len(records), "failed_sequence": None, "head_hash": previous}
