from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class PolicyCheck:
    rule_id: str
    passed: bool
    reason_code: str
    detail: str


class DeterministicDecisionPolicy:
    """Deterministic safety envelope around probabilistic retrieval and recommendation."""

    MAX_INTEREST_RATE = 36.0
    MAX_CONTEXT_AGE_SECONDS = 86400

    def evaluate(self, state, high_risk_review_required=False):
        checks = []

        context = state.get("customer_context") or {}
        verified = context.get("verification_status") in {"verified", "synthetic_verified"}
        try:
            as_of = datetime.fromisoformat(context["as_of"].replace("Z", "+00:00"))
            fresh = 0 <= (datetime.now(timezone.utc) - as_of).total_seconds() <= self.MAX_CONTEXT_AGE_SECONDS
        except (KeyError, TypeError, ValueError):
            fresh = False
        context_valid = verified and fresh
        checks.append(PolicyCheck(
            "CUSTOMER_CONTEXT", context_valid,
            "VERIFIED_CUSTOMER_CONTEXT" if context_valid else "CUSTOMER_CONTEXT_UNVERIFIED_OR_STALE",
            "Customer decision context is verified and current." if context_valid else "A verified context no older than 24 hours is required.",
        ))

        segment_matches = context.get("customer_segment") == state.get("customer_segment")
        checks.append(PolicyCheck(
            "SEGMENT_BINDING", segment_matches,
            "SERVER_SEGMENT_BOUND" if segment_matches else "CUSTOMER_SEGMENT_MISMATCH",
            "Eligibility used the server-sourced customer segment." if segment_matches else "Requested and trusted customer segments do not match.",
        ))

        signal_evidence = state.get("signal_evidence") or {}
        signal_valid = (
            signal_evidence.get("category") == state.get("signal_category")
            and signal_evidence.get("evaluation_status") in {"approved", "demo_approved"}
            and isinstance(signal_evidence.get("confidence"), (int, float))
            and 0 <= signal_evidence.get("confidence") <= 1
            and len(signal_evidence.get("input_digest") or "") == 64
            and bool(signal_evidence.get("model_id"))
            and bool(signal_evidence.get("model_version"))
        )
        checks.append(PolicyCheck(
            "SIGNAL_PROVENANCE", signal_valid,
            "EVALUATED_SIGNAL_EVIDENCE" if signal_valid else "SIGNAL_EVIDENCE_INVALID",
            "Signal classification is versioned, evaluated, confidence-scored, and input-bound."
            if signal_valid else "Valid evaluated signal provenance is required.",
        ))

        has_product = bool(state.get("neo4j_query")) and state.get("recommended_product_id") != "NO_PRODUCT"
        checks.append(PolicyCheck(
            "PRODUCT_ELIGIBILITY", has_product, "SEGMENT_PRODUCT_ELIGIBLE" if has_product else "NO_ELIGIBLE_PRODUCT",
            "Product was resolved from the effective-dated segment and signal rule graph." if has_product else "No active product rule matched.",
        ))

        product = state.get("neo4j_query") or {}
        income = float(context.get("monthly_income") or 0)
        obligations = max(0.0, float(context.get("monthly_obligations") or 0))
        commitment = max(0.0, float(product.get("monthly_commitment") or 0))
        product_type = product.get("product_type", "service")
        threshold = float(product.get("max_dsti") or 1.0)
        if product_type == "credit":
            affordability_ratio = (obligations + commitment) / income if income > 0 else 1.0
            affordable = income > 0 and affordability_ratio <= threshold
        elif product_type in {"savings", "investment"}:
            disposable = max(0.0, income - obligations)
            affordability_ratio = commitment / disposable if disposable > 0 else 1.0
            affordable = disposable > 0 and affordability_ratio <= threshold
        else:
            affordability_ratio = 0.0
            affordable = True
        checks.append(PolicyCheck(
            "AFFORDABILITY", affordable,
            "AFFORDABILITY_WITHIN_LIMIT" if affordable else "AFFORDABILITY_LIMIT_EXCEEDED",
            f"Calculated commitment ratio {affordability_ratio:.3f} is within limit {threshold:.3f}." if affordable else f"Calculated commitment ratio {affordability_ratio:.3f} exceeds limit {threshold:.3f}.",
        ))

        evidence = state.get("policy_evidence") or {}
        policy_approved = evidence.get("approval_status") == "approved" and bool(evidence.get("content_sha256"))
        checks.append(PolicyCheck(
            "POLICY_PROVENANCE", policy_approved, "APPROVED_POLICY_EVIDENCE" if policy_approved else "POLICY_EVIDENCE_INVALID",
            "Policy evidence is approved and integrity-addressed." if policy_approved else "Approved policy provenance is required.",
        ))

        rate = state.get("interest_rate")
        rate_allowed = rate is None or float(rate) <= self.MAX_INTEREST_RATE
        checks.append(PolicyCheck(
            "RATE_CAP", rate_allowed, "RATE_WITHIN_SAFETY_CAP" if rate_allowed else "RATE_EXCEEDS_SAFETY_CAP",
            f"Interest rate is within the {self.MAX_INTEREST_RATE:.0f}% safety cap." if rate_allowed else f"Interest rate {rate}% exceeds the safety cap.",
        ))

        vulnerability_flags = set(context.get("vulnerability_flags") or [])
        vulnerable = "financial_stress" in vulnerability_flags

        if not all(check.passed for check in checks):
            outcome = "rejected"
        elif state.get("signal_category") == "stress" or vulnerable:
            outcome = "support_only"
            checks.append(PolicyCheck("VULNERABILITY_ROUTING", True, "FINANCIAL_STRESS_SUPPORT_ONLY", "Promotional action is suppressed because a stress signal or verified vulnerability marker is active."))
        elif state.get("risk_tier") == "high" and high_risk_review_required:
            outcome = "review_required"
            checks.append(PolicyCheck("HUMAN_OVERSIGHT", True, "HIGH_RISK_HUMAN_REVIEW_REQUIRED", "Independent approval is required before customer authorization."))
        else:
            outcome = "eligible"
            if state.get("risk_tier") == "high":
                checks.append(PolicyCheck("HUMAN_OVERSIGHT", True, "HIGH_RISK_REVIEW_DISABLED", "Review enforcement is disabled in this runtime configuration."))

        return {
            "outcome": outcome,
            "reason_codes": [check.reason_code for check in checks],
            "checks": [asdict(check) for check in checks],
            "policy_version": "decision-safety-envelope-2026.08.2",
            "context_summary": {
                "customer_segment": context.get("customer_segment"),
                "verification_status": context.get("verification_status"),
                "source_system": context.get("source_system"),
                "as_of": context.get("as_of"),
                "context_version": context.get("context_version"),
                "affordability_ratio": round(affordability_ratio, 6),
                "affordability_limit": threshold,
                "vulnerability_routing": vulnerable,
                "signal_model_id": signal_evidence.get("model_id"),
                "signal_model_version": signal_evidence.get("model_version"),
                "signal_confidence": signal_evidence.get("confidence"),
            },
        }
