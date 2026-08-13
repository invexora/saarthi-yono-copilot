CREATE TABLE IF NOT EXISTS governed_artifacts (
    artifact_id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL CHECK(artifact_type IN ('product_catalog', 'policy_registry')),
    version TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    envelope_json TEXT NOT NULL,
    signature TEXT NOT NULL,
    signing_key_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'materializing', 'active', 'rejected', 'superseded')),
    requested_by_ref TEXT NOT NULL,
    requested_at REAL NOT NULL,
    decided_by_ref TEXT,
    decided_at REAL,
    effective_at REAL,
    UNIQUE(artifact_type, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_governed_artifacts_one_pending
ON governed_artifacts(artifact_type) WHERE status IN ('pending', 'materializing');

CREATE UNIQUE INDEX IF NOT EXISTS idx_governed_artifacts_one_active
ON governed_artifacts(artifact_type) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_governed_artifacts_status_type
ON governed_artifacts(status, artifact_type, requested_at);
