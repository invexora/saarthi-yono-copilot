from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class Segment(str, Enum):
    corporate = "corporate"
    pensioner = "pensioner"
    sme = "sme"
    stressed = "stressed"
    student = "student"


class OrchestrationRequest(ApiModel):
    signal: str = Field(min_length=1, max_length=1000)
    details: str = Field(default="", max_length=5000)
    segment: Segment = Segment.corporate


class NudgeBudget(ApiModel):
    allowed: bool
    used: int = Field(ge=0)
    max_allowed: int = Field(ge=0)
    remaining: int = Field(ge=0)
    cycle_start: str | None = None


class OrchestrationResponse(ApiModel):
    raw_signal: str
    masked_details: str | None = None
    signal_category: str | None = None
    signal_evidence: dict[str, Any] | None = None
    recommended_product_id: str | None = None
    interest_rate: float | None = None
    risk_tier: str | None = None
    compliance_approved: bool
    compliance_logs: str | None = None
    nudge_output: str | None = None
    execution_timings: dict[str, float]
    decision_token: str | None = None
    recommendation_id: str | None = None
    delivery_mode: str
    rag_context: str | None = None
    neo4j_query: dict[str, Any] | None = None
    nudge_budget: NudgeBudget | None = None
    event_id: str | None = None
    policy_evidence: dict[str, Any] | None = None
    review_id: str | None = None
    decision_outcome: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    policy_checks: list[dict[str, Any]] = Field(default_factory=list)
    decision_context: dict[str, Any] | None = None
    customer_segment: str | None = None
    rollout_mode: str | None = None
    customer_presentation: dict[str, Any] | None = None


class ConsentRequest(ApiModel):
    purpose: Literal["personalization"]


class ConsentRecord(ApiModel):
    customer_id: str
    purpose: str
    consent_status: int
    updated_at: str
    consent_version: str
    erasure_requested: int


class ConsentArtifact(ApiModel):
    customer_id: str
    purpose: str
    timestamp: str
    status: str
    signature: str


class ConsentRevocationResponse(ApiModel):
    status: str
    customer_id: str
    purpose: str
    records_updated: int


class ErasureResponse(ApiModel):
    status: Literal["processed"]
    customer_id: str
    scope: Literal["eligible_saarthi_derived_data"]
    retained: list[Literal["revoked_consent_tombstone", "integrity_ledger_evidence"]]


class AuthorizationRequest(ApiModel):
    recommendation_id: str = Field(alias="recommendationId", min_length=10, max_length=100)


class AuthorizationResponse(ApiModel):
    status: str
    recommendation_id: str | None = None
    customer_id: str | None = None
    product_id: str | None = None
    decision_token: str | None = None
    consent_artifact: ConsentArtifact | None = None
    recommendation: dict[str, Any] | None = None


class RecommendationPresentation(ApiModel):
    recommendation_id: str
    status: str
    product_id: str
    interest_rate: float | None = None
    risk_tier: str
    created_at: float
    expires_at: float
    presented_at: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    nudge_budget: NudgeBudget | None = None


class RecommendationPresentationResponse(ApiModel):
    status: str
    recommendation: RecommendationPresentation | None = None


class ActionExecutionRequest(ApiModel):
    recommendation_id: str = Field(alias="recommendationId", min_length=10, max_length=100)
    decision_token: str = Field(alias="decisionToken", min_length=64, max_length=128)


class ActionExecutionResponse(ApiModel):
    status: str
    recommendation_id: str
    fulfillment: dict[str, Any] | None = None
    error_code: str | None = None


class FulfillmentReconciliationRecord(ApiModel):
    recommendation_id: str
    fulfillment_reference: str
    status: Literal["pending", "checking", "matched", "mismatch", "retry"]
    provider_status: str
    attempt_count: int = Field(ge=0)
    created_at: float
    last_checked_at: float | None = None
    next_check_at: float | None = None
    last_error_code: str | None = None
    acknowledged_at: float | None = None
    acknowledgement_note: str | None = None


class FulfillmentReconciliationResponse(ApiModel):
    status: str
    reconciliation: FulfillmentReconciliationRecord | None = None
    error_code: str | None = None


class ReconciliationAcknowledgementRequest(ApiModel):
    note: str = Field(min_length=10, max_length=1000)


class OperationsCaseRequest(ApiModel):
    recommendation_id: str = Field(alias="recommendationId", min_length=10, max_length=100)
    summary: str = Field(min_length=10, max_length=1000)


class OperationsCaseRecord(ApiModel):
    case_id: str
    recommendation_id: str
    status: Literal[
        "draft", "approved", "submitting", "submission_retry",
        "open", "in_progress", "syncing", "sync_retry",
        "resolved", "closed", "rejected",
    ]
    safe_summary: str
    requested_at: float
    approved_at: float | None = None
    attempt_count: int = Field(ge=0)
    external_case_reference: str | None = None
    provider_status: str | None = None
    last_synced_at: float | None = None
    next_action_at: float | None = None
    last_error_code: str | None = None


class OperationsCaseResponse(ApiModel):
    status: str
    case: OperationsCaseRecord | None = None
    error_code: str | None = None


class RolloutControlRequest(ApiModel):
    scope_type: Literal["global", "channel", "segment", "signal", "product", "model"]
    scope_value: str = Field(min_length=1, max_length=200)
    mode: Literal["active", "shadow", "disabled"]
    cohort_percentage: int = Field(default=100, ge=0, le=100)
    reason: str = Field(min_length=10, max_length=1000)


class RolloutControlDecisionRequest(ApiModel):
    decision: Literal["approved", "rejected"]


class EmergencyDisableRequest(ApiModel):
    scope_type: Literal["global", "channel", "segment", "signal", "product", "model"]
    scope_value: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=10, max_length=1000)


class RolloutControlRecord(ApiModel):
    control_id: str
    scope_type: str
    scope_value: str
    mode: Literal["active", "shadow", "disabled"]
    cohort_percentage: int = Field(ge=0, le=100)
    status: Literal["pending", "materializing", "active", "rejected", "superseded"]
    reason: str
    requested_at: float
    decided_at: float | None = None
    effective_at: float | None = None


class RolloutControlResponse(ApiModel):
    status: str
    control: RolloutControlRecord | None = None


class OutcomeObservationRequest(ApiModel):
    recommendation_id: str = Field(alias="recommendationId", min_length=10, max_length=100)
    source_event_id: str = Field(
        alias="sourceEventId", min_length=8, max_length=200,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    outcome_type: Literal[
        "converted", "declined", "complaint", "opt_out",
        "false_positive", "benefit", "harm",
    ] = Field(alias="outcomeType")
    source_system: Literal[
        "yono", "crm", "fulfillment", "complaints", "analytics",
    ] = Field(alias="sourceSystem")
    evidence_digest: str = Field(alias="evidenceDigest", pattern=r"^[0-9a-fA-F]{64}$")
    occurred_at: float = Field(alias="occurredAt", gt=0)
    impact_score: float | None = Field(default=None, alias="impactScore", ge=-1, le=1)


class OutcomeObservation(ApiModel):
    observation_id: str
    recommendation_id: str
    outcome_type: str
    source_system: str
    impact_score: float | None = None
    occurred_at: float
    recorded_at: float


class OutcomeObservationResponse(ApiModel):
    status: str
    observation: OutcomeObservation | None = None


class OutcomeMonitoringGroup(ApiModel):
    group: str
    recommendations: int = Field(ge=0)
    outcome_counts: dict[str, int]
    rates: dict[str, float]
    net_benefit_rate: float


class OutcomeMonitoringAlert(ApiModel):
    alert_type: str
    group: str
    observed: float
    threshold: float
    severity: Literal["review"]


class OutcomeMonitoringReport(ApiModel):
    policy_id: str
    policy_status: Literal["draft", "approved"]
    window_days: int = Field(ge=1, le=365)
    dimension: Literal["segment", "signal", "product"]
    minimum_sample_size: int = Field(ge=1)
    groups: list[OutcomeMonitoringGroup]
    alerts: list[OutcomeMonitoringAlert]
    limitations: list[str]


class SignalModelEvaluationReport(ApiModel):
    model_id: str
    model_version: str
    feature_schema_version: str
    evaluation_id: str
    evaluation_status: Literal["demo_approved", "approved", "pending"]
    dataset_version: str
    sample_count: int = Field(ge=0)
    accuracy: float = Field(ge=0, le=1)
    macro_precision: float = Field(ge=0, le=1)
    macro_recall: float = Field(ge=0, le=1)
    per_category: dict[str, Any]
    limitations: str


class GovernedArtifactRequest(ApiModel):
    artifact_type: Literal["product_catalog", "policy_registry"] = Field(alias="artifactType")
    version: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:+\-/]+$")
    payload: dict[str, Any]
    signature: str = Field(min_length=80, max_length=200)
    signing_key_id: str = Field(alias="signingKeyId", min_length=1, max_length=100)


class GovernedArtifactDecisionRequest(ApiModel):
    decision: Literal["approved", "rejected"]


class GovernedArtifactRecord(ApiModel):
    artifact_id: str
    artifact_type: Literal["product_catalog", "policy_registry"]
    version: str
    content_digest: str
    signing_key_id: str
    status: Literal["pending", "active", "rejected", "superseded"]
    requested_at: float
    decided_at: float | None = None
    effective_at: float | None = None
    item_count: int = Field(ge=1)


class GovernedArtifactResponse(ApiModel):
    status: str
    artifact: GovernedArtifactRecord | None = None


class HealthResponse(ApiModel):
    status: Literal["ok"]
    system: str
    version: str
    deployment_mode: str
    auth_mode: str
    data_residency: str
    controls: list[str]
    simulated_components: list[str]
    applied_migrations: list[str]


class ReadinessResponse(ApiModel):
    status: Literal["ready", "not_ready"]
    dependencies: list[dict[str, Any]]


class ProductResponse(ApiModel):
    segment: str
    trigger: str
    product_id: str
    product: str
    rate: float | None = None
    risk_tier: str
    catalog_version: str
    effective_from: str
    effective_to: str | None = None
    product_type: str
    monthly_commitment: float = Field(ge=0)
    max_dsti: float = Field(gt=0, le=1)


class AuditRecord(ApiModel):
    id: int
    timestamp: str
    customer_id: str
    signal: str
    recommended_product_id: str | None = None
    decision_token: str | None = None
    risk_tier: str | None = None
    delivery_mode: str | None = None
    compliance_status: int
    execution_time_ms: int


class CustomerDataExport(ApiModel):
    audit_logs: list[AuditRecord]
    consent_status: list[ConsentRecord]
    outcomes: list[dict[str, Any]] = Field(default_factory=list)


class ReviewDecisionRequest(ApiModel):
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=1000)


class HumanReview(ApiModel):
    review_id: str
    recommendation_id: str
    status: Literal["pending", "approved", "rejected"]
    reason: str | None = None
    reviewer_subject: str | None = None
    created_at: float
    decided_at: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class ReviewDecisionResponse(ApiModel):
    status: str
    review: HumanReview | None = None


class LedgerVerificationResponse(ApiModel):
    valid: bool
    records_checked: int
    failed_sequence: int | None = None
    head_hash: str | None = None


class EventStreamStatus(ApiModel):
    stream_name: str
    group_name: str
    length: int = Field(ge=0)
    pending: int = Field(ge=0)
    consumers: int = Field(ge=0)
    active_consumers: int = Field(ge=0)
    lag: int = Field(ge=0)
    dead_letters: int = Field(ge=0)
    within_slo: bool


class DeadLetterRecord(ApiModel):
    dead_letter_id: str
    original_event_id: str
    failed_at: str
    error_code: str
    event_type: str | None = None
    replay_count: int = Field(ge=0)


class DeadLetterReplayResponse(ApiModel):
    event_id: str
    replayed: bool
    deduplicated: bool
