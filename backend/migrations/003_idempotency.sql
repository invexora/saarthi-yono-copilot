CREATE TABLE IF NOT EXISTS request_idempotency (
    customer_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    state TEXT NOT NULL,
    response_json TEXT,
    http_status INTEGER,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    PRIMARY KEY (customer_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_request_idempotency_expiry
ON request_idempotency(expires_at);
