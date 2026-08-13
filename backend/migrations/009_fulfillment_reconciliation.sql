CREATE TABLE IF NOT EXISTS fulfillment_reconciliations (
    recommendation_id TEXT PRIMARY KEY,
    fulfillment_reference TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'checking', 'matched', 'mismatch', 'retry')),
    provider_status TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
    created_at REAL NOT NULL,
    checking_started_at REAL,
    last_checked_at REAL,
    next_check_at REAL,
    provider_response_digest TEXT,
    last_error_code TEXT,
    acknowledged_at REAL,
    acknowledged_by TEXT,
    acknowledgement_note TEXT,
    FOREIGN KEY(recommendation_id) REFERENCES recommendations(recommendation_id)
);

CREATE INDEX IF NOT EXISTS idx_fulfillment_reconciliation_status_due
ON fulfillment_reconciliations(status, next_check_at);

INSERT OR IGNORE INTO fulfillment_reconciliations (
    recommendation_id, fulfillment_reference, status, provider_status,
    attempt_count, created_at, next_check_at
)
SELECT recommendation_id, fulfillment_reference, 'pending', 'unknown',
       0, COALESCE(fulfilled_at, created_at), COALESCE(fulfilled_at, created_at)
FROM recommendations
WHERE status = 'fulfilled' AND fulfillment_reference IS NOT NULL;
