import hashlib
import hmac
import re
import time
import uuid


class OutcomeMonitoringError(ValueError):
    pass


class OutcomeMonitoringService:
    OUTCOME_TYPES = {
        "converted", "declined", "complaint", "opt_out",
        "false_positive", "benefit", "harm",
    }
    SOURCE_SYSTEMS = {"yono", "crm", "fulfillment", "complaints", "analytics"}
    DIMENSIONS = {"segment", "signal", "product"}
    DIGEST_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")

    def __init__(
        self,
        database,
        secret,
        audit_ledger=None,
        *,
        policy_id="draft-segment-outcomes-v1",
        policy_status="draft",
        minimum_sample_size=30,
        maximum_complaint_rate=0.05,
        maximum_harm_rate=0.02,
        minimum_conversion_ratio=0.80,
    ):
        self.database = database
        self.secret = secret.encode()
        self.audit_ledger = audit_ledger
        self.policy_id = policy_id
        self.policy_status = policy_status
        self.minimum_sample_size = minimum_sample_size
        self.maximum_complaint_rate = maximum_complaint_rate
        self.maximum_harm_rate = maximum_harm_rate
        self.minimum_conversion_ratio = minimum_conversion_ratio

    def _source_event_ref(self, source_event_id):
        return hmac.new(
            self.secret,
            f"outcome-source:{source_event_id}".encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _public_observation(row):
        return {
            key: row.get(key)
            for key in (
                "observation_id", "recommendation_id", "outcome_type",
                "source_system", "impact_score", "occurred_at", "recorded_at",
            )
        }

    def record(
        self,
        recommendation_id,
        source_event_id,
        outcome_type,
        source_system,
        evidence_digest,
        occurred_at,
        impact_score=None,
    ):
        if outcome_type not in self.OUTCOME_TYPES:
            raise OutcomeMonitoringError("invalid_outcome_type")
        if source_system not in self.SOURCE_SYSTEMS:
            raise OutcomeMonitoringError("invalid_source_system")
        if not self.DIGEST_PATTERN.fullmatch(evidence_digest or ""):
            raise OutcomeMonitoringError("invalid_evidence_digest")
        if not isinstance(occurred_at, (int, float)):
            raise OutcomeMonitoringError("invalid_occurred_at")
        if impact_score is not None and not -1 <= impact_score <= 1:
            raise OutcomeMonitoringError("invalid_impact_score")
        if outcome_type == "benefit" and impact_score is not None and impact_score < 0:
            raise OutcomeMonitoringError("benefit_impact_must_be_non_negative")
        if outcome_type == "harm" and impact_score is not None and impact_score > 0:
            raise OutcomeMonitoringError("harm_impact_must_be_non_positive")

        context = self.database.get_recommendation_monitoring_context(recommendation_id)
        if not context:
            return {"status": "not_found", "observation": None}
        now = time.time()
        if occurred_at < context["created_at"] or occurred_at > now + 300:
            raise OutcomeMonitoringError("outcome_time_outside_recommendation_lifecycle")

        source_event_ref = self._source_event_ref(source_event_id)
        observation, result_status = self.database.record_recommendation_outcome(
            str(uuid.uuid4()), source_event_ref, recommendation_id, outcome_type,
            source_system, impact_score, evidence_digest.lower(), occurred_at,
        )
        if result_status == "replay":
            expected = {
                "recommendation_id": recommendation_id,
                "outcome_type": outcome_type,
                "source_system": source_system,
                "impact_score": impact_score,
                "evidence_digest": evidence_digest.lower(),
                "occurred_at": occurred_at,
            }
            if any(observation.get(key) != value for key, value in expected.items()):
                return {"status": "idempotency_conflict", "observation": None}
        elif self.audit_ledger:
            self.audit_ledger.append(context["customer_id"], "recommendation_outcome_recorded", {
                "observation_id": observation["observation_id"],
                "recommendation_id": recommendation_id,
                "outcome_type": outcome_type,
                "source_system": source_system,
                "evidence_digest": evidence_digest.lower(),
            })
        return {
            "status": result_status,
            "observation": self._public_observation(observation),
        }

    def report(self, window_days=30, dimension="segment"):
        if dimension not in self.DIMENSIONS:
            raise OutcomeMonitoringError("invalid_dimension")
        if not isinstance(window_days, int) or not 1 <= window_days <= 365:
            raise OutcomeMonitoringError("invalid_window_days")
        since = time.time() - window_days * 86400
        records = self.database.list_monitoring_records(since)
        groups = {}
        for row in records:
            evidence = row.get("evidence") or {}
            dimension_value = {
                "segment": evidence.get("customer_segment"),
                "signal": evidence.get("signal_category"),
                "product": row.get("product_id"),
            }[dimension] or "unknown"
            group = groups.setdefault(dimension_value, {
                "recommendation_ids": set(),
                **{outcome: set() for outcome in self.OUTCOME_TYPES},
            })
            recommendation_id = row["recommendation_id"]
            group["recommendation_ids"].add(recommendation_id)
            if row.get("outcome_type"):
                group[row["outcome_type"]].add(recommendation_id)

        public_groups = []
        for name in sorted(groups):
            group = groups[name]
            total = len(group["recommendation_ids"])
            counts = {outcome: len(group[outcome]) for outcome in sorted(self.OUTCOME_TYPES)}
            rates = {
                f"{outcome}_rate": round(count / total, 6) if total else 0.0
                for outcome, count in counts.items()
            }
            public_groups.append({
                "group": name,
                "recommendations": total,
                "outcome_counts": counts,
                "rates": rates,
                "net_benefit_rate": round(
                    (counts["benefit"] - counts["harm"]) / total, 6,
                ) if total else 0.0,
            })

        alerts = []
        eligible = [
            group for group in public_groups
            if group["recommendations"] >= self.minimum_sample_size
        ]
        for group in eligible:
            if group["rates"]["complaint_rate"] > self.maximum_complaint_rate:
                alerts.append(self._alert("complaint_rate", group, self.maximum_complaint_rate))
            if group["rates"]["harm_rate"] > self.maximum_harm_rate:
                alerts.append(self._alert("harm_rate", group, self.maximum_harm_rate))
        if eligible:
            best_conversion = max(group["rates"]["converted_rate"] for group in eligible)
            if best_conversion > 0:
                for group in eligible:
                    ratio = group["rates"]["converted_rate"] / best_conversion
                    if ratio < self.minimum_conversion_ratio:
                        alerts.append({
                            "alert_type": "conversion_disparity",
                            "group": group["group"],
                            "observed": round(ratio, 6),
                            "threshold": self.minimum_conversion_ratio,
                            "severity": "review",
                        })

        return {
            "policy_id": self.policy_id,
            "policy_status": self.policy_status,
            "window_days": window_days,
            "dimension": dimension,
            "minimum_sample_size": self.minimum_sample_size,
            "groups": public_groups,
            "alerts": alerts,
            "limitations": [
                "Operational segment monitoring is not protected-class analysis.",
                "No protected attribute is inferred or accepted by this service.",
                "Causal benefit and harm require SBI-approved outcome definitions and source feeds.",
            ],
        }

    @staticmethod
    def _alert(alert_type, group, threshold):
        return {
            "alert_type": alert_type,
            "group": group["group"],
            "observed": group["rates"][alert_type],
            "threshold": threshold,
            "severity": "review",
        }
