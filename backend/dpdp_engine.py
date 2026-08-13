import time
import hashlib
import hmac
import os

try:
    from backend.database import DatabaseManager
except ImportError:
    from database import DatabaseManager

class DPDPEngine:
    def __init__(self, db=None, decision_secret=None, audit_ledger=None, rollout_control=None):
        self.db = db if db is not None else DatabaseManager()
        self.decision_secret = decision_secret or os.environ.get("SAARTHI_DECISION_SECRET", "saarthi-local-development-secret-32")
        self.audit_ledger = audit_ledger
        self.rollout_control = rollout_control

    def _rollout_gate(self, recommendation_id, customer_id):
        if not self.rollout_control:
            return None
        recommendation, evaluation = self.rollout_control.evaluate_recommendation(
            recommendation_id, customer_id,
        )
        if not recommendation:
            return None
        if evaluation["mode"] == "disabled":
            if self.audit_ledger:
                self.audit_ledger.append(customer_id, "rollout_decision_suppressed", {
                    "stage": "recommendation_access",
                    "mode": "disabled",
                    "control_ids": evaluation["control_ids"],
                    "recommendation_id": recommendation_id,
                })
            return {"status": "rollout_blocked", "recommendation": None}
        if evaluation["mode"] == "shadow":
            if self.audit_ledger:
                self.audit_ledger.append(customer_id, "rollout_decision_suppressed", {
                    "stage": "recommendation_access",
                    "mode": "shadow",
                    "control_ids": evaluation["control_ids"],
                    "recommendation_id": recommendation_id,
                })
            return {"status": "rollout_shadow", "recommendation": None}
        return None

    def verify_purpose_consent(self, customer_id, purpose):
        consents = self.db.get_consent_status(customer_id)
        for c in consents:
            if c['purpose'] == purpose and c['consent_status'] == 1:
                return True
        return False

    def grant_consent(self, customer_id, purpose):
        self.db.update_consent(customer_id, purpose, True)
        if self.audit_ledger:
            self.audit_ledger.append(customer_id, "consent_granted", {"purpose": purpose, "consent_version": "1.0"})
        return self.generate_consent_artifact(customer_id, purpose)

    def revoke_consent_and_erase(self, customer_id):
        """Remove eligible prototype data and retain the revocation tombstone."""
        if self.audit_ledger:
            self.audit_ledger.append(customer_id, "erasure_requested", {"scope": "non_regulatory_customer_data"})
        self.db.process_erasure_request(customer_id)
        return {
            "status": "processed",
            "customer_id": customer_id,
            "scope": "eligible_saarthi_derived_data",
            "retained": ["revoked_consent_tombstone", "integrity_ledger_evidence"],
        }

    def revoke_consent(self, customer_id, purpose=None):
        revoked = self.db.revoke_consent(customer_id, purpose)
        if self.audit_ledger:
            self.audit_ledger.append(customer_id, "consent_revoked", {"purpose": purpose or "all", "records_updated": revoked})
        return {
            "status": "REVOKED",
            "customer_id": customer_id,
            "purpose": purpose or "all",
            "records_updated": revoked,
        }

    def generate_data_portability_export(self, customer_id):
        return self.db.export_customer_data(customer_id)

    def generate_consent_artifact(self, customer_id, purpose):
        artifact = {
            "customer_id": customer_id,
            "purpose": purpose,
            "timestamp": str(time.time()),
            "status": "GRANTED"
        }
        token_str = f"{customer_id}|{purpose}|{artifact['timestamp']}"
        artifact["signature"] = hmac.new(self.decision_secret.encode(), token_str.encode(), hashlib.sha256).hexdigest()
        return artifact

    def authorize_recommendation(self, recommendation_id, customer_id):
        """Issue a scoped, single-use server token after explicit action consent."""
        if not self.db.recommendation_belongs_to_customer(recommendation_id, customer_id):
            return {"status": "not_found"}
        rollout_gate = self._rollout_gate(recommendation_id, customer_id)
        if rollout_gate:
            return {"status": rollout_gate["status"]}
        if not self.verify_purpose_consent(customer_id, "personalization"):
            return {"status": "consent_required"}
        issued_at = str(int(time.time()))
        payload = f"{recommendation_id}|{customer_id}|{issued_at}|EXPLICIT_ACTION_CONSENT"
        token = hmac.new(self.decision_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        recommendation, status = self.db.authorize_recommendation(recommendation_id, customer_id, token)
        if status != "authorized":
            return {"status": status}

        purpose = f"execute_recommendation:{recommendation_id}"
        consent_artifact = self.grant_consent(customer_id, purpose)
        if self.audit_ledger:
            self.audit_ledger.append(customer_id, "recommendation_authorized", {
                "recommendation_id": recommendation_id,
                "product_id": recommendation["product_id"],
            })
        return {
            "status": "authorized",
            "recommendation_id": recommendation_id,
            "customer_id": customer_id,
            "product_id": recommendation["product_id"],
            "decision_token": token,
            "consent_artifact": consent_artifact,
        }

    def decide_human_review(self, review_id, decision, reviewer_subject, reason=None):
        review, status = self.db.decide_human_review(review_id, decision, reviewer_subject, reason)
        if status == "decided" and self.audit_ledger:
            self.audit_ledger.append(review["customer_id"], "human_review_decided", {
                "review_id": review_id,
                "recommendation_id": review["recommendation_id"],
                "decision": decision,
                "reviewer_ref": self.audit_ledger.principal_ref(reviewer_subject),
            })
        if review:
            review = {key: value for key, value in review.items() if key != "customer_id"}
            evidence = review.pop("evidence_json", None)
            if evidence is not None:
                import json
                review["evidence"] = json.loads(evidence) if isinstance(evidence, str) else evidence
        return review, status

    def present_recommendation(self, recommendation_id, customer_id):
        if not self.db.recommendation_belongs_to_customer(recommendation_id, customer_id):
            return {"status": "not_found", "recommendation": None}
        rollout_gate = self._rollout_gate(recommendation_id, customer_id)
        if rollout_gate:
            return rollout_gate
        if not self.verify_purpose_consent(customer_id, "personalization"):
            return {"status": "consent_required", "recommendation": None}
        recommendation, status = self.db.present_recommendation(recommendation_id, customer_id)
        if status == "presented" and self.audit_ledger:
            self.audit_ledger.append(customer_id, "recommendation_presented", {
                "recommendation_id": recommendation_id,
                "product_id": recommendation["product_id"],
                "context_version": recommendation.get("evidence", {}).get("decision_context", {}).get("context_version"),
            })
        return {"status": status, "recommendation": recommendation}

if __name__ == "__main__":
    engine = DPDPEngine()
    print(engine.grant_consent("SBI-123", "loan_offers"))
    print(engine.verify_purpose_consent("SBI-123", "loan_offers"))
