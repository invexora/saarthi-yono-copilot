DROP INDEX IF EXISTS idx_rollout_controls_one_pending;
DROP INDEX IF EXISTS idx_rollout_controls_one_active;
DROP INDEX IF EXISTS idx_rollout_controls_status_scope;

ALTER TABLE rollout_controls RENAME TO rollout_controls_pre_model_scope;

CREATE TABLE rollout_controls (
    control_id TEXT PRIMARY KEY,
    scope_type TEXT NOT NULL CHECK(scope_type IN ('global', 'channel', 'segment', 'signal', 'product', 'model')),
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

INSERT INTO rollout_controls (
    control_id, scope_type, scope_value, mode, cohort_percentage, status,
    reason, requested_by_ref, requested_at, decided_by_ref, decided_at, effective_at
)
SELECT
    control_id, scope_type, scope_value, mode, cohort_percentage, status,
    reason, requested_by_ref, requested_at, decided_by_ref, decided_at, effective_at
FROM rollout_controls_pre_model_scope;

DROP TABLE rollout_controls_pre_model_scope;

CREATE UNIQUE INDEX idx_rollout_controls_one_pending
ON rollout_controls(scope_type, scope_value) WHERE status = 'pending';

CREATE UNIQUE INDEX idx_rollout_controls_one_active
ON rollout_controls(scope_type, scope_value) WHERE status = 'active';

CREATE INDEX idx_rollout_controls_status_scope
ON rollout_controls(status, scope_type, scope_value);
