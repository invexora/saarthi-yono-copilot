CREATE TABLE audit_ledger (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    occurred_at TEXT NOT NULL,
    customer_ref TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE,
    key_version TEXT NOT NULL
);

CREATE INDEX idx_audit_ledger_customer_ref ON audit_ledger(customer_ref, sequence);

CREATE TRIGGER audit_ledger_no_update
BEFORE UPDATE ON audit_ledger
BEGIN
    SELECT RAISE(ABORT, 'audit_ledger is append-only');
END;

CREATE TRIGGER audit_ledger_no_delete
BEFORE DELETE ON audit_ledger
BEGIN
    SELECT RAISE(ABORT, 'audit_ledger is append-only');
END;

CREATE TABLE human_reviews (
    review_id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL UNIQUE,
    customer_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected')),
    reason TEXT,
    reviewer_subject TEXT,
    created_at REAL NOT NULL,
    decided_at REAL,
    FOREIGN KEY(recommendation_id) REFERENCES recommendations(recommendation_id)
);

CREATE INDEX idx_human_reviews_status_created ON human_reviews(status, created_at);
