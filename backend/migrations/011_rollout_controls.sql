CREATE TABLE IF NOT EXISTS rollout_controls (
    control_id TEXT PRIMARY KEY,
    scope_type TEXT NOT NULL CHECK(scope_type IN ('global', 'channel', 'segment', 'signal', 'product')),
    scope_value TEXT NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('active', 'shadow', 'disabled')),
    cohort_percentage INTEGER NOT NULL CHECK(cohort_percentage >= 0 AND cohort_percentage <= 100),
    status TEXT NOT NULL CHECK(status IN ('pending', 'active', 'rejected', 'superseded')),
    reason TEXT NOT NULL,
    requested_by_ref TEXT NOT NULL,
    requested_at REAL NOT NULL,
    decided_by_ref TEXT,
    decided_at REAL,
    effective_at REAL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rollout_controls_one_pending
ON rollout_controls(scope_type, scope_value) WHERE status = 'pending';

CREATE UNIQUE INDEX IF NOT EXISTS idx_rollout_controls_one_active
ON rollout_controls(scope_type, scope_value) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_rollout_controls_status_scope
ON rollout_controls(status, scope_type, scope_value);
