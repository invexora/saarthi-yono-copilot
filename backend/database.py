import os
import json
import sqlite3
import time
import hmac
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# ponytail: simple SQLite DB wrapper for Enterprise Database Manager
class DatabaseManager:
    def __init__(self, db_path=None, migrations_path=None):
        configured_path = db_path or os.environ.get('SAARTHI_DB_PATH', 'saarthi.db')
        self.db_path = str(Path(configured_path).expanduser().resolve())
        self.migrations_path = Path(migrations_path or Path(__file__).with_name('migrations'))
        self._run_migrations()

    def _run_migrations(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at REAL NOT NULL
                )
            ''')
            applied = {row[0] for row in conn.execute('SELECT version FROM schema_migrations')}
            migration_files = sorted(self.migrations_path.glob('*.sql'))
            if not migration_files:
                raise RuntimeError(f'No database migrations found in {self.migrations_path}')

            for migration in migration_files:
                version = migration.stem
                if version in applied:
                    continue
                escaped_version = version.replace("'", "''")
                migration_sql = migration.read_text()
                try:
                    conn.executescript(
                        "BEGIN IMMEDIATE;\n"
                        f"{migration_sql}\n"
                        "INSERT INTO schema_migrations (version, applied_at) "
                        f"VALUES ('{escaped_version}', {time.time()});\n"
                        "COMMIT;"
                    )
                except Exception:
                    if conn.in_transaction:
                        conn.rollback()
                    raise

    def get_applied_migrations(self):
        with sqlite3.connect(self.db_path) as conn:
            return [row[0] for row in conn.execute('SELECT version FROM schema_migrations ORDER BY version')]

    def log_audit_event(self, customer_id, signal, recommended_product_id, decision_token, risk_tier, delivery_mode, compliance_status, execution_time_ms):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO audit_logs (timestamp, customer_id, signal, recommended_product_id, decision_token, risk_tier, delivery_mode, compliance_status, execution_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (str(time.time()), customer_id, signal, recommended_product_id, decision_token, risk_tier, delivery_mode, compliance_status, execution_time_ms))
            conn.commit()

    def get_audit_logs(self, customer_id=None, limit=50):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if customer_id:
                cursor.execute('SELECT * FROM audit_logs WHERE customer_id = ? ORDER BY timestamp DESC LIMIT ?', (customer_id, limit))
            else:
                cursor.execute('SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_consent_status(self, customer_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM dpdp_consent WHERE customer_id = ?', (customer_id,))
            return [dict(row) for row in cursor.fetchall()]

    def update_consent(self, customer_id, purpose, granted):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO dpdp_consent (customer_id, purpose, consent_status, updated_at, consent_version, erasure_requested)
                VALUES (?, ?, ?, ?, '1.0', 0)
                ON CONFLICT(customer_id, purpose) DO UPDATE SET
                consent_status=excluded.consent_status,
                updated_at=excluded.updated_at,
                erasure_requested=0
            ''', (customer_id, purpose, 1 if granted else 0, str(time.time())))
            conn.commit()

    def revoke_consent(self, customer_id, purpose=None):
        """Revoke processing permission without conflating revocation with erasure."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            now = str(time.time())
            if purpose:
                cursor.execute('''
                    UPDATE dpdp_consent
                    SET consent_status = 0, updated_at = ?
                    WHERE customer_id = ? AND purpose = ?
                ''', (now, customer_id, purpose))
            else:
                cursor.execute('''
                    UPDATE dpdp_consent
                    SET consent_status = 0, updated_at = ?
                    WHERE customer_id = ?
                ''', (now, customer_id))
            conn.commit()
            return cursor.rowcount

    def process_erasure_request(self, customer_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM audit_logs WHERE customer_id = ?', (customer_id,))
            cursor.execute('''
                UPDATE dpdp_consent
                SET consent_status = 0, updated_at = ?, erasure_requested = 1
                WHERE customer_id = ?
            ''', (str(time.time()), customer_id))
            if cursor.rowcount == 0:
                cursor.execute('''
                    INSERT INTO dpdp_consent (
                        customer_id, purpose, consent_status, updated_at,
                        consent_version, erasure_requested
                    ) VALUES (?, 'personalization', 0, ?, '1.0', 1)
                ''', (customer_id, str(time.time())))
            cursor.execute('DELETE FROM nudge_budgets WHERE customer_id = ?', (customer_id,))
            cursor.execute('DELETE FROM human_reviews WHERE customer_id = ?', (customer_id,))
            cursor.execute('''
                DELETE FROM operations_cases WHERE recommendation_id IN (
                    SELECT recommendation_id FROM recommendations WHERE customer_id = ?
                )
            ''', (customer_id,))
            cursor.execute('''
                DELETE FROM recommendation_outcomes WHERE recommendation_id IN (
                    SELECT recommendation_id FROM recommendations WHERE customer_id = ?
                )
            ''', (customer_id,))
            cursor.execute('''
                DELETE FROM fulfillment_reconciliations WHERE recommendation_id IN (
                    SELECT recommendation_id FROM recommendations WHERE customer_id = ?
                )
            ''', (customer_id,))
            cursor.execute('DELETE FROM recommendations WHERE customer_id = ?', (customer_id,))
            cursor.execute('DELETE FROM request_idempotency WHERE customer_id = ?', (customer_id,))
            conn.commit()

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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT cycle_start, nudge_count, max_allowed FROM nudge_budgets WHERE customer_id = ?', (customer_id,))
            row = cursor.fetchone()
            if not row:
                return {
                    "allowed": True,
                    "used": 0,
                    "max_allowed": max_allowed,
                    "remaining": max_allowed,
                    "cycle_start": None,
                }

            cycle_start, count, stored_max = row
            if now - float(cycle_start) >= cycle_days * 86400:
                count = 0
            return {
                "allowed": count < stored_max,
                "used": count,
                "max_allowed": stored_max,
                "remaining": max(0, stored_max - count),
                "cycle_start": datetime.fromtimestamp(float(cycle_start), timezone.utc).isoformat(),
            }

    def consume_nudge_budget(self, customer_id, max_allowed=2, cycle_days=14):
        """Atomically reserve one promotional nudge in the current engagement cycle."""
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.execute('BEGIN IMMEDIATE')
            cursor = conn.cursor()
            cursor.execute('SELECT cycle_start, nudge_count, max_allowed FROM nudge_budgets WHERE customer_id = ?', (customer_id,))
            row = cursor.fetchone()

            if not row or now - float(row[0]) >= cycle_days * 86400:
                cycle_start = now
                used = 0
                stored_max = max_allowed
            else:
                cycle_start = float(row[0])
                used = int(row[1])
                stored_max = int(row[2])

            if used >= stored_max:
                conn.commit()
                return {
                    "allowed": False,
                    "used": used,
                    "max_allowed": stored_max,
                    "remaining": 0,
                    "cycle_start": datetime.fromtimestamp(cycle_start, timezone.utc).isoformat(),
                }

            used += 1
            cursor.execute('''
                INSERT INTO nudge_budgets (customer_id, cycle_start, nudge_count, max_allowed)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(customer_id) DO UPDATE SET
                    cycle_start=excluded.cycle_start,
                    nudge_count=excluded.nudge_count,
                    max_allowed=excluded.max_allowed
            ''', (customer_id, str(cycle_start), used, stored_max))
            conn.commit()
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
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO recommendations (
                    recommendation_id, created_at, expires_at, customer_id,
                    product_id, interest_rate, risk_tier, status, evidence_json, presented_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                recommendation_id, now, now + ttl_seconds, customer_id, product_id,
                interest_rate, risk_tier, initial_status,
                json.dumps(evidence or {}, separators=(",", ":")),
                now if initial_status == "presented" else None,
            ))
            conn.commit()

    def authorize_recommendation(self, recommendation_id, customer_id, decision_token):
        now = time.time()
        decision_token_hash = hashlib.sha256(decision_token.encode()).hexdigest()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('''
                SELECT * FROM recommendations
                WHERE recommendation_id = ? AND customer_id = ?
            ''', (recommendation_id, customer_id)).fetchone()
            if not row:
                conn.commit()
                return None, "not_found"
            if row["status"] != "presented":
                conn.commit()
                if row["status"] == "pending_review":
                    return dict(row), "review_required"
                if row["status"] == "approved":
                    return dict(row), "offer_not_presented"
                if row["status"] == "rejected":
                    return dict(row), "review_rejected"
                return dict(row), "already_authorized"
            if row["expires_at"] <= now:
                conn.execute("UPDATE recommendations SET status='expired' WHERE recommendation_id = ?", (recommendation_id,))
                conn.commit()
                return dict(row), "expired"

            conn.execute('''
                UPDATE recommendations
                SET status='authorized', decision_token=?, authorized_at=?
                WHERE recommendation_id=? AND status='presented'
            ''', (decision_token_hash, now, recommendation_id))
            conn.commit()
            authorized = dict(row)
            authorized.update({"status": "authorized", "decision_token": decision_token_hash, "authorized_at": now})
            return authorized, "authorized"

    def recommendation_belongs_to_customer(self, recommendation_id, customer_id):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                'SELECT 1 FROM recommendations WHERE recommendation_id=? AND customer_id=?',
                (recommendation_id, customer_id),
            ).fetchone() is not None

    def get_recommendation_context(self, recommendation_id, customer_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('''
                SELECT recommendation_id, customer_id, product_id, risk_tier,
                       status, evidence_json
                FROM recommendations
                WHERE recommendation_id=? AND customer_id=?
            ''', (recommendation_id, customer_id)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["evidence"] = json.loads(result.pop("evidence_json") or "{}")
            return result

    def claim_execution(self, recommendation_id, customer_id, decision_token, token_ttl_seconds=300, processing_timeout_seconds=60):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM recommendations WHERE recommendation_id=? AND customer_id=?',
                               (recommendation_id, customer_id)).fetchone()
            if not row:
                conn.commit()
                return None, "not_found"
            row = dict(row)
            stored_token_hash = row.get("decision_token") or ""
            supplied_token_hash = hashlib.sha256((decision_token or "").encode()).hexdigest()
            token_matches = hmac.compare_digest(stored_token_hash, supplied_token_hash)
            legacy_token_matches = bool(decision_token) and hmac.compare_digest(stored_token_hash, decision_token)
            if not decision_token or not (token_matches or legacy_token_matches):
                conn.commit()
                return None, "invalid_token"
            if legacy_token_matches:
                conn.execute("UPDATE recommendations SET decision_token=? WHERE recommendation_id=?", (supplied_token_hash, recommendation_id))
                row["decision_token"] = supplied_token_hash
            if row["status"] == "fulfilled":
                row["fulfillment_response"] = json.loads(row.get("fulfillment_response_json") or "{}")
                conn.commit()
                return row, "already_fulfilled"
            if row["status"] == "executing":
                if now - float(row.get("execution_started_at") or 0) < processing_timeout_seconds:
                    conn.commit()
                    return None, "in_progress"
            elif row["status"] != "authorized":
                conn.commit()
                return None, "not_authorized"
            if now - float(row.get("authorized_at") or 0) > token_ttl_seconds:
                conn.commit()
                return None, "token_expired"
            conn.execute("UPDATE recommendations SET status='executing', execution_started_at=? WHERE recommendation_id=?", (now, recommendation_id))
            conn.commit()
            row.update(status="executing", execution_started_at=now)
            return row, "claimed"

    def complete_execution(self, recommendation_id, customer_id, result):
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE recommendations SET status='fulfilled', fulfillment_reference=?, fulfilled_at=?, fulfillment_response_json=?
                WHERE recommendation_id=? AND customer_id=? AND status='executing'
            ''', (result["reference"], now, json.dumps(result, separators=(",", ":")), recommendation_id, customer_id))
            if cursor.rowcount != 1:
                conn.rollback()
                raise RuntimeError("Execution claim was lost before completion")
            conn.execute('''
                INSERT OR IGNORE INTO fulfillment_reconciliations (
                    recommendation_id, fulfillment_reference, status, provider_status,
                    attempt_count, created_at, next_check_at
                ) VALUES (?, ?, 'pending', 'unknown', 0, ?, ?)
            ''', (recommendation_id, result["reference"], now, now))
            conn.commit()

    def abandon_execution(self, recommendation_id, customer_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE recommendations SET status='authorized', execution_started_at=NULL
                WHERE recommendation_id=? AND customer_id=? AND status='executing'
            ''', (recommendation_id, customer_id))
            conn.commit()

    def claim_fulfillment_reconciliation(self, recommendation_id, processing_timeout_seconds=60):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('''
                SELECT r.*, f.customer_id, f.status AS local_status
                FROM fulfillment_reconciliations r
                JOIN recommendations f ON f.recommendation_id = r.recommendation_id
                WHERE r.recommendation_id = ?
            ''', (recommendation_id,)).fetchone()
            if not row:
                conn.commit()
                return None, "not_found"
            row = dict(row)
            if row["status"] == "matched":
                conn.commit()
                return row, "already_matched"
            if row["status"] == "checking" and now - float(row["checking_started_at"] or 0) < processing_timeout_seconds:
                conn.commit()
                return None, "in_progress"
            conn.execute('''
                UPDATE fulfillment_reconciliations
                SET status='checking', checking_started_at=?, attempt_count=attempt_count+1,
                    last_error_code=NULL
                WHERE recommendation_id=?
            ''', (now, recommendation_id))
            conn.commit()
            row.update(status="checking", checking_started_at=now, attempt_count=row["attempt_count"] + 1)
            return row, "claimed"

    def complete_fulfillment_reconciliation(self, recommendation_id, provider_status, provider_reference, provider_response_digest, retry_seconds=60):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute(
                'SELECT * FROM fulfillment_reconciliations WHERE recommendation_id=?',
                (recommendation_id,),
            ).fetchone()
            if not row or row["status"] != "checking":
                conn.commit()
                return None, "claim_lost"
            if provider_status == "completed" and provider_reference == row["fulfillment_reference"]:
                outcome = "matched"
                next_check_at = None
            elif provider_status in {"pending", "processing"}:
                outcome = "retry"
                next_check_at = now + retry_seconds
            else:
                outcome = "mismatch"
                next_check_at = None
            conn.execute('''
                UPDATE fulfillment_reconciliations
                SET status=?, provider_status=?, checking_started_at=NULL,
                    last_checked_at=?, next_check_at=?, provider_response_digest=?,
                    last_error_code=NULL
                WHERE recommendation_id=? AND status='checking'
            ''', (outcome, provider_status, now, next_check_at, provider_response_digest, recommendation_id))
            conn.commit()
            result = dict(row)
            result.update(
                status=outcome, provider_status=provider_status, checking_started_at=None,
                last_checked_at=now, next_check_at=next_check_at,
                provider_response_digest=provider_response_digest, last_error_code=None,
            )
            return result, outcome

    def fail_fulfillment_reconciliation(self, recommendation_id, error_code, retry_seconds=60):
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE fulfillment_reconciliations
                SET status='retry', checking_started_at=NULL, last_checked_at=?,
                    next_check_at=?, last_error_code=?
                WHERE recommendation_id=? AND status='checking'
            ''', (now, now + retry_seconds, error_code, recommendation_id))
            conn.commit()
            return cursor.rowcount == 1

    def list_fulfillment_reconciliations(self, reconciliation_status=None, limit=100):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if reconciliation_status:
                rows = conn.execute('''
                    SELECT * FROM fulfillment_reconciliations
                    WHERE status=? ORDER BY created_at LIMIT ?
                ''', (reconciliation_status, limit)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM fulfillment_reconciliations
                    ORDER BY created_at LIMIT ?
                ''', (limit,)).fetchall()
            return [dict(row) for row in rows]

    def get_fulfillment_reconciliation(self, recommendation_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                'SELECT * FROM fulfillment_reconciliations WHERE recommendation_id=?',
                (recommendation_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_due_fulfillment_reconciliations(self, limit=25, processing_timeout_seconds=60):
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            return [row[0] for row in conn.execute('''
                SELECT recommendation_id FROM fulfillment_reconciliations
                WHERE (status IN ('pending', 'retry') AND COALESCE(next_check_at, 0) <= ?)
                   OR (status = 'checking' AND COALESCE(checking_started_at, 0) <= ?)
                ORDER BY COALESCE(next_check_at, created_at), created_at
                LIMIT ?
            ''', (now, now - processing_timeout_seconds, limit)).fetchall()]

    def acknowledge_fulfillment_mismatch(self, recommendation_id, operator_ref, note):
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE fulfillment_reconciliations
                SET acknowledged_at=?, acknowledged_by=?, acknowledgement_note=?
                WHERE recommendation_id=? AND status='mismatch'
            ''', (now, operator_ref, note, recommendation_id))
            conn.commit()
            if cursor.rowcount != 1:
                return None
            return self.get_fulfillment_reconciliation(recommendation_id)

    def create_operations_case(self, case_id, recommendation_id, requester_ref, safe_summary):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            existing = conn.execute(
                'SELECT * FROM operations_cases WHERE recommendation_id=?',
                (recommendation_id,),
            ).fetchone()
            if existing:
                conn.commit()
                return dict(existing), "already_requested"
            reconciliation = conn.execute(
                'SELECT status FROM fulfillment_reconciliations WHERE recommendation_id=?',
                (recommendation_id,),
            ).fetchone()
            if not reconciliation or reconciliation["status"] != "mismatch":
                conn.commit()
                return None, "mismatch_required"
            conn.execute('''
                INSERT INTO operations_cases (
                    case_id, recommendation_id, status, safe_summary,
                    requested_by_ref, requested_at, attempt_count
                ) VALUES (?, ?, 'draft', ?, ?, ?, 0)
            ''', (case_id, recommendation_id, safe_summary, requester_ref, now))
            conn.commit()
            return self.get_operations_case(case_id), "requested"

    def approve_operations_case(self, case_id, approver_ref):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute(
                'SELECT * FROM operations_cases WHERE case_id=?', (case_id,),
            ).fetchone()
            if not row:
                conn.commit()
                return None, "not_found"
            row = dict(row)
            if row["requested_by_ref"] == approver_ref:
                conn.commit()
                return row, "four_eyes_required"
            if row["status"] != "draft":
                conn.commit()
                return row, "already_decided"
            conn.execute('''
                UPDATE operations_cases
                SET status='approved', approved_by_ref=?, approved_at=?, next_action_at=?
                WHERE case_id=? AND status='draft'
            ''', (approver_ref, now, now, case_id))
            conn.commit()
            row.update(status="approved", approved_by_ref=approver_ref, approved_at=now, next_action_at=now)
            return row, "approved"

    def claim_operations_case_submission(self, case_id, processing_timeout_seconds=60):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('''
                SELECT c.*, r.fulfillment_reference
                FROM operations_cases c
                JOIN fulfillment_reconciliations r ON r.recommendation_id=c.recommendation_id
                WHERE c.case_id=?
            ''', (case_id,)).fetchone()
            if not row:
                conn.commit()
                return None, "not_found"
            row = dict(row)
            stale_submission = row["status"] == "submitting" and now - float(row["action_started_at"] or 0) >= processing_timeout_seconds
            if row["status"] == "submitting" and not stale_submission:
                conn.commit()
                return row, "in_progress"
            if row["status"] not in {"approved", "submission_retry"} and not stale_submission:
                conn.commit()
                return row, "invalid_state"
            conn.execute('''
                UPDATE operations_cases SET status='submitting', action_started_at=?,
                    attempt_count=attempt_count+1, last_error_code=NULL
                WHERE case_id=?
            ''', (now, case_id))
            conn.commit()
            row.update(status="submitting", action_started_at=now, attempt_count=row["attempt_count"] + 1)
            return row, "claimed"

    def complete_operations_case_submission(self, case_id, provider_status, external_reference, response_digest, sync_interval_seconds=300):
        now = time.time()
        next_action_at = now + sync_interval_seconds if provider_status in {"open", "in_progress"} else None
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE operations_cases
                SET status=?, provider_status=?, external_case_reference=?,
                    provider_response_digest=?, action_started_at=NULL,
                    last_synced_at=?, next_action_at=?, last_error_code=NULL
                WHERE case_id=? AND status='submitting'
            ''', (provider_status, provider_status, external_reference, response_digest, now, next_action_at, case_id))
            conn.commit()
            return self.get_operations_case(case_id) if cursor.rowcount == 1 else None

    def fail_operations_case_action(self, case_id, action, error_code, retry_seconds=60):
        now = time.time()
        expected_status = "submitting" if action == "submit" else "syncing"
        retry_status = "submission_retry" if action == "submit" else "sync_retry"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE operations_cases
                SET status=?, action_started_at=NULL, next_action_at=?, last_error_code=?
                WHERE case_id=? AND status=?
            ''', (retry_status, now + retry_seconds, error_code, case_id, expected_status))
            conn.commit()
            return cursor.rowcount == 1

    def claim_operations_case_sync(self, case_id, processing_timeout_seconds=60):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM operations_cases WHERE case_id=?', (case_id,)).fetchone()
            if not row:
                conn.commit()
                return None, "not_found"
            row = dict(row)
            stale_sync = row["status"] == "syncing" and now - float(row["action_started_at"] or 0) >= processing_timeout_seconds
            if row["status"] == "syncing" and not stale_sync:
                conn.commit()
                return row, "in_progress"
            if row["status"] not in {"open", "in_progress", "sync_retry"} and not stale_sync:
                conn.commit()
                return row, "invalid_state"
            if not row["external_case_reference"]:
                conn.commit()
                return row, "missing_reference"
            conn.execute('''
                UPDATE operations_cases SET status='syncing', action_started_at=?,
                    attempt_count=attempt_count+1, last_error_code=NULL
                WHERE case_id=?
            ''', (now, case_id))
            conn.commit()
            row.update(status="syncing", action_started_at=now, attempt_count=row["attempt_count"] + 1)
            return row, "claimed"

    def complete_operations_case_sync(self, case_id, provider_status, response_digest, sync_interval_seconds=300):
        now = time.time()
        next_action_at = now + sync_interval_seconds if provider_status in {"open", "in_progress"} else None
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE operations_cases
                SET status=?, provider_status=?, provider_response_digest=?,
                    action_started_at=NULL, last_synced_at=?, next_action_at=?, last_error_code=NULL
                WHERE case_id=? AND status='syncing'
            ''', (provider_status, provider_status, response_digest, now, next_action_at, case_id))
            conn.commit()
            return self.get_operations_case(case_id) if cursor.rowcount == 1 else None

    def get_operations_case(self, case_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM operations_cases WHERE case_id=?', (case_id,)).fetchone()
            return dict(row) if row else None

    def list_operations_cases(self, case_status=None, limit=100):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if case_status:
                rows = conn.execute(
                    'SELECT * FROM operations_cases WHERE status=? ORDER BY requested_at LIMIT ?',
                    (case_status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    'SELECT * FROM operations_cases ORDER BY requested_at LIMIT ?', (limit,),
                ).fetchall()
            return [dict(row) for row in rows]

    def list_due_operations_case_actions(self, limit=25, processing_timeout_seconds=60):
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute('''
                SELECT case_id,
                    CASE WHEN status IN ('approved', 'submission_retry', 'submitting')
                         THEN 'submit' ELSE 'sync' END AS action
                FROM operations_cases
                WHERE (status IN ('approved', 'submission_retry', 'open', 'in_progress', 'sync_retry')
                       AND COALESCE(next_action_at, 0) <= ?)
                   OR (status IN ('submitting', 'syncing')
                       AND COALESCE(action_started_at, 0) <= ?)
                ORDER BY COALESCE(next_action_at, requested_at), requested_at
                LIMIT ?
            ''', (now, now - processing_timeout_seconds, limit)).fetchall()
            return [{"case_id": row[0], "action": row[1]} for row in rows]

    def request_rollout_control(self, control_id, scope_type, scope_value, mode, cohort_percentage, reason, requester_ref):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            existing = conn.execute('''
                SELECT * FROM rollout_controls
                WHERE scope_type=? AND scope_value=? AND status='pending'
            ''', (scope_type, scope_value)).fetchone()
            if existing:
                conn.commit()
                return dict(existing), "already_pending"
            conn.execute('''
                INSERT INTO rollout_controls (
                    control_id, scope_type, scope_value, mode, cohort_percentage,
                    status, reason, requested_by_ref, requested_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            ''', (
                control_id, scope_type, scope_value, mode, cohort_percentage,
                reason, requester_ref, now,
            ))
            conn.commit()
            return self.get_rollout_control(control_id), "requested"

    def decide_rollout_control(self, control_id, decider_ref, decision):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute(
                'SELECT * FROM rollout_controls WHERE control_id=?', (control_id,),
            ).fetchone()
            if not row:
                conn.commit()
                return None, "not_found"
            row = dict(row)
            if row["requested_by_ref"] == decider_ref:
                conn.commit()
                return row, "four_eyes_required"
            if row["status"] != "pending":
                conn.commit()
                return row, "already_decided"
            if decision == "approved":
                conn.execute('''
                    UPDATE rollout_controls SET status='superseded'
                    WHERE scope_type=? AND scope_value=? AND status='active'
                ''', (row["scope_type"], row["scope_value"]))
                conn.execute('''
                    UPDATE rollout_controls
                    SET status='active', decided_by_ref=?, decided_at=?, effective_at=?
                    WHERE control_id=? AND status='pending'
                ''', (decider_ref, now, now, control_id))
                outcome = "approved"
                row.update(status="active", decided_by_ref=decider_ref, decided_at=now, effective_at=now)
            else:
                conn.execute('''
                    UPDATE rollout_controls
                    SET status='rejected', decided_by_ref=?, decided_at=?
                    WHERE control_id=? AND status='pending'
                ''', (decider_ref, now, control_id))
                outcome = "rejected"
                row.update(status="rejected", decided_by_ref=decider_ref, decided_at=now)
            conn.commit()
            return row, outcome

    def emergency_disable_rollout_scope(self, control_id, scope_type, scope_value, reason, actor_ref):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('''
                UPDATE rollout_controls
                SET status='superseded', decided_by_ref=COALESCE(decided_by_ref, ?),
                    decided_at=COALESCE(decided_at, ?)
                WHERE scope_type=? AND scope_value=? AND status IN ('active', 'pending')
            ''', (actor_ref, now, scope_type, scope_value))
            conn.execute('''
                INSERT INTO rollout_controls (
                    control_id, scope_type, scope_value, mode, cohort_percentage,
                    status, reason, requested_by_ref, requested_at,
                    decided_by_ref, decided_at, effective_at
                ) VALUES (?, ?, ?, 'disabled', 0, 'active', ?, ?, ?, ?, ?, ?)
            ''', (
                control_id, scope_type, scope_value, reason,
                actor_ref, now, actor_ref, now, now,
            ))
            conn.commit()
            return self.get_rollout_control(control_id)

    def get_rollout_control(self, control_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                'SELECT * FROM rollout_controls WHERE control_id=?', (control_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_rollout_controls(self, control_status=None, limit=200):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if control_status:
                rows = conn.execute('''
                    SELECT * FROM rollout_controls WHERE status=?
                    ORDER BY requested_at DESC LIMIT ?
                ''', (control_status, limit)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM rollout_controls
                    ORDER BY requested_at DESC LIMIT ?
                ''', (limit,)).fetchall()
            return [dict(row) for row in rows]

    def get_active_rollout_controls(self):
        return self.list_rollout_controls("active", 1000)

    def request_governed_artifact(
        self, artifact_id, artifact_type, version, content_digest, envelope,
        signature, signing_key_id, requester_ref,
    ):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            version_row = conn.execute('''
                SELECT * FROM governed_artifacts
                WHERE artifact_type=? AND version=?
            ''', (artifact_type, version)).fetchone()
            if version_row:
                conn.commit()
                return dict(version_row), "already_exists"
            pending = conn.execute('''
                SELECT * FROM governed_artifacts
                WHERE artifact_type=? AND status IN ('pending', 'materializing')
            ''', (artifact_type,)).fetchone()
            if pending:
                conn.commit()
                return dict(pending), "already_pending"
            conn.execute('''
                INSERT INTO governed_artifacts (
                    artifact_id, artifact_type, version, content_digest,
                    envelope_json, signature, signing_key_id, status,
                    requested_by_ref, requested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            ''', (
                artifact_id, artifact_type, version, content_digest,
                json.dumps(envelope, sort_keys=True, separators=(",", ":")),
                signature, signing_key_id, requester_ref, now,
            ))
            conn.commit()
            return self.get_governed_artifact(artifact_id), "requested"

    def decide_governed_artifact(self, artifact_id, decider_ref, decision):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute(
                'SELECT * FROM governed_artifacts WHERE artifact_id=?', (artifact_id,),
            ).fetchone()
            if not row:
                conn.commit()
                return None, "not_found"
            row = dict(row)
            if row["requested_by_ref"] == decider_ref:
                conn.commit()
                return row, "four_eyes_required"
            if row["status"] != "pending":
                conn.commit()
                return row, "already_decided"
            if decision == "approved":
                conn.execute('''
                    UPDATE governed_artifacts SET status='superseded'
                    WHERE artifact_type=? AND status='active'
                ''', (row["artifact_type"],))
                conn.execute('''
                    UPDATE governed_artifacts
                    SET status='active', decided_by_ref=?, decided_at=?, effective_at=?
                    WHERE artifact_id=? AND status='pending'
                ''', (decider_ref, now, now, artifact_id))
                outcome = "approved"
                row.update(status="active", decided_by_ref=decider_ref, decided_at=now, effective_at=now)
            else:
                conn.execute('''
                    UPDATE governed_artifacts
                    SET status='rejected', decided_by_ref=?, decided_at=?
                    WHERE artifact_id=? AND status='pending'
                ''', (decider_ref, now, artifact_id))
                outcome = "rejected"
                row.update(status="rejected", decided_by_ref=decider_ref, decided_at=now)
            conn.commit()
            return row, outcome

    def claim_governed_artifact_activation(self, artifact_id, decider_ref, processing_timeout_seconds=60):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute(
                'SELECT * FROM governed_artifacts WHERE artifact_id=?', (artifact_id,),
            ).fetchone()
            if not row:
                conn.commit()
                return None, "not_found"
            row = dict(row)
            if row["requested_by_ref"] == decider_ref:
                conn.commit()
                return row, "four_eyes_required"
            if row["status"] == "materializing":
                if (row.get("decided_at") or 0) > now - processing_timeout_seconds:
                    conn.commit()
                    return row, "materialization_in_progress"
            elif row["status"] != "pending":
                conn.commit()
                return row, "already_decided"
            conn.execute('''
                UPDATE governed_artifacts
                SET status='materializing', decided_by_ref=?, decided_at=?
                WHERE artifact_id=? AND status IN ('pending', 'materializing')
            ''', (decider_ref, now, artifact_id))
            conn.commit()
            row.update(status="materializing", decided_by_ref=decider_ref, decided_at=now)
            return row, "claimed"

    def complete_governed_artifact_activation(self, artifact_id, decider_ref):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute(
                'SELECT * FROM governed_artifacts WHERE artifact_id=?', (artifact_id,),
            ).fetchone()
            if not row or row["status"] != "materializing" or row["decided_by_ref"] != decider_ref:
                conn.commit()
                return dict(row) if row else None, "claim_lost"
            conn.execute('''
                UPDATE governed_artifacts SET status='superseded'
                WHERE artifact_type=? AND status='active'
            ''', (row["artifact_type"],))
            conn.execute('''
                UPDATE governed_artifacts
                SET status='active', decided_at=?, effective_at=?
                WHERE artifact_id=? AND status='materializing' AND decided_by_ref=?
            ''', (now, now, artifact_id, decider_ref))
            conn.commit()
            result = dict(row)
            result.update(status="active", decided_at=now, effective_at=now)
            return result, "approved"

    def abandon_governed_artifact_activation(self, artifact_id, decider_ref):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE governed_artifacts
                SET status='pending', decided_by_ref=NULL, decided_at=NULL
                WHERE artifact_id=? AND status='materializing' AND decided_by_ref=?
            ''', (artifact_id, decider_ref))
            conn.commit()
            return cursor.rowcount == 1

    def get_governed_artifact(self, artifact_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                'SELECT * FROM governed_artifacts WHERE artifact_id=?', (artifact_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_governed_artifacts(self, artifact_status=None, artifact_type=None, limit=200):
        clauses, parameters = [], []
        if artifact_status:
            clauses.append("status=?")
            parameters.append(artifact_status)
        if artifact_type:
            clauses.append("artifact_type=?")
            parameters.append(artifact_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM governed_artifacts {where} ORDER BY requested_at DESC LIMIT ?",
                (*parameters, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_active_governed_artifact(self, artifact_type):
        rows = self.list_governed_artifacts("active", artifact_type, 1)
        return rows[0] if rows else None

    def get_recommendation_monitoring_context(self, recommendation_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('''
                SELECT recommendation_id, customer_id, product_id, status,
                       created_at, evidence_json
                FROM recommendations WHERE recommendation_id=?
            ''', (recommendation_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["evidence"] = json.loads(result.pop("evidence_json") or "{}")
            return result

    def record_recommendation_outcome(
        self, observation_id, source_event_ref, recommendation_id, outcome_type,
        source_system, impact_score, evidence_digest, occurred_at,
    ):
        recorded_at = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            cursor = conn.execute('''
                INSERT OR IGNORE INTO recommendation_outcomes (
                    observation_id, source_event_ref, recommendation_id, outcome_type,
                    source_system, impact_score, evidence_digest, occurred_at, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                observation_id, source_event_ref, recommendation_id, outcome_type,
                source_system, impact_score, evidence_digest, occurred_at, recorded_at,
            ))
            row = conn.execute(
                'SELECT * FROM recommendation_outcomes WHERE source_event_ref=?',
                (source_event_ref,),
            ).fetchone()
            conn.commit()
            return dict(row), "recorded" if cursor.rowcount == 1 else "replay"

    def list_monitoring_records(self, since):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT r.recommendation_id, r.product_id, r.status, r.created_at,
                       r.evidence_json, o.observation_id, o.outcome_type,
                       o.source_system, o.impact_score, o.occurred_at
                FROM recommendations r
                LEFT JOIN recommendation_outcomes o
                  ON o.recommendation_id=r.recommendation_id AND o.occurred_at>=?
                WHERE r.created_at>=?
                ORDER BY r.created_at, r.recommendation_id, o.occurred_at
            ''', (since, since)).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["evidence"] = json.loads(item.pop("evidence_json") or "{}")
                result.append(item)
            return result

    def get_customer_outcomes(self, customer_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT o.observation_id, o.recommendation_id, o.outcome_type,
                       o.source_system, o.impact_score, o.occurred_at, o.recorded_at
                FROM recommendation_outcomes o
                JOIN recommendations r ON r.recommendation_id=o.recommendation_id
                WHERE r.customer_id=? ORDER BY o.occurred_at
            ''', (customer_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def _public_recommendation(row, budget=None):
        item = dict(row)
        evidence = json.loads(item.pop("evidence_json") or "{}")
        return {
            "recommendation_id": item["recommendation_id"],
            "status": item["status"],
            "product_id": item["product_id"],
            # Retain synthetic pricing in the database for governed review and
            # audit evidence, but never customer-present it as a live SBI rate.
            "interest_rate": None,
            "risk_tier": item["risk_tier"],
            "created_at": item["created_at"],
            "expires_at": item["expires_at"],
            "presented_at": item.get("presented_at"),
            "evidence": evidence,
            "nudge_budget": budget,
        }

    def present_recommendation(self, recommendation_id, customer_id, max_allowed=2, cycle_days=14):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM recommendations WHERE recommendation_id=? AND customer_id=?',
                               (recommendation_id, customer_id)).fetchone()
            if not row:
                conn.commit()
                return None, "not_found"
            if row["expires_at"] <= now and row["status"] != "authorized":
                conn.execute("UPDATE recommendations SET status='expired' WHERE recommendation_id=?", (recommendation_id,))
                conn.commit()
                return None, "expired"
            if row["status"] == "pending_review":
                conn.commit()
                return None, "review_required"
            if row["status"] == "rejected":
                conn.commit()
                return None, "review_rejected"
            if row["status"] == "authorized":
                result = self._public_recommendation(row)
                conn.commit()
                return result, "already_authorized"
            if row["status"] == "presented":
                result = self._public_recommendation(row)
                conn.commit()
                return result, "already_presented"
            if row["status"] != "approved":
                conn.commit()
                return None, "invalid_state"

            budget_row = conn.execute('SELECT cycle_start, nudge_count, max_allowed FROM nudge_budgets WHERE customer_id=?', (customer_id,)).fetchone()
            if not budget_row or now - float(budget_row[0]) >= cycle_days * 86400:
                cycle_start, used, stored_max = now, 0, max_allowed
            else:
                cycle_start, used, stored_max = float(budget_row[0]), int(budget_row[1]), int(budget_row[2])
            if used >= stored_max:
                conn.commit()
                return None, "budget_exceeded"
            used += 1
            conn.execute('''
                INSERT INTO nudge_budgets (customer_id, cycle_start, nudge_count, max_allowed)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(customer_id) DO UPDATE SET cycle_start=excluded.cycle_start, nudge_count=excluded.nudge_count, max_allowed=excluded.max_allowed
            ''', (customer_id, str(cycle_start), used, stored_max))
            conn.execute("UPDATE recommendations SET status='presented', presented_at=? WHERE recommendation_id=? AND status='approved'", (now, recommendation_id))
            updated = dict(row)
            updated.update(status="presented", presented_at=now)
            budget = {
                "allowed": True, "used": used, "max_allowed": stored_max,
                "remaining": stored_max - used,
                "cycle_start": datetime.fromtimestamp(cycle_start, timezone.utc).isoformat(),
            }
            conn.commit()
            return self._public_recommendation(updated, budget), "presented"

    def create_human_review(self, review_id, recommendation_id, customer_id, reason, evidence=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO human_reviews (review_id, recommendation_id, customer_id, status, reason, created_at, evidence_json)
                VALUES (?, ?, ?, 'pending', ?, ?, ?)
            ''', (review_id, recommendation_id, customer_id, reason, time.time(), json.dumps(evidence or {}, separators=(",", ":"))))
            conn.commit()

    def list_human_reviews(self, status="pending", limit=100):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT review_id, recommendation_id, status, reason, reviewer_subject, created_at, decided_at, evidence_json
                FROM human_reviews WHERE status = ? ORDER BY created_at LIMIT ?
            ''', (status, limit)).fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["evidence"] = json.loads(item.pop("evidence_json") or "{}")
                results.append(item)
            return results

    def decide_human_review(self, review_id, decision, reviewer_subject, reason=None):
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM human_reviews WHERE review_id = ?', (review_id,)).fetchone()
            if not row:
                conn.commit()
                return None, "not_found"
            if row["status"] != "pending":
                conn.commit()
                return dict(row), "already_decided"
            new_recommendation_status = "approved" if decision == "approved" else "rejected"
            now = time.time()
            conn.execute('''UPDATE human_reviews SET status=?, reason=COALESCE(?, reason), reviewer_subject=?, decided_at=? WHERE review_id=?''',
                         (decision, reason, reviewer_subject, now, review_id))
            conn.execute('UPDATE recommendations SET status=? WHERE recommendation_id=? AND status=\'pending_review\'',
                         (new_recommendation_status, row["recommendation_id"]))
            conn.commit()
            result = dict(row)
            result.update(status=decision, reason=reason or row["reason"], reviewer_subject=reviewer_subject, decided_at=now)
            return result, "decided"

    def append_integrity_record(self, builder):
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT record_hash FROM audit_ledger ORDER BY sequence DESC LIMIT 1').fetchone()
            record = builder(row["record_hash"] if row else None)
            cursor = conn.execute('''
                INSERT INTO audit_ledger (event_id, occurred_at, customer_ref, event_type, payload_json, previous_hash, record_hash, key_version)
                VALUES (:event_id, :occurred_at, :customer_ref, :event_type, :payload_json, :previous_hash, :record_hash, :key_version)
            ''', record)
            conn.commit()
            return {**record, "sequence": cursor.lastrowid}

    def get_integrity_records(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute('SELECT * FROM audit_ledger ORDER BY sequence')]

    def record_processed_event(self, event_id, event_type, customer_ref, payload_digest, consumer_name):
        """Persist an idempotent, data-minimized receipt before stream acknowledgement."""
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            cursor = conn.execute('''
                INSERT OR IGNORE INTO event_processing_receipts (
                    event_id, event_type, customer_ref, payload_digest,
                    consumer_name, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (event_id, event_type, customer_ref, payload_digest, consumer_name, time.time()))
            conn.commit()
            return cursor.rowcount == 1

    def get_processed_event(self, event_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                'SELECT * FROM event_processing_receipts WHERE event_id = ?',
                (event_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_system_metrics(self):
        with sqlite3.connect(self.db_path) as conn:
            audit_count = conn.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]
            active_consents = conn.execute('SELECT COUNT(*) FROM dpdp_consent WHERE consent_status = 1').fetchone()[0]
            pending_recommendations = conn.execute("SELECT COUNT(*) FROM recommendations WHERE status IN ('pending_review', 'approved', 'presented')").fetchone()[0]
            authorized_recommendations = conn.execute("SELECT COUNT(*) FROM recommendations WHERE status = 'authorized'").fetchone()[0]
            fulfilled_recommendations = conn.execute("SELECT COUNT(*) FROM recommendations WHERE status = 'fulfilled'").fetchone()[0]
            processed_events = conn.execute('SELECT COUNT(*) FROM event_processing_receipts').fetchone()[0]
            reconciliation_pending = conn.execute(
                "SELECT COUNT(*) FROM fulfillment_reconciliations WHERE status IN ('pending', 'checking', 'retry')"
            ).fetchone()[0]
            reconciliation_mismatches = conn.execute(
                "SELECT COUNT(*) FROM fulfillment_reconciliations WHERE status = 'mismatch'"
            ).fetchone()[0]
            cases_pending_approval = conn.execute(
                "SELECT COUNT(*) FROM operations_cases WHERE status = 'draft'"
            ).fetchone()[0]
            cases_open = conn.execute(
                "SELECT COUNT(*) FROM operations_cases WHERE status IN ('open', 'in_progress')"
            ).fetchone()[0]
            cases_retry = conn.execute(
                "SELECT COUNT(*) FROM operations_cases WHERE status IN ('submission_retry', 'sync_retry')"
            ).fetchone()[0]
            rollout_pending = conn.execute(
                "SELECT COUNT(*) FROM rollout_controls WHERE status = 'pending'"
            ).fetchone()[0]
            rollout_disabled = conn.execute(
                "SELECT COUNT(*) FROM rollout_controls WHERE status = 'active' AND mode = 'disabled'"
            ).fetchone()[0]
            rollout_shadow = conn.execute(
                "SELECT COUNT(*) FROM rollout_controls WHERE status = 'active' AND (mode = 'shadow' OR cohort_percentage < 100)"
            ).fetchone()[0]
            outcome_observations = conn.execute(
                "SELECT COUNT(*) FROM recommendation_outcomes"
            ).fetchone()[0]
            harm_outcomes = conn.execute(
                "SELECT COUNT(*) FROM recommendation_outcomes WHERE outcome_type = 'harm'"
            ).fetchone()[0]
            complaint_outcomes = conn.execute(
                "SELECT COUNT(*) FROM recommendation_outcomes WHERE outcome_type = 'complaint'"
            ).fetchone()[0]
            governed_artifacts_pending = conn.execute(
                "SELECT COUNT(*) FROM governed_artifacts WHERE status IN ('pending', 'materializing')"
            ).fetchone()[0]
            governed_artifacts_active = conn.execute(
                "SELECT COUNT(*) FROM governed_artifacts WHERE status='active'"
            ).fetchone()[0]
            return {
                "audit_records": audit_count,
                "active_consents": active_consents,
                "pending_recommendations": pending_recommendations,
                "authorized_recommendations": authorized_recommendations,
                "fulfilled_recommendations": fulfilled_recommendations,
                "processed_events": processed_events,
                "reconciliation_pending": reconciliation_pending,
                "reconciliation_mismatches": reconciliation_mismatches,
                "cases_pending_approval": cases_pending_approval,
                "cases_open": cases_open,
                "cases_retry": cases_retry,
                "rollout_pending": rollout_pending,
                "rollout_disabled": rollout_disabled,
                "rollout_shadow": rollout_shadow,
                "outcome_observations": outcome_observations,
                "harm_outcomes": harm_outcomes,
                "complaint_outcomes": complaint_outcomes,
                "governed_artifacts_pending": governed_artifacts_pending,
                "governed_artifacts_active": governed_artifacts_active,
            }

    def health(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('SELECT 1').fetchone()
            return {"name": "database", "mode": "sqlite", "ready": True, "detail": "connected"}
        except Exception as error:
            return {"name": "database", "mode": "sqlite", "ready": False, "detail": type(error).__name__}

    def claim_idempotency(self, customer_id, idempotency_key, ttl_seconds=86400, processing_timeout_seconds=60):
        now = time.time()
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('DELETE FROM request_idempotency WHERE expires_at <= ?', (now,))
            row = conn.execute('''
                SELECT state, response_json, http_status, created_at
                FROM request_idempotency
                WHERE customer_id = ? AND idempotency_key = ?
            ''', (customer_id, idempotency_key)).fetchone()
            if row:
                if row["state"] == "completed":
                    conn.commit()
                    return {
                        "status": "replay",
                        "response": json.loads(row["response_json"]),
                        "http_status": row["http_status"],
                    }
                if now - float(row["created_at"]) >= processing_timeout_seconds:
                    conn.execute('''
                        UPDATE request_idempotency
                        SET created_at=?, expires_at=?
                        WHERE customer_id=? AND idempotency_key=?
                    ''', (now, now + ttl_seconds, customer_id, idempotency_key))
                    conn.commit()
                    return {"status": "claimed"}
                conn.commit()
                return {"status": "in_progress"}

            conn.execute('''
                INSERT INTO request_idempotency (
                    customer_id, idempotency_key, state,
                    created_at, expires_at
                ) VALUES (?, ?, 'processing', ?, ?)
            ''', (customer_id, idempotency_key, now, now + ttl_seconds))
            conn.commit()
            return {"status": "claimed"}

    def complete_idempotency(self, customer_id, idempotency_key, response, http_status):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE request_idempotency
                SET state='completed', response_json=?, http_status=?
                WHERE customer_id=? AND idempotency_key=? AND state='processing'
            ''', (
                json.dumps(response, separators=(",", ":")),
                http_status,
                customer_id,
                idempotency_key,
            ))
            conn.commit()
            if cursor.rowcount != 1:
                raise RuntimeError("Idempotency claim was lost before completion")

    def abandon_idempotency(self, customer_id, idempotency_key):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                DELETE FROM request_idempotency
                WHERE customer_id=? AND idempotency_key=? AND state='processing'
            ''', (customer_id, idempotency_key))
            conn.commit()

if __name__ == "__main__":
    db = DatabaseManager()
    db.update_consent("SBI-123", "marketing", True)
    print(db.get_consent_status("SBI-123"))
