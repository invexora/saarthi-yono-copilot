import hashlib
import hmac
import re
import uuid

from backend.guardrails import InputGuardian


class RolloutControlError(ValueError):
    pass


class RolloutControlService:
    SCOPE_TYPES = {"global", "channel", "segment", "signal", "product", "model"}
    MODES = {"active", "shadow", "disabled"}
    SEGMENTS = {"corporate", "pensioner", "sme", "stressed", "student"}
    SIGNALS = {"friction", "opportunity", "lifeevent", "stress"}
    CHANNELS = {"in_app", "push", "email", "sms", "rm"}
    VALUE_PATTERN = re.compile(r"^[A-Za-z0-9_.:/@+\-]{1,200}$")
    PUBLIC_FIELDS = (
        "control_id", "scope_type", "scope_value", "mode",
        "cohort_percentage", "status", "reason", "requested_at",
        "decided_at", "effective_at",
    )

    def __init__(self, database, secret, audit_ledger=None):
        self.database = database
        self.secret = secret.encode()
        self.audit_ledger = audit_ledger
        self.input_guardian = InputGuardian()

    @classmethod
    def _public(cls, row):
        if not row:
            return None
        return {field: row.get(field) for field in cls.PUBLIC_FIELDS}

    @classmethod
    def _validate_scope(cls, scope_type, scope_value):
        if scope_type not in cls.SCOPE_TYPES:
            raise RolloutControlError("invalid_scope_type")
        if scope_type == "global" and scope_value != "*":
            raise RolloutControlError("global_scope_value_must_be_wildcard")
        if scope_type != "global" and not cls.VALUE_PATTERN.fullmatch(scope_value or ""):
            raise RolloutControlError("invalid_scope_value")
        if scope_type == "segment" and scope_value not in cls.SEGMENTS:
            raise RolloutControlError("unknown_segment")
        if scope_type == "signal" and scope_value not in cls.SIGNALS:
            raise RolloutControlError("unknown_signal")
        if scope_type == "channel" and scope_value not in cls.CHANNELS:
            raise RolloutControlError("unknown_channel")

    def request(self, scope_type, scope_value, mode, cohort_percentage, reason, requester_ref):
        self._validate_scope(scope_type, scope_value)
        if mode not in self.MODES:
            raise RolloutControlError("invalid_mode")
        if not isinstance(cohort_percentage, int) or not 0 <= cohort_percentage <= 100:
            raise RolloutControlError("invalid_cohort_percentage")
        if mode == "disabled":
            cohort_percentage = 0
        elif mode == "shadow":
            cohort_percentage = 100
        control_id = str(uuid.uuid4())
        safe_reason = self.input_guardian.mask_pii(reason)
        control, request_status = self.database.request_rollout_control(
            control_id, scope_type, scope_value, mode, cohort_percentage,
            safe_reason, requester_ref,
        )
        if self.audit_ledger and request_status == "requested":
            self.audit_ledger.append("system:rollout-control", "rollout_control_requested", {
                "control_id": control_id,
                "scope_type": scope_type,
                "scope_value": scope_value,
                "mode": mode,
                "cohort_percentage": cohort_percentage,
                "requester_ref": requester_ref,
            })
        return {"status": request_status, "control": self._public(control)}

    def decide(self, control_id, decision, decider_ref):
        if decision not in {"approved", "rejected"}:
            raise RolloutControlError("invalid_decision")
        control, outcome = self.database.decide_rollout_control(
            control_id, decider_ref, decision,
        )
        if self.audit_ledger and outcome in {"approved", "rejected"}:
            self.audit_ledger.append("system:rollout-control", f"rollout_control_{outcome}", {
                "control_id": control_id,
                "decider_ref": decider_ref,
            })
        return {"status": outcome, "control": self._public(control)}

    def emergency_disable(self, scope_type, scope_value, reason, actor_ref):
        self._validate_scope(scope_type, scope_value)
        control_id = str(uuid.uuid4())
        safe_reason = self.input_guardian.mask_pii(reason)
        control = self.database.emergency_disable_rollout_scope(
            control_id, scope_type, scope_value, safe_reason, actor_ref,
        )
        if self.audit_ledger:
            self.audit_ledger.append("system:rollout-control", "rollout_emergency_disabled", {
                "control_id": control_id,
                "scope_type": scope_type,
                "scope_value": scope_value,
                "actor_ref": actor_ref,
            })
        return {"status": "disabled", "control": self._public(control)}

    def list(self, control_status=None, limit=200):
        return [
            self._public(row)
            for row in self.database.list_rollout_controls(control_status, limit)
        ]

    def _bucket(self, customer_id, control_id):
        digest = hmac.new(
            self.secret,
            f"customer:{customer_id}|control:{control_id}".encode(),
            hashlib.sha256,
        ).digest()
        return int.from_bytes(digest[:8], "big") % 10000

    @staticmethod
    def _matches(control, *, channel, segment, signal, product, model):
        values = {
            "global": "*",
            "channel": channel,
            "segment": segment,
            "signal": signal,
            "product": product,
            "model": model,
        }
        return values.get(control["scope_type"]) == control["scope_value"]

    def evaluate(self, customer_id, *, channel="in_app", segment=None, signal=None, product=None, model=None):
        matched = [
            control for control in self.database.get_active_rollout_controls()
            if self._matches(
                control, channel=channel, segment=segment, signal=signal, product=product,
                model=model,
            )
        ]
        disabled = [control for control in matched if control["mode"] == "disabled"]
        shadow = [control for control in matched if control["mode"] == "shadow"]
        cohort_exclusions = []
        for control in matched:
            if control["mode"] != "active":
                continue
            if self._bucket(customer_id, control["control_id"]) >= int(control["cohort_percentage"]) * 100:
                cohort_exclusions.append(control)
        if disabled:
            mode = "disabled"
            reasons = ["ROLLOUT_SCOPE_DISABLED"]
        elif shadow or cohort_exclusions:
            mode = "shadow"
            reasons = ["ROLLOUT_SHADOW_MODE" if shadow else "ROLLOUT_COHORT_EXCLUDED"]
        else:
            mode = "live"
            reasons = ["ROLLOUT_LIVE"]
        relevant = disabled or shadow or cohort_exclusions or matched
        return {
            "mode": mode,
            "reason_codes": reasons,
            "control_ids": [control["control_id"] for control in relevant],
        }

    def evaluate_recommendation(self, recommendation_id, customer_id, channel="in_app"):
        recommendation = self.database.get_recommendation_context(recommendation_id, customer_id)
        if not recommendation:
            return None, {"mode": "live", "reason_codes": ["ROLLOUT_LIVE"], "control_ids": []}
        evidence = recommendation.get("evidence") or {}
        signal_evidence = evidence.get("signal_detection") or {}
        model = None
        if signal_evidence.get("model_id") and signal_evidence.get("model_version"):
            model = f"{signal_evidence['model_id']}:{signal_evidence['model_version']}"
        return recommendation, self.evaluate(
            customer_id,
            channel=channel,
            segment=evidence.get("customer_segment") or evidence.get("decision_context", {}).get("customer_segment"),
            signal=evidence.get("signal_category"),
            product=recommendation.get("product_id"),
            model=model,
        )
