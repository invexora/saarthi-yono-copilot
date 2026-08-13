CREATE TABLE IF NOT EXISTS event_processing_receipts (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    customer_ref TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    consumer_name TEXT NOT NULL,
    processed_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_event_processing_receipts_processed_at
ON event_processing_receipts(processed_at DESC);
