import json
import time
from datetime import datetime, timezone
from uuid import uuid4


class RedisEventStream:
    """Redis Streams adapter with an explicit in-memory development mode."""

    IDEMPOTENT_XADD_SCRIPT = """
    local existing = redis.call('GET', KEYS[1])
    if existing then
      return {existing, '1'}
    end
    local event_id = redis.call('XADD', KEYS[2], 'MAXLEN', '~', ARGV[1], '*',
      'event_type', ARGV[2],
      'customer_id', ARGV[3],
      'timestamp', ARGV[4],
      'payload', ARGV[5])
    redis.call('SET', KEYS[1], event_id, 'EX', ARGV[6])
    return {event_id, '0'}
    """

    DEAD_LETTER_SCRIPT = """
    local pending = redis.call('XPENDING', KEYS[1], ARGV[4], ARGV[1], ARGV[1], 1)
    if #pending == 0 then return {'', '0'} end
    local rows = redis.call('XRANGE', KEYS[1], ARGV[1], ARGV[1])
    if #rows == 0 then return {'', '0'} end
    local fields = rows[1][2]
    local mapped = {}
    for i = 1, #fields, 2 do mapped[fields[i]] = fields[i + 1] end
    local dlq_id = redis.call('XADD', KEYS[2], '*',
      'original_event_id', ARGV[1],
      'failed_at', ARGV[2],
      'error_code', ARGV[3],
      'event_type', mapped['event_type'] or '',
      'customer_id', mapped['customer_id'] or '',
      'timestamp', mapped['timestamp'] or '',
      'payload', mapped['payload'] or '{}',
      'replay_count', '0')
    redis.call('XACK', KEYS[1], ARGV[4], ARGV[1])
    return {dlq_id, '1'}
    """

    REPLAY_DLQ_SCRIPT = """
    local existing = redis.call('GET', KEYS[3])
    if existing then return {existing, '1'} end
    local rows = redis.call('XRANGE', KEYS[1], ARGV[1], ARGV[1])
    if #rows == 0 then return {'', '0'} end
    local fields = rows[1][2]
    local mapped = {}
    for i = 1, #fields, 2 do mapped[fields[i]] = fields[i + 1] end
    local event_id = redis.call('XADD', KEYS[2], '*',
      'event_type', mapped['event_type'] or '',
      'customer_id', mapped['customer_id'] or '',
      'timestamp', ARGV[2],
      'payload', mapped['payload'] or '{}')
    redis.call('SET', KEYS[3], event_id, 'EX', ARGV[3])
    redis.call('XDEL', KEYS[1], ARGV[1])
    return {event_id, '0'}
    """

    def __init__(
        self,
        stream_name="saarthi:events",
        mode="memory",
        redis_url="redis://localhost:6379/0",
        client=None,
        max_len=10000,
        idempotency_ttl_seconds=86400,
    ):
        if mode not in {"memory", "redis"}:
            raise ValueError("event stream mode must be 'memory' or 'redis'")
        self.stream_name = stream_name
        self.mode = mode
        self.redis_url = redis_url
        self.max_len = max_len
        self.idempotency_ttl_seconds = idempotency_ttl_seconds
        self.event_log = []
        self.idempotency_log = {}
        self.consumer_groups = {}
        self.consumer_heartbeats = {}
        self.dead_letter_log = []
        self.replay_log = {}
        self.client = client

        if self.mode == "redis":
            if self.client is None:
                import redis

                self.client = redis.Redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=3,
                    socket_timeout=3,
                    health_check_interval=30,
                )
            self.client.ping()

    @property
    def dead_letter_stream_name(self):
        return f"{self.stream_name}:dead-letter"

    @staticmethod
    def _decode_event(stream_name, event_id, fields, mode="redis-stream", delivery_count=1):
        raw_payload = fields.get("payload", "{}")
        try:
            payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
        except (json.JSONDecodeError, TypeError):
            # Preserve delivery semantics for poison messages. The governed
            # processor will reject this sentinel and drive bounded DLQ handling.
            payload = None
        return {
            "stream": stream_name,
            "event_id": str(event_id),
            "timestamp": fields.get("timestamp"),
            "event_type": fields.get("event_type"),
            "customer_id": fields.get("customer_id"),
            "payload": payload,
            "ingestion_mode": mode,
            "delivery_count": delivery_count,
        }

    def publish_event(self, event_type, customer_id, payload, idempotency_key=None):
        timestamp = datetime.now(timezone.utc).isoformat()
        idempotency_key = idempotency_key or str(uuid4())

        if self.mode == "redis":
            redis_key = f"{self.stream_name}:idempotency:{idempotency_key}"
            event_result = self.client.eval(
                self.IDEMPOTENT_XADD_SCRIPT,
                2,
                redis_key,
                self.stream_name,
                self.max_len,
                event_type,
                customer_id,
                timestamp,
                json.dumps(payload, separators=(",", ":"), sort_keys=True),
                self.idempotency_ttl_seconds,
            )
            return {
                "stream": self.stream_name,
                "event_id": str(event_result[0]),
                "timestamp": timestamp,
                "event_type": event_type,
                "customer_id": customer_id,
                "payload": payload,
                "ingestion_mode": "redis-stream",
                "idempotency_key": idempotency_key,
                "deduplicated": str(event_result[1]) == "1",
            }

        existing = self.idempotency_log.get(idempotency_key)
        if existing:
            return {**existing, "deduplicated": True}
        event = {
            "stream": self.stream_name,
            "event_id": f"{int(time.time() * 1000)}-{len(self.event_log)}",
            "timestamp": timestamp,
            "event_type": event_type,
            "customer_id": customer_id,
            "payload": payload,
            "ingestion_mode": "memory",
            "idempotency_key": idempotency_key,
            "deduplicated": False,
        }
        self.event_log.append(event)
        self.idempotency_log[idempotency_key] = event
        if len(self.event_log) > self.max_len:
            removed = self.event_log[:-self.max_len]
            self.event_log = self.event_log[-self.max_len:]
            for old_event in removed:
                self.idempotency_log.pop(old_event["idempotency_key"], None)
        return event

    def consume_events(self, count=10):
        if self.mode == "redis":
            rows = self.client.xrevrange(self.stream_name, count=count)
            events = []
            for event_id, fields in reversed(rows):
                events.append({
                    "stream": self.stream_name,
                    "event_id": event_id,
                    "timestamp": fields.get("timestamp"),
                    "event_type": fields.get("event_type"),
                    "customer_id": fields.get("customer_id"),
                    "payload": json.loads(fields.get("payload", "{}")),
                    "ingestion_mode": "redis-stream",
                })
            return events
        return self.event_log[-count:]

    def ensure_consumer_group(self, group_name, start_id="0"):
        if self.mode == "redis":
            try:
                self.client.xgroup_create(self.stream_name, group_name, id=start_id, mkstream=True)
                return True
            except Exception as error:
                if "BUSYGROUP" not in str(error):
                    raise
                return False
        if group_name in self.consumer_groups:
            return False
        self.consumer_groups[group_name] = {"next_index": 0 if start_id == "0" else len(self.event_log), "pending": {}, "consumers": set()}
        return True

    def read_group(self, group_name, consumer_name, count=10, block_ms=0):
        self.ensure_consumer_group(group_name)
        if self.mode == "redis":
            options = {"count": count}
            # Redis interprets BLOCK 0 as "wait forever". Omitting BLOCK gives
            # bounded, non-blocking process_once semantics.
            if block_ms and block_ms > 0:
                options["block"] = block_ms
            rows = self.client.xreadgroup(
                group_name, consumer_name, {self.stream_name: ">"}, **options,
            )
            return [
                self._decode_event(stream, event_id, fields)
                for stream, entries in rows
                for event_id, fields in entries
            ]
        group = self.consumer_groups[group_name]
        group["consumers"].add(consumer_name)
        start = group["next_index"]
        selected = self.event_log[start:start + count]
        now_ms = int(time.time() * 1000)
        for event in selected:
            group["pending"][event["event_id"]] = {
                "event": event,
                "consumer": consumer_name,
                "delivery_count": 1,
                "last_delivery_ms": now_ms,
            }
        group["next_index"] += len(selected)
        return [{**event, "delivery_count": 1} for event in selected]

    def claim_stale(self, group_name, consumer_name, min_idle_ms=60000, count=10):
        self.ensure_consumer_group(group_name)
        if self.mode == "redis":
            result = self.client.xautoclaim(
                self.stream_name, group_name, consumer_name,
                min_idle_ms, "0-0", count=count,
            )
            entries = result[1] if len(result) > 1 else []
            events = []
            for event_id, fields in entries:
                pending = self.client.xpending_range(self.stream_name, group_name, event_id, event_id, 1)
                delivery_count = int(pending[0].get("times_delivered", 1)) if pending else 1
                events.append(self._decode_event(self.stream_name, event_id, fields, delivery_count=delivery_count))
            return events
        group = self.consumer_groups[group_name]
        group["consumers"].add(consumer_name)
        now_ms = int(time.time() * 1000)
        claimed = []
        for pending in group["pending"].values():
            if len(claimed) >= count:
                break
            if now_ms - pending["last_delivery_ms"] >= min_idle_ms:
                pending["consumer"] = consumer_name
                pending["delivery_count"] += 1
                pending["last_delivery_ms"] = now_ms
                claimed.append({**pending["event"], "delivery_count": pending["delivery_count"]})
        return claimed

    def ack_event(self, group_name, event_id):
        if self.mode == "redis":
            return int(self.client.xack(self.stream_name, group_name, event_id))
        group = self.consumer_groups.get(group_name)
        return 1 if group and group["pending"].pop(event_id, None) else 0

    def heartbeat_consumer(self, group_name, consumer_name):
        seen_at = time.time()
        if self.mode == "redis":
            key = f"{self.stream_name}:consumers:{group_name}:heartbeats"
            pipeline = self.client.pipeline()
            pipeline.hset(key, consumer_name, seen_at)
            pipeline.expire(key, 86400)
            pipeline.execute()
        else:
            self.consumer_heartbeats[(group_name, consumer_name)] = seen_at
        return seen_at

    def _active_consumer_count(self, group_name, timeout_seconds):
        cutoff = time.time() - timeout_seconds
        if self.mode == "redis":
            key = f"{self.stream_name}:consumers:{group_name}:heartbeats"
            heartbeats = self.client.hgetall(key)
            stale = []
            for name, seen_at in heartbeats.items():
                try:
                    is_stale = float(seen_at) < cutoff
                except (TypeError, ValueError):
                    is_stale = True
                if is_stale:
                    stale.append(name)
            if stale:
                self.client.hdel(key, *stale)
            return len(heartbeats) - len(stale)
        stale = [
            identity for identity, seen_at in self.consumer_heartbeats.items()
            if identity[0] == group_name and seen_at < cutoff
        ]
        for identity in stale:
            self.consumer_heartbeats.pop(identity, None)
        return sum(1 for identity in self.consumer_heartbeats if identity[0] == group_name)

    def dead_letter_event(self, group_name, event_id, error_code):
        failed_at = datetime.now(timezone.utc).isoformat()
        if self.mode == "redis":
            result = self.client.eval(
                self.DEAD_LETTER_SCRIPT, 2,
                self.stream_name, self.dead_letter_stream_name,
                event_id, failed_at, error_code, group_name,
            )
            return {"dead_letter_id": str(result[0]), "moved": str(result[1]) == "1"}
        group = self.consumer_groups.get(group_name)
        pending = group["pending"].pop(event_id, None) if group else None
        if not pending:
            return {"dead_letter_id": "", "moved": False}
        dlq_id = f"{int(time.time() * 1000)}-{len(self.dead_letter_log)}"
        self.dead_letter_log.append({
            "dead_letter_id": dlq_id,
            "original_event_id": event_id,
            "failed_at": failed_at,
            "error_code": error_code,
            "event": pending["event"],
            "replay_count": 0,
        })
        return {"dead_letter_id": dlq_id, "moved": True}

    def list_dead_letters(self, count=50):
        if self.mode == "redis":
            rows = self.client.xrevrange(self.dead_letter_stream_name, count=count)
            return [{
                "dead_letter_id": event_id,
                "original_event_id": fields.get("original_event_id"),
                "failed_at": fields.get("failed_at"),
                "error_code": fields.get("error_code"),
                "event_type": fields.get("event_type"),
                "replay_count": int(fields.get("replay_count", 0)),
            } for event_id, fields in rows]
        return [{
            "dead_letter_id": item["dead_letter_id"],
            "original_event_id": item["original_event_id"],
            "failed_at": item["failed_at"],
            "error_code": item["error_code"],
            "event_type": item["event"].get("event_type"),
            "replay_count": item["replay_count"],
        } for item in reversed(self.dead_letter_log[-count:])]

    def replay_dead_letter(self, dead_letter_id, replay_key):
        timestamp = datetime.now(timezone.utc).isoformat()
        if self.mode == "redis":
            idempotency_key = f"{self.dead_letter_stream_name}:replay:{dead_letter_id}:{replay_key}"
            result = self.client.eval(
                self.REPLAY_DLQ_SCRIPT, 3,
                self.dead_letter_stream_name, self.stream_name, idempotency_key,
                dead_letter_id, timestamp, self.idempotency_ttl_seconds,
            )
            return {"event_id": str(result[0]), "replayed": bool(result[0]), "deduplicated": str(result[1]) == "1"}
        replay_identity = (dead_letter_id, replay_key)
        existing = self.replay_log.get(replay_identity)
        if existing:
            return {**existing, "deduplicated": True}
        item = next((entry for entry in self.dead_letter_log if entry["dead_letter_id"] == dead_letter_id), None)
        if not item:
            return {"event_id": "", "replayed": False, "deduplicated": False}
        event = item["event"]
        replayed = self.publish_event(event["event_type"], event["customer_id"], event["payload"], f"dlq:{dead_letter_id}:{replay_key}")
        result = {"event_id": replayed["event_id"], "replayed": True}
        self.replay_log[replay_identity] = result
        self.dead_letter_log.remove(item)
        return {**result, "deduplicated": False}

    def get_consumer_group_info(self, group_name, heartbeat_timeout_seconds=30):
        if self.mode == "redis":
            groups = self.client.xinfo_groups(self.stream_name)
            group = next((item for item in groups if item.get("name") == group_name), None)
            return {
                "stream_name": self.stream_name,
                "group_name": group_name,
                "length": int(self.client.xlen(self.stream_name)),
                "pending": int(group.get("pending", 0)) if group else 0,
                "consumers": int(group.get("consumers", 0)) if group else 0,
                "active_consumers": self._active_consumer_count(group_name, heartbeat_timeout_seconds),
                "lag": int(group.get("lag", 0) or 0) if group else int(self.client.xlen(self.stream_name)),
                "dead_letters": int(self.client.xlen(self.dead_letter_stream_name)),
            }
        group = self.consumer_groups.get(group_name, {"next_index": 0, "pending": {}, "consumers": set()})
        return {
            "stream_name": self.stream_name,
            "group_name": group_name,
            "length": len(self.event_log),
            "pending": len(group["pending"]),
            "consumers": len(group["consumers"]),
            "active_consumers": self._active_consumer_count(group_name, heartbeat_timeout_seconds),
            "lag": max(0, len(self.event_log) - group["next_index"]),
            "dead_letters": len(self.dead_letter_log),
        }

    def get_stream_info(self):
        if self.mode == "redis":
            info = self.client.xinfo_stream(self.stream_name)
            return {
                "stream_name": self.stream_name,
                "length": info.get("length", 0),
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
            }
        return {
            "stream_name": self.stream_name,
            "length": len(self.event_log),
            "first_entry": self.event_log[0] if self.event_log else None,
            "last_entry": self.event_log[-1] if self.event_log else None,
        }

    def trim_stream(self, max_len=1000):
        if self.mode == "redis":
            self.client.xtrim(self.stream_name, maxlen=max_len, approximate=True)
            return self.client.xlen(self.stream_name)
        self.event_log = self.event_log[-max_len:]
        self.idempotency_log = {event["idempotency_key"]: event for event in self.event_log}
        return len(self.event_log)

    def health(self):
        if self.mode == "redis":
            try:
                ready = bool(self.client.ping())
                return {"name": "event_stream", "mode": "redis", "ready": ready, "detail": self.stream_name}
            except Exception as error:
                return {"name": "event_stream", "mode": "redis", "ready": False, "detail": type(error).__name__}
        return {"name": "event_stream", "mode": "memory", "ready": True, "detail": "development-only"}
