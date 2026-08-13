CREATE TABLE IF NOT EXISTS recommendation_outcomes (
    observation_id TEXT PRIMARY KEY,
    source_event_ref TEXT NOT NULL UNIQUE,
    recommendation_id TEXT NOT NULL,
    outcome_type TEXT NOT NULL CHECK(outcome_type IN (
        'converted', 'declined', 'complaint', 'opt_out',
        'false_positive', 'benefit', 'harm'
    )),
    source_system TEXT NOT NULL CHECK(source_system IN (
        'yono', 'crm', 'fulfillment', 'complaints', 'analytics'
    )),
    impact_score REAL CHECK(impact_score IS NULL OR (impact_score >= -1 AND impact_score <= 1)),
    evidence_digest TEXT NOT NULL,
    occurred_at REAL NOT NULL,
    recorded_at REAL NOT NULL,
    FOREIGN KEY(recommendation_id) REFERENCES recommendations(recommendation_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_recommendation_outcomes_time
ON recommendation_outcomes(occurred_at, outcome_type);

CREATE INDEX IF NOT EXISTS idx_recommendation_outcomes_recommendation
ON recommendation_outcomes(recommendation_id, outcome_type);
