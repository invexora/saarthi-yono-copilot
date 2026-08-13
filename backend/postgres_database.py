import time
import hmac
import hashlib
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    case,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    and_,
    create_engine,
    delete,
    func,
    insert,
    or_,
    select,
    text,
    update,
)


METADATA = MetaData()

SCHEMA_MIGRATIONS = Table(
    "schema_migrations",
    METADATA,
    Column("version", String(100), primary_key=True),
    Column("applied_at", Float, nullable=False),
)

AUDIT_LOGS = Table(
    "audit_logs",
    METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("timestamp", String(50), nullable=False),
    Column("customer_id", String(64), nullable=False),
    Column("signal", String(1000), nullable=False),
    Column("recommended_product_id", String(100)),
    Column("decision_token", String(128)),
    Column("risk_tier", String(30)),
    Column("delivery_mode", String(50)),
    Column("compliance_status", Integer, nullable=False),
    Column("execution_time_ms", Integer, nullable=False),
)
Index("idx_audit_logs_customer_timestamp", AUDIT_LOGS.c.customer_id, AUDIT_LOGS.c.timestamp)

DPDP_CONSENT = Table(
    "dpdp_consent",
    METADATA,
    Column("customer_id", String(64), primary_key=True),
    Column("purpose", String(100), primary_key=True),
    Column("consent_status", Integer, nullable=False),
    Column("updated_at", String(50), nullable=False),
    Column("consent_version", String(20), nullable=False),
    Column("erasure_requested", Integer, nullable=False, default=0),
)

NUDGE_BUDGETS = Table(
    "nudge_budgets",
    METADATA,
    Column("customer_id", String(64), primary_key=True),
    Column("cycle_start", String(50), nullable=False),
    Column("nudge_count", Integer, nullable=False),
    Column("max_allowed", Integer, nullable=False, default=2),
)

RECOMMENDATIONS = Table(
    "recommendations",
    METADATA,
    Column("recommendation_id", String(100), primary_key=True),
    Column("created_at", Float, nullable=False),
    Column("expires_at", Float, nullable=False),
    Column("customer_id", String(64), nullable=False),
    Column("product_id", String(100), nullable=False),
    Column("interest_rate", Float),
    Column("risk_tier", String(30), nullable=False),
    Column("status", String(30), nullable=False),
    Column("decision_token", String(128)),
    Column("authorized_at", Float),
    Column("evidence_json", JSON),
    Column("presented_at", Float),
    Column("execution_started_at", Float),
    Column("fulfillment_reference", String(200)),
    Column("fulfilled_at", Float),
    Column("fulfillment_response_json", JSON),
)
Index("idx_recommendations_customer", RECOMMENDATIONS.c.customer_id, RECOMMENDATIONS.c.created_at)

AUDIT_LEDGER = Table(
    "audit_ledger",
    METADATA,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("event_id", String(100), nullable=False, unique=True),
    Column("occurred_at", String(50), nullable=False),
    Column("customer_ref", String(64), nullable=False),
    Column("event_type", String(100), nullable=False),
    Column("payload_json", String(5000), nullable=False),
    Column("previous_hash", String(64), nullable=False),
    Column("record_hash", String(64), nullable=False, unique=True),
    Column("key_version", String(30), nullable=False),
)
Index("idx_audit_ledger_customer_ref", AUDIT_LEDGER.c.customer_ref, AUDIT_LEDGER.c.sequence)

HUMAN_REVIEWS = Table(
    "human_reviews",
    METADATA,
    Column("review_id", String(100), primary_key=True),
    Column("recommendation_id", String(100), nullable=False, unique=True),
    Column("customer_id", String(64), nullable=False),
    Column("status", String(30), nullable=False),
    Column("reason", String(1000)),
    Column("reviewer_subject", String(200)),
    Column("created_at", Float, nullable=False),
    Column("decided_at", Float),
    Column("evidence_json", JSON),
)
Index("idx_human_reviews_status_created", HUMAN_REVIEWS.c.status, HUMAN_REVIEWS.c.created_at)

REQUEST_IDEMPOTENCY = Table(
    "request_idempotency",
    METADATA,
    Column("customer_id", String(64), primary_key=True),
    Column("idempotency_key", String(128), primary_key=True),
    Column("state", String(30), nullable=False),
    Column("response_json", JSON),
    Column("http_status", Integer),
    Column("created_at", Float, nullable=False),
    Column("expires_at", Float, nullable=False),
)
Index("idx_request_idempotency_expiry", REQUEST_IDEMPOTENCY.c.expires_at)

EVENT_PROCESSING_RECEIPTS = Table(
    "event_processing_receipts",
    METADATA,
    Column("event_id", String(100), primary_key=True),
    Column("event_type", String(100), nullable=False),
    Column("customer_ref", String(64), nullable=False),
    Column("payload_digest", String(64), nullable=False),
    Column("consumer_name", String(200), nullable=False),
    Column("processed_at", Float, nullable=False),
)
Index("idx_event_processing_receipts_processed_at", EVENT_PROCESSING_RECEIPTS.c.processed_at.desc())

FULFILLMENT_RECONCILIATIONS = Table(
    "fulfillment_reconciliations",
    METADATA,
    Column(
        "recommendation_id", String(100),
        ForeignKey("recommendations.recommendation_id"), primary_key=True,
    ),
    Column("fulfillment_reference", String(200), nullable=False),
    Column("status", String(30), nullable=False),
    Column("provider_status", String(30), nullable=False),
    Column("attempt_count", Integer, nullable=False, default=0),
    Column("created_at", Float, nullable=False),
    Column("checking_started_at", Float),
    Column("last_checked_at", Float),
    Column("next_check_at", Float),
    Column("provider_response_digest", String(64)),
    Column("last_error_code", String(100)),
    Column("acknowledged_at", Float),
    Column("acknowledged_by", String(64)),
    Column("acknowledgement_note", String(1000)),
    CheckConstraint(
        "status IN ('pending', 'checking', 'matched', 'mismatch', 'retry')",
        name="ck_fulfillment_reconciliation_status",
    ),
    CheckConstraint("attempt_count >= 0", name="ck_fulfillment_reconciliation_attempts"),
)
Index(
    "idx_fulfillment_reconciliation_status_due",
    FULFILLMENT_RECONCILIATIONS.c.status,
    FULFILLMENT_RECONCILIATIONS.c.next_check_at,
)

OPERATIONS_CASES = Table(
    "operations_cases",
    METADATA,
    Column("case_id", String(100), primary_key=True),
    Column(
        "recommendation_id", String(100),
        ForeignKey("fulfillment_reconciliations.recommendation_id"),
        nullable=False, unique=True,
    ),
    Column("status", String(30), nullable=False),
    Column("safe_summary", String(1000), nullable=False),
    Column("requested_by_ref", String(64), nullable=False),
    Column("requested_at", Float, nullable=False),
    Column("approved_by_ref", String(64)),
    Column("approved_at", Float),
    Column("action_started_at", Float),
    Column("attempt_count", Integer, nullable=False, default=0),
    Column("external_case_reference", String(200)),
    Column("provider_status", String(30)),
    Column("provider_response_digest", String(64)),
    Column("last_synced_at", Float),
    Column("next_action_at", Float),
    Column("last_error_code", String(100)),
    CheckConstraint(
        "status IN ('draft', 'approved', 'submitting', 'submission_retry', 'open', "
        "'in_progress', 'syncing', 'sync_retry', 'resolved', 'closed', 'rejected')",
        name="ck_operations_case_status",
    ),
    CheckConstraint("attempt_count >= 0", name="ck_operations_case_attempts"),
)
Index("idx_operations_cases_status_due", OPERATIONS_CASES.c.status, OPERATIONS_CASES.c.next_action_at)

ROLLOUT_CONTROLS = Table(
    "rollout_controls",
    METADATA,
    Column("control_id", String(100), primary_key=True),
    Column("scope_type", String(30), nullable=False),
    Column("scope_value", String(200), nullable=False),
    Column("mode", String(30), nullable=False),
    Column("cohort_percentage", Integer, nullable=False),
    Column("status", String(30), nullable=False),
    Column("reason", String(1000), nullable=False),
    Column("requested_by_ref", String(64), nullable=False),
    Column("requested_at", Float, nullable=False),
    Column("decided_by_ref", String(64)),
    Column("decided_at", Float),
    Column("effective_at", Float),
    CheckConstraint(
        "scope_type IN ('global', 'channel', 'segment', 'signal', 'product', 'model')",
        name="ck_rollout_control_scope",
    ),
    CheckConstraint(
        "mode IN ('active', 'shadow', 'disabled')",
        name="ck_rollout_control_mode",
    ),
    CheckConstraint(
        "status IN ('pending', 'active', 'rejected', 'superseded')",
        name="ck_rollout_control_status",
    ),
    CheckConstraint(
        "cohort_percentage >= 0 AND cohort_percentage <= 100",
        name="ck_rollout_control_cohort",
    ),
)
Index(
    "idx_rollout_controls_one_pending",
    ROLLOUT_CONTROLS.c.scope_type,
    ROLLOUT_CONTROLS.c.scope_value,
    unique=True,
    postgresql_where=ROLLOUT_CONTROLS.c.status == "pending",
    sqlite_where=ROLLOUT_CONTROLS.c.status == "pending",
)
Index(
    "idx_rollout_controls_one_active",
    ROLLOUT_CONTROLS.c.scope_type,
    ROLLOUT_CONTROLS.c.scope_value,
    unique=True,
    postgresql_where=ROLLOUT_CONTROLS.c.status == "active",
    sqlite_where=ROLLOUT_CONTROLS.c.status == "active",
)
Index("idx_rollout_controls_status_scope", ROLLOUT_CONTROLS.c.status, ROLLOUT_CONTROLS.c.scope_type, ROLLOUT_CONTROLS.c.scope_value)

RECOMMENDATION_OUTCOMES = Table(
    "recommendation_outcomes",
    METADATA,
    Column("observation_id", String(100), primary_key=True),
    Column("source_event_ref", String(64), nullable=False, unique=True),
    Column(
        "recommendation_id", String(100),
        ForeignKey("recommendations.recommendation_id", ondelete="CASCADE"), nullable=False,
    ),
    Column("outcome_type", String(30), nullable=False),
    Column("source_system", String(30), nullable=False),
    Column("impact_score", Float),
    Column("evidence_digest", String(64), nullable=False),
    Column("occurred_at", Float, nullable=False),
    Column("recorded_at", Float, nullable=False),
    CheckConstraint(
        "outcome_type IN ('converted', 'declined', 'complaint', 'opt_out', "
        "'false_positive', 'benefit', 'harm')",
        name="ck_recommendation_outcome_type",
    ),
    CheckConstraint(
        "source_system IN ('yono', 'crm', 'fulfillment', 'complaints', 'analytics')",
        name="ck_recommendation_outcome_source",
    ),
    CheckConstraint(
        "impact_score IS NULL OR (impact_score >= -1 AND impact_score <= 1)",
        name="ck_recommendation_outcome_impact",
    ),
)
Index(
    "idx_recommendation_outcomes_time",
    RECOMMENDATION_OUTCOMES.c.occurred_at,
    RECOMMENDATION_OUTCOMES.c.outcome_type,
)
Index(
    "idx_recommendation_outcomes_recommendation",
    RECOMMENDATION_OUTCOMES.c.recommendation_id,
    RECOMMENDATION_OUTCOMES.c.outcome_type,
)

GOVERNED_ARTIFACTS = Table(
    "governed_artifacts",
    METADATA,
    Column("artifact_id", String(100), primary_key=True),
    Column("artifact_type", String(30), nullable=False),
    Column("version", String(100), nullable=False),
    Column("content_digest", String(64), nullable=False),
    Column("envelope_json", JSON, nullable=False),
    Column("signature", String(200), nullable=False),
    Column("signing_key_id", String(100), nullable=False),
    Column("status", String(30), nullable=False),
    Column("requested_by_ref", String(64), nullable=False),
    Column("requested_at", Float, nullable=False),
    Column("decided_by_ref", String(64)),
    Column("decided_at", Float),
    Column("effective_at", Float),
    CheckConstraint(
        "artifact_type IN ('product_catalog', 'policy_registry')",
        name="ck_governed_artifact_type",
    ),
    CheckConstraint(
        "status IN ('pending', 'materializing', 'active', 'rejected', 'superseded')",
        name="ck_governed_artifact_status",
    ),
)
Index(
    "uq_governed_artifact_type_version",
    GOVERNED_ARTIFACTS.c.artifact_type,
    GOVERNED_ARTIFACTS.c.version,
    unique=True,
)
Index(
    "idx_governed_artifacts_one_pending",
    GOVERNED_ARTIFACTS.c.artifact_type,
    unique=True,
    postgresql_where=GOVERNED_ARTIFACTS.c.status.in_(["pending", "materializing"]),
    sqlite_where=GOVERNED_ARTIFACTS.c.status.in_(["pending", "materializing"]),
)
Index(
    "idx_governed_artifacts_one_active",
    GOVERNED_ARTIFACTS.c.artifact_type,
    unique=True,
    postgresql_where=GOVERNED_ARTIFACTS.c.status == "active",
    sqlite_where=GOVERNED_ARTIFACTS.c.status == "active",
)
Index(
    "idx_governed_artifacts_status_type",
    GOVERNED_ARTIFACTS.c.status,
    GOVERNED_ARTIFACTS.c.artifact_type,
    GOVERNED_ARTIFACTS.c.requested_at,
)


class PostgresDatabaseManager:
    """SQLAlchemy Core persistence used for PostgreSQL production deployments.

    The implementation also accepts a SQLite SQLAlchemy URL for contract tests.
    """

    MIGRATION_VERSION = "011_governed_artifacts_schema"

    def __init__(self, database_url, engine=None):
        self.database_url = database_url
        self.engine = engine or create_engine(database_url, pool_pre_ping=True, future=True)
        self.db_path = database_url
        self._run_migrations()

    def _run_migrations(self):
        SCHEMA_MIGRATIONS.create(self.engine, checkfirst=True)
        with self.engine.begin() as conn:
            METADATA.create_all(conn)
            migration = self._dialect_insert(SCHEMA_MIGRATIONS).values(
                version=self.MIGRATION_VERSION,
                applied_at=time.time(),
            ).on_conflict_do_nothing(index_elements=[SCHEMA_MIGRATIONS.c.version])
            conn.execute(migration)
            reconciliation_backfill = self._dialect_insert(FULFILLMENT_RECONCILIATIONS).from_select(
                [
                    "recommendation_id", "fulfillment_reference", "status", "provider_status",
                    "attempt_count", "created_at", "next_check_at",
                ],
                select(
                    RECOMMENDATIONS.c.recommendation_id,
                    RECOMMENDATIONS.c.fulfillment_reference,
                    text("'pending'"),
                    text("'unknown'"),
                    text("0"),
                    func.coalesce(RECOMMENDATIONS.c.fulfilled_at, RECOMMENDATIONS.c.created_at),
                    func.coalesce(RECOMMENDATIONS.c.fulfilled_at, RECOMMENDATIONS.c.created_at),
                ).where(and_(
                    RECOMMENDATIONS.c.status == "fulfilled",
                    RECOMMENDATIONS.c.fulfillment_reference.is_not(None),
                )),
            ).on_conflict_do_nothing(index_elements=[FULFILLMENT_RECONCILIATIONS.c.recommendation_id])
            conn.execute(reconciliation_backfill)
            if self.engine.dialect.name == "postgresql":
                conn.execute(text(
                    "ALTER TABLE rollout_controls DROP CONSTRAINT IF EXISTS ck_rollout_control_scope"
                ))
                conn.execute(text('''
                    ALTER TABLE rollout_controls ADD CONSTRAINT ck_rollout_control_scope
                    CHECK(scope_type IN ('global', 'channel', 'segment', 'signal', 'product', 'model'))
                '''))
                conn.execute(text("ALTER TABLE human_reviews ADD COLUMN IF NOT EXISTS evidence_json JSON"))
                conn.execute(text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS evidence_json JSON"))
                conn.execute(text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS presented_at DOUBLE PRECISION"))
                conn.execute(text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS execution_started_at DOUBLE PRECISION"))
                conn.execute(text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS fulfillment_reference VARCHAR(200)"))
                conn.execute(text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS fulfilled_at DOUBLE PRECISION"))
                conn.execute(text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS fulfillment_response_json JSON"))
                conn.execute(text("UPDATE recommendations SET status='presented', presented_at=created_at WHERE status='pending'"))
                conn.execute(text('''
                    CREATE OR REPLACE FUNCTION saarthi_reject_audit_ledger_mutation()
                    RETURNS trigger AS $$ BEGIN
                        RAISE EXCEPTION 'audit_ledger is append-only';
                    END; $$ LANGUAGE plpgsql
                '''))
                conn.execute(text("DROP TRIGGER IF EXISTS audit_ledger_no_mutation ON audit_ledger"))
                conn.execute(text('''
                    CREATE TRIGGER audit_ledger_no_mutation BEFORE UPDATE OR DELETE ON audit_ledger
                    FOR EACH ROW EXECUTE FUNCTION saarthi_reject_audit_ledger_mutation()
                '''))
            elif self.engine.dialect.name == "sqlite":
                rollout_sql = conn.exec_driver_sql(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='rollout_controls'"
                ).scalar_one()
                if "'model'" not in rollout_sql:
                    conn.exec_driver_sql("DROP INDEX IF EXISTS idx_rollout_controls_one_pending")
                    conn.exec_driver_sql("DROP INDEX IF EXISTS idx_rollout_controls_one_active")
                    conn.exec_driver_sql("DROP INDEX IF EXISTS idx_rollout_controls_status_scope")
                    conn.exec_driver_sql(
                        "ALTER TABLE rollout_controls RENAME TO rollout_controls_pre_model_scope"
                    )
                    ROLLOUT_CONTROLS.create(conn)
                    conn.exec_driver_sql('''
                        INSERT INTO rollout_controls (
                            control_id, scope_type, scope_value, mode, cohort_percentage,
                            status, reason, requested_by_ref, requested_at,
                            decided_by_ref, decided_at, effective_at
                        )
                        SELECT control_id, scope_type, scope_value, mode, cohort_percentage,
                               status, reason, requested_by_ref, requested_at,
                               decided_by_ref, decided_at, effective_at
                        FROM rollout_controls_pre_model_scope
                    ''')
                    conn.exec_driver_sql("DROP TABLE rollout_controls_pre_model_scope")
                review_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(human_reviews)")}
                if "evidence_json" not in review_columns:
                    conn.exec_driver_sql("ALTER TABLE human_reviews ADD COLUMN evidence_json JSON")
                recommendation_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(recommendations)")}
                if "evidence_json" not in recommendation_columns:
                    conn.exec_driver_sql("ALTER TABLE recommendations ADD COLUMN evidence_json JSON")
                if "presented_at" not in recommendation_columns:
                    conn.exec_driver_sql("ALTER TABLE recommendations ADD COLUMN presented_at FLOAT")
                if "execution_started_at" not in recommendation_columns:
                    conn.exec_driver_sql("ALTER TABLE recommendations ADD COLUMN execution_started_at FLOAT")
                if "fulfillment_reference" not in recommendation_columns:
                    conn.exec_driver_sql("ALTER TABLE recommendations ADD COLUMN fulfillment_reference VARCHAR(200)")
                if "fulfilled_at" not in recommendation_columns:
                    conn.exec_driver_sql("ALTER TABLE recommendations ADD COLUMN fulfilled_at FLOAT")
                if "fulfillment_response_json" not in recommendation_columns:
                    conn.exec_driver_sql("ALTER TABLE recommendations ADD COLUMN fulfillment_response_json JSON")
                conn.exec_driver_sql("UPDATE recommendations SET status='presented', presented_at=created_at WHERE status='pending'")
                conn.exec_driver_sql("CREATE TRIGGER IF NOT EXISTS audit_ledger_no_update BEFORE UPDATE ON audit_ledger BEGIN SELECT RAISE(ABORT, 'audit_ledger is append-only'); END")
                conn.exec_driver_sql("CREATE TRIGGER IF NOT EXISTS audit_ledger_no_delete BEFORE DELETE ON audit_ledger BEGIN SELECT RAISE(ABORT, 'audit_ledger is append-only'); END")

    def get_applied_migrations(self):
        with self.engine.connect() as conn:
            return list(conn.execute(select(SCHEMA_MIGRATIONS.c.version).order_by(SCHEMA_MIGRATIONS.c.version)).scalars())

    def _dialect_insert(self, table):
        if self.engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        else:
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        return dialect_insert(table)

    @staticmethod
    def _rows(result):
        return [dict(row) for row in result.mappings()]

    def log_audit_event(self, customer_id, signal, recommended_product_id, decision_token, risk_tier, delivery_mode, compliance_status, execution_time_ms):
        with self.engine.begin() as conn:
            conn.execute(insert(AUDIT_LOGS).values(
                timestamp=str(time.time()),
                customer_id=customer_id,
                signal=signal,
                recommended_product_id=recommended_product_id,
                decision_token=decision_token,
                risk_tier=risk_tier,
                delivery_mode=delivery_mode,
                compliance_status=compliance_status,
                execution_time_ms=execution_time_ms,
            ))

    def get_audit_logs(self, customer_id=None, limit=50):
        statement = select(AUDIT_LOGS)
        if customer_id:
            statement = statement.where(AUDIT_LOGS.c.customer_id == customer_id)
        statement = statement.order_by(AUDIT_LOGS.c.timestamp.desc()).limit(limit)
        with self.engine.connect() as conn:
            return self._rows(conn.execute(statement))

    def get_consent_status(self, customer_id):
        with self.engine.connect() as conn:
            return self._rows(conn.execute(select(DPDP_CONSENT).where(DPDP_CONSENT.c.customer_id == customer_id)))

    def update_consent(self, customer_id, purpose, granted):
        now = str(time.time())
        statement = self._dialect_insert(DPDP_CONSENT).values(
            customer_id=customer_id,
            purpose=purpose,
            consent_status=1 if granted else 0,
            updated_at=now,
            consent_version="1.0",
            erasure_requested=0,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[DPDP_CONSENT.c.customer_id, DPDP_CONSENT.c.purpose],
            set_={"consent_status": 1 if granted else 0, "updated_at": now, "erasure_requested": 0},
        )
        with self.engine.begin() as conn:
            conn.execute(statement)

    def revoke_consent(self, customer_id, purpose=None):
        statement = update(DPDP_CONSENT).where(DPDP_CONSENT.c.customer_id == customer_id)
        if purpose:
            statement = statement.where(DPDP_CONSENT.c.purpose == purpose)
        with self.engine.begin() as conn:
            result = conn.execute(statement.values(consent_status=0, updated_at=str(time.time())))
            return result.rowcount

    def process_erasure_request(self, customer_id):
        now = str(time.time())
        with self.engine.begin() as conn:
            conn.execute(delete(AUDIT_LOGS).where(AUDIT_LOGS.c.customer_id == customer_id))
            result = conn.execute(
                update(DPDP_CONSENT)
                .where(DPDP_CONSENT.c.customer_id == customer_id)
                .values(consent_status=0, updated_at=now, erasure_requested=1)
            )
            if result.rowcount == 0:
                conn.execute(insert(DPDP_CONSENT).values(
                    customer_id=customer_id,
                    purpose="personalization",
                    consent_status=0,
                    updated_at=now,
                    consent_version="1.0",
                    erasure_requested=1,
                ))
            recommendation_ids = select(RECOMMENDATIONS.c.recommendation_id).where(
                RECOMMENDATIONS.c.customer_id == customer_id
            )
            conn.execute(delete(RECOMMENDATION_OUTCOMES).where(
                RECOMMENDATION_OUTCOMES.c.recommendation_id.in_(recommendation_ids)
            ))
            conn.execute(delete(OPERATIONS_CASES).where(
                OPERATIONS_CASES.c.recommendation_id.in_(recommendation_ids)
            ))
            conn.execute(delete(FULFILLMENT_RECONCILIATIONS).where(
                FULFILLMENT_RECONCILIATIONS.c.recommendation_id.in_(recommendation_ids)
            ))
            for table in (NUDGE_BUDGETS, HUMAN_REVIEWS, RECOMMENDATIONS, REQUEST_IDEMPOTENCY):
                conn.execute(delete(table).where(table.c.customer_id == customer_id))

    def export_customer_data(self, customer_id):
        return {
            "audit_logs": self.get_audit_logs(customer_id=customer_id, limit=1000),
            "consent_status": self.get_consent_status(customer_id),
            "outcomes": self.get_customer_outcomes(customer_id),
        }

    def check_nudge_budget(self, customer_id):
        return self.get_nudge_budget_status(customer_id)["allowed"]

    def get_nudge_budget_status(self, customer_id, max_allowed=2, cycle_days=14):
        now = time.time()
        with self.engine.connect() as conn:
            row = conn.execute(select(NUDGE_BUDGETS).where(NUDGE_BUDGETS.c.customer_id == customer_id)).mappings().first()
        if not row:
            return {"allowed": True, "used": 0, "max_allowed": max_allowed, "remaining": max_allowed, "cycle_start": None}
        cycle_start = float(row["cycle_start"])
        count = 0 if now - cycle_start >= cycle_days * 86400 else int(row["nudge_count"])
        stored_max = int(row["max_allowed"])
        return {
            "allowed": count < stored_max,
            "used": count,
            "max_allowed": stored_max,
            "remaining": max(0, stored_max - count),
            "cycle_start": datetime.fromtimestamp(cycle_start, timezone.utc).isoformat(),
        }

    def consume_nudge_budget(self, customer_id, max_allowed=2, cycle_days=14):
        now = time.time()
        with self.engine.begin() as conn:
            seed = self._dialect_insert(NUDGE_BUDGETS).values(
                customer_id=customer_id,
                cycle_start=str(now),
                nudge_count=0,
                max_allowed=max_allowed,
            ).on_conflict_do_nothing(index_elements=[NUDGE_BUDGETS.c.customer_id])
            conn.execute(seed)
            row = conn.execute(
                select(NUDGE_BUDGETS)
                .where(NUDGE_BUDGETS.c.customer_id == customer_id)
                .with_for_update()
            ).mappings().first()
            if now - float(row["cycle_start"]) >= cycle_days * 86400:
                cycle_start, used, stored_max = now, 0, max_allowed
            else:
                cycle_start, used, stored_max = float(row["cycle_start"]), int(row["nudge_count"]), int(row["max_allowed"])
            if used >= stored_max:
                return {
                    "allowed": False,
                    "used": used,
                    "max_allowed": stored_max,
                    "remaining": 0,
                    "cycle_start": datetime.fromtimestamp(cycle_start, timezone.utc).isoformat(),
                }
            used += 1
            conn.execute(
                update(NUDGE_BUDGETS)
                .where(NUDGE_BUDGETS.c.customer_id == customer_id)
                .values(cycle_start=str(cycle_start), nudge_count=used, max_allowed=stored_max)
            )
            return {
                "allowed": True,
                "used": used,
                "max_allowed": stored_max,
                "remaining": stored_max - used,
                "cycle_start": datetime.fromtimestamp(cycle_start, timezone.utc).isoformat(),
            }

    def create_recommendation(self, recommendation_id, customer_id, product_id, interest_rate, risk_tier, ttl_seconds=600):
        return self.create_recommendation_with_status(recommendation_id, customer_id, product_id, interest_rate, risk_tier, "presented", ttl_seconds)

    def create_recommendation_with_status(self, recommendation_id, customer_id, product_id, interest_rate, risk_tier, initial_status="presented", ttl_seconds=600, evidence=None):
        now = time.time()
        with self.engine.begin() as conn:
            conn.execute(insert(RECOMMENDATIONS).values(
                recommendation_id=recommendation_id,
                created_at=now,
                expires_at=now + ttl_seconds,
                customer_id=customer_id,
                product_id=product_id,
                interest_rate=interest_rate,
                risk_tier=risk_tier,
                status=initial_status,
                evidence_json=evidence or {},
                presented_at=now if initial_status == "presented" else None,
            ))

    def authorize_recommendation(self, recommendation_id, customer_id, decision_token):
        now = time.time()
        decision_token_hash = hashlib.sha256(decision_token.encode()).hexdigest()
        with self.engine.begin() as conn:
            row = conn.execute(
                select(RECOMMENDATIONS)
                .where(and_(
                    RECOMMENDATIONS.c.recommendation_id == recommendation_id,
                    RECOMMENDATIONS.c.customer_id == customer_id,
                ))
                .with_for_update()
            ).mappings().first()
            if not row:
                return None, "not_found"
            row = dict(row)
            if row["status"] != "presented":
                if row["status"] == "pending_review":
                    return row, "review_required"
                if row["status"] == "approved":
                    return row, "offer_not_presented"
                if row["status"] == "rejected":
                    return row, "review_rejected"
                return row, "already_authorized"
            if row["expires_at"] <= now:
                conn.execute(update(RECOMMENDATIONS).where(RECOMMENDATIONS.c.recommendation_id == recommendation_id).values(status="expired"))
                return row, "expired"
            conn.execute(
                update(RECOMMENDATIONS)
                .where(RECOMMENDATIONS.c.recommendation_id == recommendation_id)
                .values(status="authorized", decision_token=decision_token_hash, authorized_at=now)
            )
            row.update(status="authorized", decision_token=decision_token_hash, authorized_at=now)
            return row, "authorized"

    def recommendation_belongs_to_customer(self, recommendation_id, customer_id):
        with self.engine.connect() as conn:
            return conn.execute(select(RECOMMENDATIONS.c.recommendation_id).where(and_(
                RECOMMENDATIONS.c.recommendation_id == recommendation_id,
                RECOMMENDATIONS.c.customer_id == customer_id,
            ))).first() is not None

    def get_recommendation_context(self, recommendation_id, customer_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(
                RECOMMENDATIONS.c.recommendation_id,
                RECOMMENDATIONS.c.customer_id,
                RECOMMENDATIONS.c.product_id,
                RECOMMENDATIONS.c.risk_tier,
                RECOMMENDATIONS.c.status,
                RECOMMENDATIONS.c.evidence_json,
            ).where(and_(
                RECOMMENDATIONS.c.recommendation_id == recommendation_id,
                RECOMMENDATIONS.c.customer_id == customer_id,
            ))).mappings().first()
            if not row:
                return None
            result = dict(row)
            result["evidence"] = result.pop("evidence_json") or {}
            return result

    def claim_execution(self, recommendation_id, customer_id, decision_token, token_ttl_seconds=300, processing_timeout_seconds=60):
        now = time.time()
        with self.engine.begin() as conn:
            row = conn.execute(select(RECOMMENDATIONS).where(and_(
                RECOMMENDATIONS.c.recommendation_id == recommendation_id,
                RECOMMENDATIONS.c.customer_id == customer_id,
            )).with_for_update()).mappings().first()
            if not row:
                return None, "not_found"
            row = dict(row)
            supplied_token_hash = hashlib.sha256((decision_token or "").encode()).hexdigest()
            stored_token_hash = row.get("decision_token") or ""
            token_matches = hmac.compare_digest(stored_token_hash, supplied_token_hash)
            legacy_token_matches = bool(decision_token) and hmac.compare_digest(stored_token_hash, decision_token)
            if not decision_token or not (token_matches or legacy_token_matches):
                return None, "invalid_token"
            if legacy_token_matches:
                conn.execute(update(RECOMMENDATIONS).where(RECOMMENDATIONS.c.recommendation_id == recommendation_id).values(decision_token=supplied_token_hash))
                row["decision_token"] = supplied_token_hash
            if row["status"] == "fulfilled":
                row["fulfillment_response"] = row.get("fulfillment_response_json") or {}
                return row, "already_fulfilled"
            if row["status"] == "executing":
                if now - float(row.get("execution_started_at") or 0) < processing_timeout_seconds:
                    return None, "in_progress"
            elif row["status"] != "authorized":
                return None, "not_authorized"
            if now - float(row.get("authorized_at") or 0) > token_ttl_seconds:
                return None, "token_expired"
            conn.execute(update(RECOMMENDATIONS).where(RECOMMENDATIONS.c.recommendation_id == recommendation_id).values(
                status="executing", execution_started_at=now,
            ))
            row.update(status="executing", execution_started_at=now)
            return row, "claimed"

    def complete_execution(self, recommendation_id, customer_id, result):
        now = time.time()
        with self.engine.begin() as conn:
            update_result = conn.execute(update(RECOMMENDATIONS).where(and_(
                RECOMMENDATIONS.c.recommendation_id == recommendation_id,
                RECOMMENDATIONS.c.customer_id == customer_id,
                RECOMMENDATIONS.c.status == "executing",
            )).values(
                status="fulfilled",
                fulfillment_reference=result["reference"],
                fulfilled_at=now,
                fulfillment_response_json=result,
            ))
            if update_result.rowcount != 1:
                raise RuntimeError("Execution claim was lost before completion")
            reconciliation = self._dialect_insert(FULFILLMENT_RECONCILIATIONS).values(
                recommendation_id=recommendation_id,
                fulfillment_reference=result["reference"],
                status="pending",
                provider_status="unknown",
                attempt_count=0,
                created_at=now,
                next_check_at=now,
            ).on_conflict_do_nothing(index_elements=[FULFILLMENT_RECONCILIATIONS.c.recommendation_id])
            conn.execute(reconciliation)

    def abandon_execution(self, recommendation_id, customer_id):
        with self.engine.begin() as conn:
            conn.execute(update(RECOMMENDATIONS).where(and_(
                RECOMMENDATIONS.c.recommendation_id == recommendation_id,
                RECOMMENDATIONS.c.customer_id == customer_id,
                RECOMMENDATIONS.c.status == "executing",
            )).values(status="authorized", execution_started_at=None))

    def claim_fulfillment_reconciliation(self, recommendation_id, processing_timeout_seconds=60):
        now = time.time()
        with self.engine.begin() as conn:
            row = conn.execute(
                select(FULFILLMENT_RECONCILIATIONS, RECOMMENDATIONS.c.customer_id, RECOMMENDATIONS.c.status.label("local_status"))
                .join(RECOMMENDATIONS, RECOMMENDATIONS.c.recommendation_id == FULFILLMENT_RECONCILIATIONS.c.recommendation_id)
                .where(FULFILLMENT_RECONCILIATIONS.c.recommendation_id == recommendation_id)
                .with_for_update()
            ).mappings().first()
            if not row:
                return None, "not_found"
            row = dict(row)
            if row["status"] == "matched":
                return row, "already_matched"
            if row["status"] == "checking" and now - float(row.get("checking_started_at") or 0) < processing_timeout_seconds:
                return None, "in_progress"
            conn.execute(update(FULFILLMENT_RECONCILIATIONS).where(
                FULFILLMENT_RECONCILIATIONS.c.recommendation_id == recommendation_id
            ).values(
                status="checking",
                checking_started_at=now,
                attempt_count=FULFILLMENT_RECONCILIATIONS.c.attempt_count + 1,
                last_error_code=None,
            ))
            row.update(status="checking", checking_started_at=now, attempt_count=row["attempt_count"] + 1)
            return row, "claimed"

    def complete_fulfillment_reconciliation(self, recommendation_id, provider_status, provider_reference, provider_response_digest, retry_seconds=60):
        now = time.time()
        with self.engine.begin() as conn:
            row = conn.execute(select(FULFILLMENT_RECONCILIATIONS).where(
                FULFILLMENT_RECONCILIATIONS.c.recommendation_id == recommendation_id
            ).with_for_update()).mappings().first()
            if not row or row["status"] != "checking":
                return None, "claim_lost"
            row = dict(row)
            if provider_status == "completed" and provider_reference == row["fulfillment_reference"]:
                outcome, next_check_at = "matched", None
            elif provider_status in {"pending", "processing"}:
                outcome, next_check_at = "retry", now + retry_seconds
            else:
                outcome, next_check_at = "mismatch", None
            conn.execute(update(FULFILLMENT_RECONCILIATIONS).where(and_(
                FULFILLMENT_RECONCILIATIONS.c.recommendation_id == recommendation_id,
                FULFILLMENT_RECONCILIATIONS.c.status == "checking",
            )).values(
                status=outcome,
                provider_status=provider_status,
                checking_started_at=None,
                last_checked_at=now,
                next_check_at=next_check_at,
                provider_response_digest=provider_response_digest,
                last_error_code=None,
            ))
            row.update(
                status=outcome, provider_status=provider_status, checking_started_at=None,
                last_checked_at=now, next_check_at=next_check_at,
                provider_response_digest=provider_response_digest, last_error_code=None,
            )
            return row, outcome

    def fail_fulfillment_reconciliation(self, recommendation_id, error_code, retry_seconds=60):
        now = time.time()
        with self.engine.begin() as conn:
            result = conn.execute(update(FULFILLMENT_RECONCILIATIONS).where(and_(
                FULFILLMENT_RECONCILIATIONS.c.recommendation_id == recommendation_id,
                FULFILLMENT_RECONCILIATIONS.c.status == "checking",
            )).values(
                status="retry",
                checking_started_at=None,
                last_checked_at=now,
                next_check_at=now + retry_seconds,
                last_error_code=error_code,
            ))
            return result.rowcount == 1

    def list_fulfillment_reconciliations(self, reconciliation_status=None, limit=100):
        statement = select(FULFILLMENT_RECONCILIATIONS)
        if reconciliation_status:
            statement = statement.where(FULFILLMENT_RECONCILIATIONS.c.status == reconciliation_status)
        statement = statement.order_by(FULFILLMENT_RECONCILIATIONS.c.created_at).limit(limit)
        with self.engine.connect() as conn:
            return self._rows(conn.execute(statement))

    def get_fulfillment_reconciliation(self, recommendation_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(FULFILLMENT_RECONCILIATIONS).where(
                FULFILLMENT_RECONCILIATIONS.c.recommendation_id == recommendation_id
            )).mappings().first()
            return dict(row) if row else None

    def list_due_fulfillment_reconciliations(self, limit=25, processing_timeout_seconds=60):
        now = time.time()
        due = or_(
            and_(
                FULFILLMENT_RECONCILIATIONS.c.status.in_(["pending", "retry"]),
                func.coalesce(FULFILLMENT_RECONCILIATIONS.c.next_check_at, 0) <= now,
            ),
            and_(
                FULFILLMENT_RECONCILIATIONS.c.status == "checking",
                func.coalesce(FULFILLMENT_RECONCILIATIONS.c.checking_started_at, 0) <= now - processing_timeout_seconds,
            ),
        )
        with self.engine.connect() as conn:
            return list(conn.execute(
                select(FULFILLMENT_RECONCILIATIONS.c.recommendation_id)
                .where(due)
                .order_by(
                    func.coalesce(
                        FULFILLMENT_RECONCILIATIONS.c.next_check_at,
                        FULFILLMENT_RECONCILIATIONS.c.created_at,
                    ),
                    FULFILLMENT_RECONCILIATIONS.c.created_at,
                )
                .limit(limit)
            ).scalars())

    def acknowledge_fulfillment_mismatch(self, recommendation_id, operator_ref, note):
        now = time.time()
        with self.engine.begin() as conn:
            result = conn.execute(update(FULFILLMENT_RECONCILIATIONS).where(and_(
                FULFILLMENT_RECONCILIATIONS.c.recommendation_id == recommendation_id,
                FULFILLMENT_RECONCILIATIONS.c.status == "mismatch",
            )).values(
                acknowledged_at=now,
                acknowledged_by=operator_ref,
                acknowledgement_note=note,
            ))
            if result.rowcount != 1:
                return None
        return self.get_fulfillment_reconciliation(recommendation_id)

    def create_operations_case(self, case_id, recommendation_id, requester_ref, safe_summary):
        now = time.time()
        with self.engine.begin() as conn:
            reconciliation = conn.execute(select(FULFILLMENT_RECONCILIATIONS.c.status).where(
                FULFILLMENT_RECONCILIATIONS.c.recommendation_id == recommendation_id
            ).with_for_update()).first()
            existing = conn.execute(select(OPERATIONS_CASES).where(
                OPERATIONS_CASES.c.recommendation_id == recommendation_id
            )).mappings().first()
            if existing:
                return dict(existing), "already_requested"
            if not reconciliation or reconciliation[0] != "mismatch":
                return None, "mismatch_required"
            conn.execute(insert(OPERATIONS_CASES).values(
                case_id=case_id,
                recommendation_id=recommendation_id,
                status="draft",
                safe_summary=safe_summary,
                requested_by_ref=requester_ref,
                requested_at=now,
                attempt_count=0,
            ))
        return self.get_operations_case(case_id), "requested"

    def approve_operations_case(self, case_id, approver_ref):
        now = time.time()
        with self.engine.begin() as conn:
            row = conn.execute(select(OPERATIONS_CASES).where(
                OPERATIONS_CASES.c.case_id == case_id
            ).with_for_update()).mappings().first()
            if not row:
                return None, "not_found"
            row = dict(row)
            if row["requested_by_ref"] == approver_ref:
                return row, "four_eyes_required"
            if row["status"] != "draft":
                return row, "already_decided"
            conn.execute(update(OPERATIONS_CASES).where(
                OPERATIONS_CASES.c.case_id == case_id
            ).values(
                status="approved", approved_by_ref=approver_ref,
                approved_at=now, next_action_at=now,
            ))
            row.update(status="approved", approved_by_ref=approver_ref, approved_at=now, next_action_at=now)
            return row, "approved"

    def claim_operations_case_submission(self, case_id, processing_timeout_seconds=60):
        now = time.time()
        with self.engine.begin() as conn:
            row = conn.execute(
                select(OPERATIONS_CASES, FULFILLMENT_RECONCILIATIONS.c.fulfillment_reference)
                .join(FULFILLMENT_RECONCILIATIONS, FULFILLMENT_RECONCILIATIONS.c.recommendation_id == OPERATIONS_CASES.c.recommendation_id)
                .where(OPERATIONS_CASES.c.case_id == case_id)
                .with_for_update()
            ).mappings().first()
            if not row:
                return None, "not_found"
            row = dict(row)
            stale = row["status"] == "submitting" and now - float(row.get("action_started_at") or 0) >= processing_timeout_seconds
            if row["status"] == "submitting" and not stale:
                return row, "in_progress"
            if row["status"] not in {"approved", "submission_retry"} and not stale:
                return row, "invalid_state"
            conn.execute(update(OPERATIONS_CASES).where(
                OPERATIONS_CASES.c.case_id == case_id
            ).values(
                status="submitting", action_started_at=now,
                attempt_count=OPERATIONS_CASES.c.attempt_count + 1,
                last_error_code=None,
            ))
            row.update(status="submitting", action_started_at=now, attempt_count=row["attempt_count"] + 1)
            return row, "claimed"

    def complete_operations_case_submission(self, case_id, provider_status, external_reference, response_digest, sync_interval_seconds=300):
        now = time.time()
        next_action_at = now + sync_interval_seconds if provider_status in {"open", "in_progress"} else None
        with self.engine.begin() as conn:
            result = conn.execute(update(OPERATIONS_CASES).where(and_(
                OPERATIONS_CASES.c.case_id == case_id,
                OPERATIONS_CASES.c.status == "submitting",
            )).values(
                status=provider_status,
                provider_status=provider_status,
                external_case_reference=external_reference,
                provider_response_digest=response_digest,
                action_started_at=None,
                last_synced_at=now,
                next_action_at=next_action_at,
                last_error_code=None,
            ))
            if result.rowcount != 1:
                return None
        return self.get_operations_case(case_id)

    def fail_operations_case_action(self, case_id, action, error_code, retry_seconds=60):
        now = time.time()
        expected_status = "submitting" if action == "submit" else "syncing"
        retry_status = "submission_retry" if action == "submit" else "sync_retry"
        with self.engine.begin() as conn:
            result = conn.execute(update(OPERATIONS_CASES).where(and_(
                OPERATIONS_CASES.c.case_id == case_id,
                OPERATIONS_CASES.c.status == expected_status,
            )).values(
                status=retry_status, action_started_at=None,
                next_action_at=now + retry_seconds, last_error_code=error_code,
            ))
            return result.rowcount == 1

    def claim_operations_case_sync(self, case_id, processing_timeout_seconds=60):
        now = time.time()
        with self.engine.begin() as conn:
            row = conn.execute(select(OPERATIONS_CASES).where(
                OPERATIONS_CASES.c.case_id == case_id
            ).with_for_update()).mappings().first()
            if not row:
                return None, "not_found"
            row = dict(row)
            stale = row["status"] == "syncing" and now - float(row.get("action_started_at") or 0) >= processing_timeout_seconds
            if row["status"] == "syncing" and not stale:
                return row, "in_progress"
            if row["status"] not in {"open", "in_progress", "sync_retry"} and not stale:
                return row, "invalid_state"
            if not row.get("external_case_reference"):
                return row, "missing_reference"
            conn.execute(update(OPERATIONS_CASES).where(
                OPERATIONS_CASES.c.case_id == case_id
            ).values(
                status="syncing", action_started_at=now,
                attempt_count=OPERATIONS_CASES.c.attempt_count + 1,
                last_error_code=None,
            ))
            row.update(status="syncing", action_started_at=now, attempt_count=row["attempt_count"] + 1)
            return row, "claimed"

    def complete_operations_case_sync(self, case_id, provider_status, response_digest, sync_interval_seconds=300):
        now = time.time()
        next_action_at = now + sync_interval_seconds if provider_status in {"open", "in_progress"} else None
        with self.engine.begin() as conn:
            result = conn.execute(update(OPERATIONS_CASES).where(and_(
                OPERATIONS_CASES.c.case_id == case_id,
                OPERATIONS_CASES.c.status == "syncing",
            )).values(
                status=provider_status,
                provider_status=provider_status,
                provider_response_digest=response_digest,
                action_started_at=None,
                last_synced_at=now,
                next_action_at=next_action_at,
                last_error_code=None,
            ))
            if result.rowcount != 1:
                return None
        return self.get_operations_case(case_id)

    def get_operations_case(self, case_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(OPERATIONS_CASES).where(
                OPERATIONS_CASES.c.case_id == case_id
            )).mappings().first()
            return dict(row) if row else None

    def list_operations_cases(self, case_status=None, limit=100):
        statement = select(OPERATIONS_CASES)
        if case_status:
            statement = statement.where(OPERATIONS_CASES.c.status == case_status)
        statement = statement.order_by(OPERATIONS_CASES.c.requested_at).limit(limit)
        with self.engine.connect() as conn:
            return self._rows(conn.execute(statement))

    def list_due_operations_case_actions(self, limit=25, processing_timeout_seconds=60):
        now = time.time()
        submit_states = ["approved", "submission_retry"]
        sync_states = ["open", "in_progress", "sync_retry"]
        due = or_(
            and_(OPERATIONS_CASES.c.status.in_(submit_states + sync_states), func.coalesce(OPERATIONS_CASES.c.next_action_at, 0) <= now),
            and_(OPERATIONS_CASES.c.status.in_(["submitting", "syncing"]), func.coalesce(OPERATIONS_CASES.c.action_started_at, 0) <= now - processing_timeout_seconds),
        )
        action = case(
            (OPERATIONS_CASES.c.status.in_(submit_states + ["submitting"]), "submit"),
            else_="sync",
        ).label("action")
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(OPERATIONS_CASES.c.case_id, action)
                .where(due)
                .order_by(func.coalesce(OPERATIONS_CASES.c.next_action_at, OPERATIONS_CASES.c.requested_at))
                .limit(limit)
            ).all()
            return [{"case_id": row[0], "action": row[1]} for row in rows]

    def _lock_rollout_scope(self, conn, scope_type, scope_value):
        if self.engine.dialect.name == "postgresql":
            conn.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:scope_key))"),
                {"scope_key": f"{scope_type}:{scope_value}"},
            )

    def request_rollout_control(self, control_id, scope_type, scope_value, mode, cohort_percentage, reason, requester_ref):
        now = time.time()
        with self.engine.begin() as conn:
            self._lock_rollout_scope(conn, scope_type, scope_value)
            existing = conn.execute(select(ROLLOUT_CONTROLS).where(and_(
                ROLLOUT_CONTROLS.c.scope_type == scope_type,
                ROLLOUT_CONTROLS.c.scope_value == scope_value,
                ROLLOUT_CONTROLS.c.status == "pending",
            ))).mappings().first()
            if existing:
                return dict(existing), "already_pending"
            conn.execute(insert(ROLLOUT_CONTROLS).values(
                control_id=control_id,
                scope_type=scope_type,
                scope_value=scope_value,
                mode=mode,
                cohort_percentage=cohort_percentage,
                status="pending",
                reason=reason,
                requested_by_ref=requester_ref,
                requested_at=now,
            ))
        return self.get_rollout_control(control_id), "requested"

    def decide_rollout_control(self, control_id, decider_ref, decision):
        now = time.time()
        with self.engine.begin() as conn:
            row = conn.execute(select(ROLLOUT_CONTROLS).where(
                ROLLOUT_CONTROLS.c.control_id == control_id
            )).mappings().first()
            if not row:
                return None, "not_found"
            row = dict(row)
            self._lock_rollout_scope(conn, row["scope_type"], row["scope_value"])
            row = conn.execute(select(ROLLOUT_CONTROLS).where(
                ROLLOUT_CONTROLS.c.control_id == control_id
            ).with_for_update()).mappings().first()
            row = dict(row)
            if row["requested_by_ref"] == decider_ref:
                return row, "four_eyes_required"
            if row["status"] != "pending":
                return row, "already_decided"
            if decision == "approved":
                conn.execute(update(ROLLOUT_CONTROLS).where(and_(
                    ROLLOUT_CONTROLS.c.scope_type == row["scope_type"],
                    ROLLOUT_CONTROLS.c.scope_value == row["scope_value"],
                    ROLLOUT_CONTROLS.c.status == "active",
                )).values(status="superseded"))
                conn.execute(update(ROLLOUT_CONTROLS).where(
                    ROLLOUT_CONTROLS.c.control_id == control_id
                ).values(
                    status="active", decided_by_ref=decider_ref,
                    decided_at=now, effective_at=now,
                ))
                outcome = "approved"
                row.update(status="active", decided_by_ref=decider_ref, decided_at=now, effective_at=now)
            else:
                conn.execute(update(ROLLOUT_CONTROLS).where(
                    ROLLOUT_CONTROLS.c.control_id == control_id
                ).values(status="rejected", decided_by_ref=decider_ref, decided_at=now))
                outcome = "rejected"
                row.update(status="rejected", decided_by_ref=decider_ref, decided_at=now)
            return row, outcome

    def emergency_disable_rollout_scope(self, control_id, scope_type, scope_value, reason, actor_ref):
        now = time.time()
        with self.engine.begin() as conn:
            self._lock_rollout_scope(conn, scope_type, scope_value)
            conn.execute(update(ROLLOUT_CONTROLS).where(and_(
                ROLLOUT_CONTROLS.c.scope_type == scope_type,
                ROLLOUT_CONTROLS.c.scope_value == scope_value,
                ROLLOUT_CONTROLS.c.status.in_(["active", "pending"]),
            )).values(
                status="superseded",
                decided_by_ref=func.coalesce(ROLLOUT_CONTROLS.c.decided_by_ref, actor_ref),
                decided_at=func.coalesce(ROLLOUT_CONTROLS.c.decided_at, now),
            ))
            conn.execute(insert(ROLLOUT_CONTROLS).values(
                control_id=control_id,
                scope_type=scope_type,
                scope_value=scope_value,
                mode="disabled",
                cohort_percentage=0,
                status="active",
                reason=reason,
                requested_by_ref=actor_ref,
                requested_at=now,
                decided_by_ref=actor_ref,
                decided_at=now,
                effective_at=now,
            ))
        return self.get_rollout_control(control_id)

    def get_rollout_control(self, control_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(ROLLOUT_CONTROLS).where(
                ROLLOUT_CONTROLS.c.control_id == control_id
            )).mappings().first()
            return dict(row) if row else None

    def list_rollout_controls(self, control_status=None, limit=200):
        statement = select(ROLLOUT_CONTROLS)
        if control_status:
            statement = statement.where(ROLLOUT_CONTROLS.c.status == control_status)
        statement = statement.order_by(ROLLOUT_CONTROLS.c.requested_at.desc()).limit(limit)
        with self.engine.connect() as conn:
            return self._rows(conn.execute(statement))

    def get_active_rollout_controls(self):
        return self.list_rollout_controls("active", 1000)

    def _lock_governed_artifact_type(self, conn, artifact_type):
        if self.engine.dialect.name == "postgresql":
            conn.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:artifact_key))"),
                {"artifact_key": f"governed-artifact:{artifact_type}"},
            )

    def request_governed_artifact(
        self, artifact_id, artifact_type, version, content_digest, envelope,
        signature, signing_key_id, requester_ref,
    ):
        now = time.time()
        with self.engine.begin() as conn:
            self._lock_governed_artifact_type(conn, artifact_type)
            version_row = conn.execute(select(GOVERNED_ARTIFACTS).where(and_(
                GOVERNED_ARTIFACTS.c.artifact_type == artifact_type,
                GOVERNED_ARTIFACTS.c.version == version,
            ))).mappings().first()
            if version_row:
                return dict(version_row), "already_exists"
            pending = conn.execute(select(GOVERNED_ARTIFACTS).where(and_(
                GOVERNED_ARTIFACTS.c.artifact_type == artifact_type,
                GOVERNED_ARTIFACTS.c.status.in_(["pending", "materializing"]),
            ))).mappings().first()
            if pending:
                return dict(pending), "already_pending"
            conn.execute(insert(GOVERNED_ARTIFACTS).values(
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                version=version,
                content_digest=content_digest,
                envelope_json=envelope,
                signature=signature,
                signing_key_id=signing_key_id,
                status="pending",
                requested_by_ref=requester_ref,
                requested_at=now,
            ))
        return self.get_governed_artifact(artifact_id), "requested"

    def decide_governed_artifact(self, artifact_id, decider_ref, decision):
        now = time.time()
        with self.engine.begin() as conn:
            initial = conn.execute(select(GOVERNED_ARTIFACTS).where(
                GOVERNED_ARTIFACTS.c.artifact_id == artifact_id
            )).mappings().first()
            if not initial:
                return None, "not_found"
            self._lock_governed_artifact_type(conn, initial["artifact_type"])
            row = conn.execute(select(GOVERNED_ARTIFACTS).where(
                GOVERNED_ARTIFACTS.c.artifact_id == artifact_id
            ).with_for_update()).mappings().first()
            row = dict(row)
            if row["requested_by_ref"] == decider_ref:
                return row, "four_eyes_required"
            if row["status"] != "pending":
                return row, "already_decided"
            if decision == "approved":
                conn.execute(update(GOVERNED_ARTIFACTS).where(and_(
                    GOVERNED_ARTIFACTS.c.artifact_type == row["artifact_type"],
                    GOVERNED_ARTIFACTS.c.status == "active",
                )).values(status="superseded"))
                conn.execute(update(GOVERNED_ARTIFACTS).where(
                    GOVERNED_ARTIFACTS.c.artifact_id == artifact_id
                ).values(
                    status="active", decided_by_ref=decider_ref,
                    decided_at=now, effective_at=now,
                ))
                outcome = "approved"
                row.update(status="active", decided_by_ref=decider_ref, decided_at=now, effective_at=now)
            else:
                conn.execute(update(GOVERNED_ARTIFACTS).where(
                    GOVERNED_ARTIFACTS.c.artifact_id == artifact_id
                ).values(status="rejected", decided_by_ref=decider_ref, decided_at=now))
                outcome = "rejected"
                row.update(status="rejected", decided_by_ref=decider_ref, decided_at=now)
            return row, outcome

    def claim_governed_artifact_activation(self, artifact_id, decider_ref, processing_timeout_seconds=60):
        now = time.time()
        with self.engine.begin() as conn:
            initial = conn.execute(select(GOVERNED_ARTIFACTS).where(
                GOVERNED_ARTIFACTS.c.artifact_id == artifact_id
            )).mappings().first()
            if not initial:
                return None, "not_found"
            self._lock_governed_artifact_type(conn, initial["artifact_type"])
            row = conn.execute(select(GOVERNED_ARTIFACTS).where(
                GOVERNED_ARTIFACTS.c.artifact_id == artifact_id
            ).with_for_update()).mappings().first()
            row = dict(row)
            if row["requested_by_ref"] == decider_ref:
                return row, "four_eyes_required"
            if row["status"] == "materializing":
                if (row.get("decided_at") or 0) > now - processing_timeout_seconds:
                    return row, "materialization_in_progress"
            elif row["status"] != "pending":
                return row, "already_decided"
            conn.execute(update(GOVERNED_ARTIFACTS).where(and_(
                GOVERNED_ARTIFACTS.c.artifact_id == artifact_id,
                GOVERNED_ARTIFACTS.c.status.in_(["pending", "materializing"]),
            )).values(status="materializing", decided_by_ref=decider_ref, decided_at=now))
            row.update(status="materializing", decided_by_ref=decider_ref, decided_at=now)
            return row, "claimed"

    def complete_governed_artifact_activation(self, artifact_id, decider_ref):
        now = time.time()
        with self.engine.begin() as conn:
            row = conn.execute(select(GOVERNED_ARTIFACTS).where(
                GOVERNED_ARTIFACTS.c.artifact_id == artifact_id
            )).mappings().first()
            if not row:
                return None, "claim_lost"
            self._lock_governed_artifact_type(conn, row["artifact_type"])
            row = conn.execute(select(GOVERNED_ARTIFACTS).where(
                GOVERNED_ARTIFACTS.c.artifact_id == artifact_id
            ).with_for_update()).mappings().first()
            row = dict(row)
            if row["status"] != "materializing" or row["decided_by_ref"] != decider_ref:
                return row, "claim_lost"
            conn.execute(update(GOVERNED_ARTIFACTS).where(and_(
                GOVERNED_ARTIFACTS.c.artifact_type == row["artifact_type"],
                GOVERNED_ARTIFACTS.c.status == "active",
            )).values(status="superseded"))
            conn.execute(update(GOVERNED_ARTIFACTS).where(and_(
                GOVERNED_ARTIFACTS.c.artifact_id == artifact_id,
                GOVERNED_ARTIFACTS.c.status == "materializing",
                GOVERNED_ARTIFACTS.c.decided_by_ref == decider_ref,
            )).values(status="active", decided_at=now, effective_at=now))
            row.update(status="active", decided_at=now, effective_at=now)
            return row, "approved"

    def abandon_governed_artifact_activation(self, artifact_id, decider_ref):
        with self.engine.begin() as conn:
            result = conn.execute(update(GOVERNED_ARTIFACTS).where(and_(
                GOVERNED_ARTIFACTS.c.artifact_id == artifact_id,
                GOVERNED_ARTIFACTS.c.status == "materializing",
                GOVERNED_ARTIFACTS.c.decided_by_ref == decider_ref,
            )).values(status="pending", decided_by_ref=None, decided_at=None))
            return result.rowcount == 1

    def get_governed_artifact(self, artifact_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(GOVERNED_ARTIFACTS).where(
                GOVERNED_ARTIFACTS.c.artifact_id == artifact_id
            )).mappings().first()
            return dict(row) if row else None

    def list_governed_artifacts(self, artifact_status=None, artifact_type=None, limit=200):
        statement = select(GOVERNED_ARTIFACTS)
        if artifact_status:
            statement = statement.where(GOVERNED_ARTIFACTS.c.status == artifact_status)
        if artifact_type:
            statement = statement.where(GOVERNED_ARTIFACTS.c.artifact_type == artifact_type)
        statement = statement.order_by(GOVERNED_ARTIFACTS.c.requested_at.desc()).limit(limit)
        with self.engine.connect() as conn:
            return self._rows(conn.execute(statement))

    def get_active_governed_artifact(self, artifact_type):
        rows = self.list_governed_artifacts("active", artifact_type, 1)
        return rows[0] if rows else None

    def get_recommendation_monitoring_context(self, recommendation_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(
                RECOMMENDATIONS.c.recommendation_id,
                RECOMMENDATIONS.c.customer_id,
                RECOMMENDATIONS.c.product_id,
                RECOMMENDATIONS.c.status,
                RECOMMENDATIONS.c.created_at,
                RECOMMENDATIONS.c.evidence_json,
            ).where(
                RECOMMENDATIONS.c.recommendation_id == recommendation_id
            )).mappings().first()
            if not row:
                return None
            result = dict(row)
            result["evidence"] = result.pop("evidence_json") or {}
            return result

    def record_recommendation_outcome(
        self, observation_id, source_event_ref, recommendation_id, outcome_type,
        source_system, impact_score, evidence_digest, occurred_at,
    ):
        values = {
            "observation_id": observation_id,
            "source_event_ref": source_event_ref,
            "recommendation_id": recommendation_id,
            "outcome_type": outcome_type,
            "source_system": source_system,
            "impact_score": impact_score,
            "evidence_digest": evidence_digest,
            "occurred_at": occurred_at,
            "recorded_at": time.time(),
        }
        statement = self._dialect_insert(RECOMMENDATION_OUTCOMES).values(**values)
        statement = statement.on_conflict_do_nothing(
            index_elements=[RECOMMENDATION_OUTCOMES.c.source_event_ref]
        )
        with self.engine.begin() as conn:
            inserted = conn.execute(statement).rowcount == 1
            row = conn.execute(select(RECOMMENDATION_OUTCOMES).where(
                RECOMMENDATION_OUTCOMES.c.source_event_ref == source_event_ref
            )).mappings().one()
            return dict(row), "recorded" if inserted else "replay"

    def list_monitoring_records(self, since):
        join = RECOMMENDATIONS.outerjoin(
            RECOMMENDATION_OUTCOMES,
            and_(
                RECOMMENDATION_OUTCOMES.c.recommendation_id == RECOMMENDATIONS.c.recommendation_id,
                RECOMMENDATION_OUTCOMES.c.occurred_at >= since,
            ),
        )
        statement = select(
            RECOMMENDATIONS.c.recommendation_id,
            RECOMMENDATIONS.c.product_id,
            RECOMMENDATIONS.c.status,
            RECOMMENDATIONS.c.created_at,
            RECOMMENDATIONS.c.evidence_json,
            RECOMMENDATION_OUTCOMES.c.observation_id,
            RECOMMENDATION_OUTCOMES.c.outcome_type,
            RECOMMENDATION_OUTCOMES.c.source_system,
            RECOMMENDATION_OUTCOMES.c.impact_score,
            RECOMMENDATION_OUTCOMES.c.occurred_at,
        ).select_from(join).where(
            RECOMMENDATIONS.c.created_at >= since
        ).order_by(
            RECOMMENDATIONS.c.created_at,
            RECOMMENDATIONS.c.recommendation_id,
            RECOMMENDATION_OUTCOMES.c.occurred_at,
        )
        with self.engine.connect() as conn:
            rows = []
            for raw in conn.execute(statement).mappings():
                item = dict(raw)
                item["evidence"] = item.pop("evidence_json") or {}
                rows.append(item)
            return rows

    def get_customer_outcomes(self, customer_id):
        statement = select(
            RECOMMENDATION_OUTCOMES.c.observation_id,
            RECOMMENDATION_OUTCOMES.c.recommendation_id,
            RECOMMENDATION_OUTCOMES.c.outcome_type,
            RECOMMENDATION_OUTCOMES.c.source_system,
            RECOMMENDATION_OUTCOMES.c.impact_score,
            RECOMMENDATION_OUTCOMES.c.occurred_at,
            RECOMMENDATION_OUTCOMES.c.recorded_at,
        ).select_from(RECOMMENDATION_OUTCOMES.join(RECOMMENDATIONS)).where(
            RECOMMENDATIONS.c.customer_id == customer_id
        ).order_by(RECOMMENDATION_OUTCOMES.c.occurred_at)
        with self.engine.connect() as conn:
            return self._rows(conn.execute(statement))

    @staticmethod
    def _public_recommendation(row, budget=None):
        return {
            "recommendation_id": row["recommendation_id"],
            "status": row["status"],
            "product_id": row["product_id"],
            # Retain synthetic pricing in the database for governed review and
            # audit evidence, but never customer-present it as a live SBI rate.
            "interest_rate": None,
            "risk_tier": row["risk_tier"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "presented_at": row.get("presented_at"),
            "evidence": row.get("evidence_json") or {},
            "nudge_budget": budget,
        }

    def present_recommendation(self, recommendation_id, customer_id, max_allowed=2, cycle_days=14):
        now = time.time()
        with self.engine.begin() as conn:
            row = conn.execute(select(RECOMMENDATIONS).where(and_(
                RECOMMENDATIONS.c.recommendation_id == recommendation_id,
                RECOMMENDATIONS.c.customer_id == customer_id,
            )).with_for_update()).mappings().first()
            if not row:
                return None, "not_found"
            row = dict(row)
            if row["expires_at"] <= now and row["status"] != "authorized":
                conn.execute(update(RECOMMENDATIONS).where(RECOMMENDATIONS.c.recommendation_id == recommendation_id).values(status="expired"))
                return None, "expired"
            if row["status"] == "pending_review":
                return None, "review_required"
            if row["status"] == "rejected":
                return None, "review_rejected"
            if row["status"] == "authorized":
                return self._public_recommendation(row), "already_authorized"
            if row["status"] == "presented":
                return self._public_recommendation(row), "already_presented"
            if row["status"] != "approved":
                return None, "invalid_state"

            seed = self._dialect_insert(NUDGE_BUDGETS).values(
                customer_id=customer_id, cycle_start=str(now), nudge_count=0, max_allowed=max_allowed,
            ).on_conflict_do_nothing(index_elements=[NUDGE_BUDGETS.c.customer_id])
            conn.execute(seed)
            budget_row = conn.execute(select(NUDGE_BUDGETS).where(NUDGE_BUDGETS.c.customer_id == customer_id).with_for_update()).mappings().first()
            if now - float(budget_row["cycle_start"]) >= cycle_days * 86400:
                cycle_start, used, stored_max = now, 0, max_allowed
            else:
                cycle_start, used, stored_max = float(budget_row["cycle_start"]), int(budget_row["nudge_count"]), int(budget_row["max_allowed"])
            if used >= stored_max:
                return None, "budget_exceeded"
            used += 1
            conn.execute(update(NUDGE_BUDGETS).where(NUDGE_BUDGETS.c.customer_id == customer_id).values(
                cycle_start=str(cycle_start), nudge_count=used, max_allowed=stored_max,
            ))
            conn.execute(update(RECOMMENDATIONS).where(and_(
                RECOMMENDATIONS.c.recommendation_id == recommendation_id,
                RECOMMENDATIONS.c.status == "approved",
            )).values(status="presented", presented_at=now))
            row.update(status="presented", presented_at=now)
            budget = {
                "allowed": True, "used": used, "max_allowed": stored_max,
                "remaining": stored_max - used,
                "cycle_start": datetime.fromtimestamp(cycle_start, timezone.utc).isoformat(),
            }
            return self._public_recommendation(row, budget), "presented"

    def create_human_review(self, review_id, recommendation_id, customer_id, reason, evidence=None):
        with self.engine.begin() as conn:
            conn.execute(insert(HUMAN_REVIEWS).values(
                review_id=review_id,
                recommendation_id=recommendation_id,
                customer_id=customer_id,
                status="pending",
                reason=reason,
                created_at=time.time(),
                evidence_json=evidence or {},
            ))

    def list_human_reviews(self, status="pending", limit=100):
        with self.engine.connect() as conn:
            return self._rows(conn.execute(
                select(
                    HUMAN_REVIEWS.c.review_id,
                    HUMAN_REVIEWS.c.recommendation_id,
                    HUMAN_REVIEWS.c.status,
                    HUMAN_REVIEWS.c.reason,
                    HUMAN_REVIEWS.c.reviewer_subject,
                    HUMAN_REVIEWS.c.created_at,
                    HUMAN_REVIEWS.c.decided_at,
                    HUMAN_REVIEWS.c.evidence_json.label("evidence"),
                ).where(HUMAN_REVIEWS.c.status == status).order_by(HUMAN_REVIEWS.c.created_at).limit(limit)
            ))

    def decide_human_review(self, review_id, decision, reviewer_subject, reason=None):
        with self.engine.begin() as conn:
            row = conn.execute(select(HUMAN_REVIEWS).where(HUMAN_REVIEWS.c.review_id == review_id).with_for_update()).mappings().first()
            if not row:
                return None, "not_found"
            row = dict(row)
            if row["status"] != "pending":
                return row, "already_decided"
            now = time.time()
            conn.execute(update(HUMAN_REVIEWS).where(HUMAN_REVIEWS.c.review_id == review_id).values(
                status=decision, reason=reason or row["reason"], reviewer_subject=reviewer_subject, decided_at=now,
            ))
            conn.execute(update(RECOMMENDATIONS).where(and_(
                RECOMMENDATIONS.c.recommendation_id == row["recommendation_id"],
                RECOMMENDATIONS.c.status == "pending_review",
            )).values(status="approved" if decision == "approved" else "rejected"))
            row.update(status=decision, reason=reason or row["reason"], reviewer_subject=reviewer_subject, decided_at=now)
            return row, "decided"

    def append_integrity_record(self, builder):
        if self.engine.dialect.name == "sqlite":
            with self.engine.connect() as conn:
                conn.exec_driver_sql("BEGIN IMMEDIATE")
                try:
                    row = conn.execute(select(AUDIT_LEDGER.c.record_hash).order_by(AUDIT_LEDGER.c.sequence.desc()).limit(1)).first()
                    record = builder(row[0] if row else None)
                    result = conn.execute(insert(AUDIT_LEDGER).values(**record))
                    conn.commit()
                    return {**record, "sequence": result.inserted_primary_key[0]}
                except Exception:
                    conn.rollback()
                    raise
        with self.engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(1935763721)"))
            row = conn.execute(select(AUDIT_LEDGER.c.record_hash).order_by(AUDIT_LEDGER.c.sequence.desc()).limit(1)).first()
            record = builder(row[0] if row else None)
            result = conn.execute(insert(AUDIT_LEDGER).values(**record))
            return {**record, "sequence": result.inserted_primary_key[0]}

    def get_integrity_records(self):
        with self.engine.connect() as conn:
            return self._rows(conn.execute(select(AUDIT_LEDGER).order_by(AUDIT_LEDGER.c.sequence)))

    def record_processed_event(self, event_id, event_type, customer_ref, payload_digest, consumer_name):
        statement = self._dialect_insert(EVENT_PROCESSING_RECEIPTS).values(
            event_id=event_id,
            event_type=event_type,
            customer_ref=customer_ref,
            payload_digest=payload_digest,
            consumer_name=consumer_name,
            processed_at=time.time(),
        ).on_conflict_do_nothing(index_elements=[EVENT_PROCESSING_RECEIPTS.c.event_id])
        with self.engine.begin() as conn:
            return conn.execute(statement).rowcount == 1

    def get_processed_event(self, event_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(EVENT_PROCESSING_RECEIPTS).where(
                EVENT_PROCESSING_RECEIPTS.c.event_id == event_id
            )).mappings().first()
            return dict(row) if row else None

    def get_system_metrics(self):
        with self.engine.connect() as conn:
            return {
                "audit_records": conn.execute(select(func.count()).select_from(AUDIT_LOGS)).scalar_one(),
                "active_consents": conn.execute(select(func.count()).select_from(DPDP_CONSENT).where(DPDP_CONSENT.c.consent_status == 1)).scalar_one(),
                "pending_recommendations": conn.execute(select(func.count()).select_from(RECOMMENDATIONS).where(RECOMMENDATIONS.c.status.in_(["pending_review", "approved", "presented"]))).scalar_one(),
                "authorized_recommendations": conn.execute(select(func.count()).select_from(RECOMMENDATIONS).where(RECOMMENDATIONS.c.status == "authorized")).scalar_one(),
                "fulfilled_recommendations": conn.execute(select(func.count()).select_from(RECOMMENDATIONS).where(RECOMMENDATIONS.c.status == "fulfilled")).scalar_one(),
                "processed_events": conn.execute(select(func.count()).select_from(EVENT_PROCESSING_RECEIPTS)).scalar_one(),
                "reconciliation_pending": conn.execute(select(func.count()).select_from(FULFILLMENT_RECONCILIATIONS).where(
                    FULFILLMENT_RECONCILIATIONS.c.status.in_(["pending", "checking", "retry"])
                )).scalar_one(),
                "reconciliation_mismatches": conn.execute(select(func.count()).select_from(FULFILLMENT_RECONCILIATIONS).where(
                    FULFILLMENT_RECONCILIATIONS.c.status == "mismatch"
                )).scalar_one(),
                "cases_pending_approval": conn.execute(select(func.count()).select_from(OPERATIONS_CASES).where(
                    OPERATIONS_CASES.c.status == "draft"
                )).scalar_one(),
                "cases_open": conn.execute(select(func.count()).select_from(OPERATIONS_CASES).where(
                    OPERATIONS_CASES.c.status.in_(["open", "in_progress"])
                )).scalar_one(),
                "cases_retry": conn.execute(select(func.count()).select_from(OPERATIONS_CASES).where(
                    OPERATIONS_CASES.c.status.in_(["submission_retry", "sync_retry"])
                )).scalar_one(),
                "rollout_pending": conn.execute(select(func.count()).select_from(ROLLOUT_CONTROLS).where(
                    ROLLOUT_CONTROLS.c.status == "pending"
                )).scalar_one(),
                "rollout_disabled": conn.execute(select(func.count()).select_from(ROLLOUT_CONTROLS).where(and_(
                    ROLLOUT_CONTROLS.c.status == "active",
                    ROLLOUT_CONTROLS.c.mode == "disabled",
                ))).scalar_one(),
                "rollout_shadow": conn.execute(select(func.count()).select_from(ROLLOUT_CONTROLS).where(and_(
                    ROLLOUT_CONTROLS.c.status == "active",
                    or_(ROLLOUT_CONTROLS.c.mode == "shadow", ROLLOUT_CONTROLS.c.cohort_percentage < 100),
                ))).scalar_one(),
                "outcome_observations": conn.execute(select(func.count()).select_from(RECOMMENDATION_OUTCOMES)).scalar_one(),
                "harm_outcomes": conn.execute(select(func.count()).select_from(RECOMMENDATION_OUTCOMES).where(
                    RECOMMENDATION_OUTCOMES.c.outcome_type == "harm"
                )).scalar_one(),
                "complaint_outcomes": conn.execute(select(func.count()).select_from(RECOMMENDATION_OUTCOMES).where(
                    RECOMMENDATION_OUTCOMES.c.outcome_type == "complaint"
                )).scalar_one(),
                "governed_artifacts_pending": conn.execute(select(func.count()).select_from(GOVERNED_ARTIFACTS).where(
                    GOVERNED_ARTIFACTS.c.status.in_(["pending", "materializing"])
                )).scalar_one(),
                "governed_artifacts_active": conn.execute(select(func.count()).select_from(GOVERNED_ARTIFACTS).where(
                    GOVERNED_ARTIFACTS.c.status == "active"
                )).scalar_one(),
            }

    def health(self):
        try:
            with self.engine.connect() as conn:
                conn.execute(select(1)).scalar_one()
            return {"name": "database", "mode": self.engine.dialect.name, "ready": True, "detail": "connected"}
        except Exception as error:
            return {"name": "database", "mode": self.engine.dialect.name, "ready": False, "detail": type(error).__name__}

    def claim_idempotency(self, customer_id, idempotency_key, ttl_seconds=86400, processing_timeout_seconds=60):
        now = time.time()
        with self.engine.begin() as conn:
            conn.execute(delete(REQUEST_IDEMPOTENCY).where(REQUEST_IDEMPOTENCY.c.expires_at <= now))
            claim = self._dialect_insert(REQUEST_IDEMPOTENCY).values(
                customer_id=customer_id,
                idempotency_key=idempotency_key,
                state="processing",
                created_at=now,
                expires_at=now + ttl_seconds,
            ).on_conflict_do_nothing(
                index_elements=[REQUEST_IDEMPOTENCY.c.customer_id, REQUEST_IDEMPOTENCY.c.idempotency_key]
            )
            claimed = conn.execute(claim).rowcount == 1
            if claimed:
                return {"status": "claimed"}
            row = conn.execute(
                select(REQUEST_IDEMPOTENCY)
                .where(and_(
                    REQUEST_IDEMPOTENCY.c.customer_id == customer_id,
                    REQUEST_IDEMPOTENCY.c.idempotency_key == idempotency_key,
                ))
                .with_for_update()
            ).mappings().first()
            if row:
                if row["state"] == "completed":
                    return {"status": "replay", "response": row["response_json"], "http_status": row["http_status"]}
                if now - float(row["created_at"]) >= processing_timeout_seconds:
                    conn.execute(
                        update(REQUEST_IDEMPOTENCY)
                        .where(and_(
                            REQUEST_IDEMPOTENCY.c.customer_id == customer_id,
                            REQUEST_IDEMPOTENCY.c.idempotency_key == idempotency_key,
                        ))
                        .values(created_at=now, expires_at=now + ttl_seconds)
                    )
                    return {"status": "claimed"}
                return {"status": "in_progress"}
            raise RuntimeError("Idempotency conflict occurred without a persisted claim")

    def complete_idempotency(self, customer_id, idempotency_key, response, http_status):
        with self.engine.begin() as conn:
            result = conn.execute(
                update(REQUEST_IDEMPOTENCY)
                .where(and_(
                    REQUEST_IDEMPOTENCY.c.customer_id == customer_id,
                    REQUEST_IDEMPOTENCY.c.idempotency_key == idempotency_key,
                    REQUEST_IDEMPOTENCY.c.state == "processing",
                ))
                .values(state="completed", response_json=response, http_status=http_status)
            )
            if result.rowcount != 1:
                raise RuntimeError("Idempotency claim was lost before completion")

    def abandon_idempotency(self, customer_id, idempotency_key):
        with self.engine.begin() as conn:
            conn.execute(
                delete(REQUEST_IDEMPOTENCY).where(and_(
                    REQUEST_IDEMPOTENCY.c.customer_id == customer_id,
                    REQUEST_IDEMPOTENCY.c.idempotency_key == idempotency_key,
                    REQUEST_IDEMPOTENCY.c.state == "processing",
                ))
            )
