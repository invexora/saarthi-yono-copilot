CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    signal TEXT NOT NULL,
    recommended_product_id TEXT,
    decision_token TEXT,
    risk_tier TEXT,
    delivery_mode TEXT,
    compliance_status INTEGER NOT NULL,
    execution_time_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_customer_timestamp
ON audit_logs(customer_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS dpdp_consent (
    customer_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    consent_status INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    consent_version TEXT NOT NULL,
    erasure_requested INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (customer_id, purpose)
);

CREATE TABLE IF NOT EXISTS nudge_budgets (
    customer_id TEXT PRIMARY KEY,
    cycle_start TEXT NOT NULL,
    nudge_count INTEGER NOT NULL,
    max_allowed INTEGER NOT NULL DEFAULT 2
);
