class FulfillmentService:
    def __init__(self, db, client, audit_ledger=None, consent_engine=None, rollout_control=None):
        self.db = db
        self.client = client
        self.audit_ledger = audit_ledger
        self.consent_engine = consent_engine
        self.rollout_control = rollout_control

    @staticmethod
    def _normalize_result(result):
        if not isinstance(result, dict):
            raise RuntimeError("Fulfilment response must be an object")
        reference = result.get("reference")
        if result.get("status") != "completed" or not isinstance(reference, str) or not reference or len(reference) > 200:
            raise RuntimeError("Fulfilment response did not confirm a valid completion reference")
        return {
            "status": "completed",
            "reference": reference,
            "completed_at": result.get("completed_at"),
            "provider": result.get("provider"),
        }

    def execute(self, recommendation_id, customer_id, decision_token):
        if not self.db.recommendation_belongs_to_customer(recommendation_id, customer_id):
            return {"status": "not_found", "recommendation_id": recommendation_id}
        if self.rollout_control:
            recommendation_context, rollout = self.rollout_control.evaluate_recommendation(
                recommendation_id, customer_id,
            )
            if recommendation_context and recommendation_context.get("status") != "fulfilled":
                if rollout["mode"] == "disabled":
                    if self.audit_ledger:
                        self.audit_ledger.append(customer_id, "rollout_decision_suppressed", {
                            "stage": "fulfillment",
                            "mode": "disabled",
                            "control_ids": rollout["control_ids"],
                            "recommendation_id": recommendation_id,
                        })
                    return {"status": "rollout_blocked", "recommendation_id": recommendation_id}
                if rollout["mode"] == "shadow":
                    if self.audit_ledger:
                        self.audit_ledger.append(customer_id, "rollout_decision_suppressed", {
                            "stage": "fulfillment",
                            "mode": "shadow",
                            "control_ids": rollout["control_ids"],
                            "recommendation_id": recommendation_id,
                        })
                    return {"status": "rollout_shadow", "recommendation_id": recommendation_id}
        purpose = f"execute_recommendation:{recommendation_id}"
        if self.consent_engine and not self.consent_engine.verify_purpose_consent(customer_id, purpose):
            return {"status": "consent_required", "recommendation_id": recommendation_id}
        recommendation, claim_status = self.db.claim_execution(recommendation_id, customer_id, decision_token)
        if claim_status == "already_fulfilled":
            return {"status": claim_status, "recommendation_id": recommendation_id, "fulfillment": recommendation.get("fulfillment_response")}
        if claim_status != "claimed":
            return {"status": claim_status, "recommendation_id": recommendation_id}

        try:
            result = self._normalize_result(
                self.client.execute(recommendation, customer_id, recommendation_id),
            )
            self.db.complete_execution(recommendation_id, customer_id, result)
        except Exception as error:
            self.db.abandon_execution(recommendation_id, customer_id)
            return {"status": "dependency_unavailable", "recommendation_id": recommendation_id, "error_code": type(error).__name__}

        if self.audit_ledger:
            self.audit_ledger.append(customer_id, "recommendation_fulfilled", {
                "recommendation_id": recommendation_id,
                "product_id": recommendation["product_id"],
                "fulfillment_reference": result["reference"],
            })
        return {"status": "fulfilled", "recommendation_id": recommendation_id, "fulfillment": result}
