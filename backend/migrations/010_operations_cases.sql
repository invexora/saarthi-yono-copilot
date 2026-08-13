CREATE TABLE IF NOT EXISTS operations_cases (
    case_id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK(status IN (
        'draft', 'approved', 'submitting', 'submission_retry',
        'open', 'in_progress', 'syncing', 'sync_retry',
        'resolved', 'closed', 'rejected'
    )),
    safe_summary TEXT NOT NULL,
    requested_by_ref TEXT NOT NULL,
    requested_at REAL NOT NULL,
    approved_by_ref TEXT,
    approved_at REAL,
    action_started_at REAL,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
    external_case_reference TEXT,
    provider_status TEXT,
    provider_response_digest TEXT,
    last_synced_at REAL,
    next_action_at REAL,
    last_error_code TEXT,
    FOREIGN KEY(recommendation_id) REFERENCES fulfillment_reconciliations(recommendation_id)
);

CREATE INDEX IF NOT EXISTS idx_operations_cases_status_due
ON operations_cases(status, next_action_at);
