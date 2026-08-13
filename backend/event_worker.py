class EventConsumerWorker:
    """Bounded Redis Streams worker with stale recovery and terminal dead-lettering."""

    def __init__(
        self,
        event_stream,
        handler,
        group_name="saarthi-workers",
        consumer_name="worker-1",
        max_delivery_attempts=3,
        min_idle_ms=60000,
    ):
        self.event_stream = event_stream
        self.handler = handler
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.max_delivery_attempts = max_delivery_attempts
        self.min_idle_ms = min_idle_ms
        self.event_stream.ensure_consumer_group(group_name)

    def process_once(self, count=10, block_ms=0):
        self.event_stream.heartbeat_consumer(self.group_name, self.consumer_name)
        events = self.event_stream.claim_stale(
            self.group_name, self.consumer_name, self.min_idle_ms, count,
        )
        if len(events) < count:
            events.extend(self.event_stream.read_group(
                self.group_name, self.consumer_name, count - len(events),
                0 if events else block_ms,
            ))
        result = {"read": len(events), "processed": 0, "failed": 0, "dead_lettered": 0}
        for event in events:
            try:
                self.handler(event)
                self.event_stream.ack_event(self.group_name, event["event_id"])
                result["processed"] += 1
            except Exception as error:
                result["failed"] += 1
                if int(event.get("delivery_count", 1)) >= self.max_delivery_attempts:
                    moved = self.event_stream.dead_letter_event(
                        self.group_name, event["event_id"], type(error).__name__,
                    )
                    result["dead_lettered"] += 1 if moved["moved"] else 0
        self.event_stream.heartbeat_consumer(self.group_name, self.consumer_name)
        return result
