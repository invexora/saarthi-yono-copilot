CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    customer_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    interest_rate REAL,
    risk_tier TEXT NOT NULL,
    status TEXT NOT NULL,
    decision_token TEXT,
    authorized_at REAL
);

CREATE INDEX IF NOT EXISTS idx_recommendations_customer
ON recommendations(customer_id, created_at DESC);
