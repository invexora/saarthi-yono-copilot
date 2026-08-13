"""Versioned, transport-neutral contracts for Saarthi's synthetic SBI boundary.

These are Invexora/Saarthi-owned mock contracts. They are not SBI or SBI
InnoHub endpoint names, payload definitions, scopes, or compatibility claims.
The official mapping deliberately remains unresolved until authenticated
InnoHub documentation and sandbox access are available.

The module exposes schemas and validators only. It does not register HTTP
routes, call a bank service, or execute financial actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


CONTRACT_ID = "invexora.saarthi.mock-sbi-boundary"
CONTRACT_VERSION = "1.0.0"
CONTRACT_OWNER = "Invexora Saarthi"
OFFICIAL_MAPPING = "TBD_AFTER_INNOHUB_ACCESS"
SYNTHETIC_ONLY = True
DISCLAIMER = (
    "Internal Invexora/Saarthi synthetic contract. Not an official SBI or "
    "SBI InnoHub API specification, endpoint, payload, scope, or certification."
)

Reference = str
Timestamp = str


class ContractModel(BaseModel):
    """Strict base for every request, response, and nested record."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class QueryContext(ContractModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    correlation_id: str = Field(min_length=8, max_length=128)
    actor_ref: Reference = Field(min_length=3, max_length=200)
    actor_role: Literal["customer", "service", "reviewer", "operations", "auditor"]
    purpose: str = Field(min_length=3, max_length=120)
    consent_ref: Reference | None = Field(default=None, max_length=200)


class MutationContext(QueryContext):
    idempotency_key: str = Field(min_length=8, max_length=128)


class SyntheticResponse(ContractModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    synthetic_only: Literal[True] = True
    correlation_id: str = Field(min_length=8, max_length=128)
    audit_ref: Reference = Field(min_length=3, max_length=200)


class SyntheticMutationResponse(SyntheticResponse):
    idempotency_key: str = Field(min_length=8, max_length=128)
    reconciliation_status: Literal[
        "not_required", "pending", "matched", "mismatch", "reversed"
    ]


# Request contracts ---------------------------------------------------------


class StepUpVerificationRequest(ContractModel):
    context: MutationContext
    challenge_ref: Reference = Field(min_length=3, max_length=200)
    proof_ref: Reference = Field(
        min_length=3,
        max_length=200,
        description="Synthetic proof reference only; never an OTP, password, or biometric.",
    )


class CustomerQueryRequest(ContractModel):
    context: QueryContext
    customer_ref: Reference = Field(min_length=3, max_length=200)


class ConsentUpdateRequest(ContractModel):
    context: MutationContext
    customer_ref: Reference = Field(min_length=3, max_length=200)
    consent_purpose: str = Field(min_length=3, max_length=120)
    decision: Literal["grant", "revoke"]
    consent_version: str = Field(min_length=1, max_length=100)


class PreferencesUpdateRequest(ContractModel):
    context: MutationContext
    customer_ref: Reference = Field(min_length=3, max_length=200)
    channel: Literal["in_app", "push", "sms", "email"]
    enabled: bool
    language: str = Field(min_length=2, max_length=20)


class AccountQueryRequest(ContractModel):
    context: QueryContext
    account_ref: Reference = Field(min_length=3, max_length=200)


class TransactionsQueryRequest(AccountQueryRequest):
    window_start: Timestamp
    window_end: Timestamp
    cursor: str | None = Field(default=None, max_length=300)
    page_size: int = Field(default=50, ge=1, le=200)


class ActivitySignalsQueryRequest(CustomerQueryRequest):
    since: Timestamp
    signal_types: list[str] = Field(default_factory=list, max_length=20)


class ProductListRequest(ContractModel):
    context: QueryContext
    segment: str | None = Field(default=None, max_length=80)
    as_of: Timestamp


class ProductQueryRequest(ContractModel):
    context: QueryContext
    product_id: Reference = Field(min_length=3, max_length=200)
    as_of: Timestamp


class EligibilityEvaluationRequest(ContractModel):
    context: QueryContext
    customer_ref: Reference = Field(min_length=3, max_length=200)
    product_id: Reference = Field(min_length=3, max_length=200)
    decision_context_ref: Reference = Field(min_length=3, max_length=200)
    feature_set_ref: Reference = Field(
        min_length=3,
        max_length=200,
        description="Reference to a minimised synthetic feature set; no raw transactions.",
    )


class ActionExecutionRequest(ContractModel):
    context: MutationContext
    customer_ref: Reference = Field(min_length=3, max_length=200)
    recommendation_ref: Reference = Field(min_length=3, max_length=200)
    product_id: Reference = Field(min_length=3, max_length=200)
    authorization_ref: Reference = Field(
        min_length=3,
        max_length=200,
        description="Synthetic authorization reference, not a reusable credential.",
    )


class ActionQueryRequest(ContractModel):
    context: QueryContext
    action_ref: Reference = Field(min_length=3, max_length=200)


class ActionCancellationRequest(ContractModel):
    context: MutationContext
    action_ref: Reference = Field(min_length=3, max_length=200)
    reason_code: str = Field(min_length=3, max_length=100)


class NotificationRequest(ContractModel):
    context: MutationContext
    customer_ref: Reference = Field(min_length=3, max_length=200)
    template_ref: Reference = Field(min_length=3, max_length=200)
    channel: Literal["in_app", "push", "sms", "email"]
    presentation_ref: Reference = Field(min_length=3, max_length=200)


class CaseCreationRequest(ContractModel):
    context: MutationContext
    customer_ref: Reference = Field(min_length=3, max_length=200)
    recommendation_ref: Reference | None = Field(default=None, max_length=200)
    case_type: Literal["relationship_manager", "fulfilment_review", "customer_support"]
    safe_summary: str = Field(min_length=3, max_length=1000)


class CaseQueryRequest(ContractModel):
    context: QueryContext
    case_ref: Reference = Field(min_length=3, max_length=200)


class OutcomeRecordingRequest(ContractModel):
    context: MutationContext
    recommendation_ref: Reference = Field(min_length=3, max_length=200)
    outcome_type: Literal["accepted", "fulfilled", "dismissed", "complaint", "harm"]
    source_event_ref: Reference = Field(min_length=3, max_length=200)
    evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    occurred_at: Timestamp


class ComplaintCreationRequest(ContractModel):
    context: MutationContext
    customer_ref: Reference = Field(min_length=3, max_length=200)
    recommendation_ref: Reference | None = Field(default=None, max_length=200)
    category: str = Field(min_length=3, max_length=100)
    safe_summary: str = Field(min_length=3, max_length=1000)


class ComplaintQueryRequest(ContractModel):
    context: QueryContext
    complaint_ref: Reference = Field(min_length=3, max_length=200)


# Record and response contracts --------------------------------------------


class StepUpVerificationResponse(SyntheticMutationResponse):
    status: Literal["verified", "declined", "expired"]
    step_up_ref: Reference = Field(min_length=3, max_length=200)
    expires_at: Timestamp | None = None


class DecisionContextRecord(ContractModel):
    customer_ref: Reference
    context_version: str
    as_of: Timestamp
    verification_status: Literal["synthetic_verified", "stale", "unavailable"]
    segment: str
    feature_set_ref: Reference


class DecisionContextResponse(SyntheticResponse):
    status: Literal["available", "stale", "unavailable"]
    decision_context: DecisionContextRecord | None = None


class ConsentRecord(ContractModel):
    consent_ref: Reference
    purpose: str
    status: Literal["granted", "revoked"]
    version: str
    updated_at: Timestamp


class ConsentListResponse(SyntheticResponse):
    status: Literal["available"]
    consents: list[ConsentRecord]


class ConsentUpdateResponse(SyntheticMutationResponse):
    status: Literal["granted", "revoked", "rejected"]
    consent: ConsentRecord | None = None


class PreferenceRecord(ContractModel):
    channel: Literal["in_app", "push", "sms", "email"]
    enabled: bool
    language: str


class PreferencesResponse(SyntheticResponse):
    status: Literal["available"]
    preferences: list[PreferenceRecord]


class PreferencesUpdateResponse(SyntheticMutationResponse):
    status: Literal["updated", "rejected"]
    preference: PreferenceRecord | None = None


class AccountRecord(ContractModel):
    account_ref: Reference
    account_type: Literal["savings", "current", "deposit", "loan"]
    currency: Literal["INR"] = "INR"
    status: Literal["active", "dormant", "closed"]


class AccountsResponse(SyntheticResponse):
    status: Literal["available"]
    accounts: list[AccountRecord]


class BalanceRecord(ContractModel):
    account_ref: Reference
    currency: Literal["INR"] = "INR"
    available_amount: float
    ledger_amount: float
    as_of: Timestamp


class BalanceResponse(SyntheticResponse):
    status: Literal["available", "unavailable"]
    balance: BalanceRecord | None = None


class TransactionRecord(ContractModel):
    transaction_ref: Reference
    direction: Literal["credit", "debit"]
    category: str
    amount: float = Field(ge=0)
    currency: Literal["INR"] = "INR"
    occurred_at: Timestamp


class TransactionsResponse(SyntheticResponse):
    status: Literal["available"]
    transactions: list[TransactionRecord]
    next_cursor: str | None = None


class LiabilityRecord(ContractModel):
    liability_ref: Reference
    liability_type: Literal["loan", "credit_card", "overdraft"]
    outstanding_amount: float = Field(ge=0)
    currency: Literal["INR"] = "INR"


class LiabilitiesResponse(SyntheticResponse):
    status: Literal["available"]
    liabilities: list[LiabilityRecord]


class CardRecord(ContractModel):
    card_ref: Reference
    card_type: Literal["credit", "debit", "prepaid"]
    status: Literal["active", "blocked", "closed"]
    masked_label: str = Field(max_length=40)


class CardsResponse(SyntheticResponse):
    status: Literal["available"]
    cards: list[CardRecord]


class HoldingRecord(ContractModel):
    holding_ref: Reference
    holding_type: Literal["deposit", "mutual_fund", "pension", "insurance"]
    product_ref: Reference
    valuation_band: str = Field(max_length=80)


class HoldingsResponse(SyntheticResponse):
    status: Literal["available"]
    holdings: list[HoldingRecord]


class ActivitySignalRecord(ContractModel):
    signal_ref: Reference
    signal_type: Literal["friction", "opportunity", "lifeevent", "stress"]
    feature_schema_version: str
    feature_set_ref: Reference
    detected_at: Timestamp


class ActivitySignalsResponse(SyntheticResponse):
    status: Literal["available"]
    signals: list[ActivitySignalRecord]


class ProductRecord(ContractModel):
    product_id: Reference
    name: str
    product_type: Literal["credit", "deposit", "investment", "service"]
    catalog_version: str
    effective_from: Timestamp
    effective_to: Timestamp | None = None


class ProductsResponse(SyntheticResponse):
    status: Literal["available"]
    products: list[ProductRecord]


class ProductResponse(SyntheticResponse):
    status: Literal["available", "not_found"]
    product: ProductRecord | None = None


class ProductTermsRecord(ContractModel):
    product_id: Reference
    terms_version: str
    rate_type: Literal["fixed", "floating", "not_applicable"]
    annual_rate: float | None = Field(default=None, ge=0, le=100)
    disclosure_ref: Reference
    key_facts_ref: Reference | None = None
    effective_from: Timestamp
    effective_to: Timestamp | None = None


class ProductTermsResponse(SyntheticResponse):
    status: Literal["available", "not_found"]
    terms: ProductTermsRecord | None = None


class EligibilityEvaluationResponse(SyntheticResponse):
    status: Literal["eligible", "ineligible", "review_required", "unavailable"]
    evaluation_ref: Reference
    product_id: Reference
    reason_codes: list[str]
    decision_context_ref: Reference


class CandidateOfferRecord(ContractModel):
    offer_ref: Reference
    product_id: Reference
    eligibility_evaluation_ref: Reference
    expires_at: Timestamp
    risk_tier: Literal["low", "high", "support"]


class CandidateOffersResponse(SyntheticResponse):
    status: Literal["available"]
    offers: list[CandidateOfferRecord]


class ActionRecord(ContractModel):
    action_ref: Reference
    recommendation_ref: Reference
    product_id: Reference
    status: Literal[
        "pending", "processing", "completed", "declined", "cancelled", "reversed", "mismatch"
    ]
    provider_reference: Reference | None = None
    updated_at: Timestamp


class ActionExecutionResponse(SyntheticMutationResponse):
    status: Literal["pending", "processing", "completed", "declined", "duplicate"]
    action: ActionRecord


class ActionStatusResponse(SyntheticResponse):
    status: Literal["available", "not_found"]
    action: ActionRecord | None = None


class ActionCancellationResponse(SyntheticMutationResponse):
    status: Literal["cancelled", "not_cancellable", "not_found"]
    action: ActionRecord | None = None


class DocumentRecord(ContractModel):
    document_ref: Reference
    document_type: Literal["receipt", "key_facts", "terms", "acknowledgement"]
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ActionDocumentsResponse(SyntheticResponse):
    status: Literal["available", "not_found"]
    documents: list[DocumentRecord]


class NotificationResponse(SyntheticMutationResponse):
    status: Literal["queued", "delivered", "failed", "duplicate"]
    notification_ref: Reference


class CaseRecord(ContractModel):
    case_ref: Reference
    case_type: Literal["relationship_manager", "fulfilment_review", "customer_support"]
    status: Literal["pending", "open", "resolved", "closed"]
    updated_at: Timestamp


class CaseCreationResponse(SyntheticMutationResponse):
    status: Literal["created", "duplicate", "rejected"]
    case: CaseRecord | None = None


class CaseResponse(SyntheticResponse):
    status: Literal["available", "not_found"]
    case: CaseRecord | None = None


class OutcomeResponse(SyntheticMutationResponse):
    status: Literal["recorded", "duplicate", "rejected"]
    observation_ref: Reference


class ComplaintRecord(ContractModel):
    complaint_ref: Reference
    status: Literal["received", "open", "resolved", "closed"]
    category: str
    updated_at: Timestamp


class ComplaintCreationResponse(SyntheticMutationResponse):
    status: Literal["created", "duplicate", "rejected"]
    complaint: ComplaintRecord | None = None


class ComplaintResponse(SyntheticResponse):
    status: Literal["available", "not_found"]
    complaint: ComplaintRecord | None = None


class ContractCategory(str, Enum):
    identity_consent = "identity_consent"
    accounts_signals = "accounts_signals"
    product_decision_support = "product_decision_support"
    engagement_fulfilment = "engagement_fulfilment"
    outcome_operations = "outcome_operations"


@dataclass(frozen=True)
class MockSbiOperation:
    operation_id: str
    category: ContractCategory
    purpose: str
    request_model: type[ContractModel]
    response_model: type[ContractModel]
    mutating: bool = False
    synthetic_only: bool = SYNTHETIC_ONLY
    official_mapping: str = OFFICIAL_MAPPING

    def __post_init__(self) -> None:
        if not self.operation_id.startswith("saarthiMock") or not self.operation_id.endswith("V1"):
            raise ValueError("mock operation IDs must be Saarthi-owned and versioned")
        if self.synthetic_only is not True:
            raise ValueError("mock operation must remain synthetic-only")
        if self.official_mapping != OFFICIAL_MAPPING:
            raise ValueError("official mapping cannot be asserted before InnoHub access")

    def manifest_entry(self) -> dict[str, Any]:
        return {
            "operationId": self.operation_id,
            "category": self.category.value,
            "purpose": self.purpose,
            "contractOwner": CONTRACT_OWNER,
            "syntheticOnly": self.synthetic_only,
            "official_mapping": self.official_mapping,
            "mutating": self.mutating,
            "transport": "UNMAPPED_TRANSPORT_NEUTRAL",
            "requestModel": self.request_model.__name__,
            "responseModel": self.response_model.__name__,
            "requestSchema": self.request_model.model_json_schema(),
            "responseSchema": self.response_model.model_json_schema(),
        }


OPERATIONS: tuple[MockSbiOperation, ...] = (
    # Identity and consent: 6
    MockSbiOperation(
        "saarthiMockVerifyStepUpV1", ContractCategory.identity_consent,
        "Verify a synthetic step-up challenge reference before a protected action.",
        StepUpVerificationRequest, StepUpVerificationResponse, True,
    ),
    MockSbiOperation(
        "saarthiMockGetDecisionContextV1", ContractCategory.identity_consent,
        "Read a minimised, pseudonymous customer decision-context reference.",
        CustomerQueryRequest, DecisionContextResponse,
    ),
    MockSbiOperation(
        "saarthiMockListConsentsV1", ContractCategory.identity_consent,
        "Read purpose-specific synthetic consent records for one customer reference.",
        CustomerQueryRequest, ConsentListResponse,
    ),
    MockSbiOperation(
        "saarthiMockUpdateConsentV1", ContractCategory.identity_consent,
        "Grant or revoke a versioned synthetic purpose-consent record.",
        ConsentUpdateRequest, ConsentUpdateResponse, True,
    ),
    MockSbiOperation(
        "saarthiMockGetPreferencesV1", ContractCategory.identity_consent,
        "Read synthetic engagement-channel and language preferences.",
        CustomerQueryRequest, PreferencesResponse,
    ),
    MockSbiOperation(
        "saarthiMockUpdatePreferencesV1", ContractCategory.identity_consent,
        "Update one synthetic engagement preference with idempotency evidence.",
        PreferencesUpdateRequest, PreferencesUpdateResponse, True,
    ),

    # Accounts and signals: 7
    MockSbiOperation(
        "saarthiMockListAccountsV1", ContractCategory.accounts_signals,
        "List synthetic account references without exposing account numbers.",
        CustomerQueryRequest, AccountsResponse,
    ),
    MockSbiOperation(
        "saarthiMockGetAccountBalanceV1", ContractCategory.accounts_signals,
        "Read a synthetic balance for a pseudonymous account reference.",
        AccountQueryRequest, BalanceResponse,
    ),
    MockSbiOperation(
        "saarthiMockListTransactionsV1", ContractCategory.accounts_signals,
        "Read paginated, categorised synthetic transactions for an approved window.",
        TransactionsQueryRequest, TransactionsResponse,
    ),
    MockSbiOperation(
        "saarthiMockListLiabilitiesV1", ContractCategory.accounts_signals,
        "Read minimised synthetic liability summaries for affordability checks.",
        CustomerQueryRequest, LiabilitiesResponse,
    ),
    MockSbiOperation(
        "saarthiMockListCardsV1", ContractCategory.accounts_signals,
        "Read synthetic card references and status without full card data.",
        CustomerQueryRequest, CardsResponse,
    ),
    MockSbiOperation(
        "saarthiMockListHoldingsV1", ContractCategory.accounts_signals,
        "Read banded synthetic deposit, investment, pension, and insurance holdings.",
        CustomerQueryRequest, HoldingsResponse,
    ),
    MockSbiOperation(
        "saarthiMockListActivitySignalsV1", ContractCategory.accounts_signals,
        "Read versioned synthetic signal references and minimised feature-set bindings.",
        ActivitySignalsQueryRequest, ActivitySignalsResponse,
    ),

    # Product and decision support: 5
    MockSbiOperation(
        "saarthiMockListProductsV1", ContractCategory.product_decision_support,
        "List effective-dated synthetic product catalogue records.",
        ProductListRequest, ProductsResponse,
    ),
    MockSbiOperation(
        "saarthiMockGetProductV1", ContractCategory.product_decision_support,
        "Read one versioned synthetic product record.",
        ProductQueryRequest, ProductResponse,
    ),
    MockSbiOperation(
        "saarthiMockGetProductTermsV1", ContractCategory.product_decision_support,
        "Read effective-dated synthetic rates, disclosures, and key-fact references.",
        ProductQueryRequest, ProductTermsResponse,
    ),
    MockSbiOperation(
        "saarthiMockEvaluateEligibilityV1", ContractCategory.product_decision_support,
        "Evaluate synthetic eligibility using referenced, minimised decision features.",
        EligibilityEvaluationRequest, EligibilityEvaluationResponse,
    ),
    MockSbiOperation(
        "saarthiMockListCandidateOffersV1", ContractCategory.product_decision_support,
        "Read synthetic candidate offers backed by eligibility evidence.",
        CustomerQueryRequest, CandidateOffersResponse,
    ),

    # Engagement and fulfilment: 5
    MockSbiOperation(
        "saarthiMockExecuteActionV1", ContractCategory.engagement_fulfilment,
        "Execute a synthetic, recommendation-bound action after authorization.",
        ActionExecutionRequest, ActionExecutionResponse, True,
    ),
    MockSbiOperation(
        "saarthiMockGetActionStatusV1", ContractCategory.engagement_fulfilment,
        "Read synthetic downstream action and reconciliation status.",
        ActionQueryRequest, ActionStatusResponse,
    ),
    MockSbiOperation(
        "saarthiMockCancelActionV1", ContractCategory.engagement_fulfilment,
        "Request cancellation of a cancellable synthetic action.",
        ActionCancellationRequest, ActionCancellationResponse, True,
    ),
    MockSbiOperation(
        "saarthiMockListActionDocumentsV1", ContractCategory.engagement_fulfilment,
        "Read digest-addressed synthetic receipts, terms, and acknowledgement references.",
        ActionQueryRequest, ActionDocumentsResponse,
    ),
    MockSbiOperation(
        "saarthiMockSendNotificationV1", ContractCategory.engagement_fulfilment,
        "Queue a synthetic, template-bound customer notification.",
        NotificationRequest, NotificationResponse, True,
    ),

    # Outcomes and operations: 5
    MockSbiOperation(
        "saarthiMockCreateCaseV1", ContractCategory.outcome_operations,
        "Create a data-minimised synthetic RM, support, or fulfilment-review case.",
        CaseCreationRequest, CaseCreationResponse, True,
    ),
    MockSbiOperation(
        "saarthiMockGetCaseV1", ContractCategory.outcome_operations,
        "Read synthetic case status through a pseudonymous case reference.",
        CaseQueryRequest, CaseResponse,
    ),
    MockSbiOperation(
        "saarthiMockRecordOutcomeV1", ContractCategory.outcome_operations,
        "Record an idempotent synthetic recommendation outcome with evidence digest.",
        OutcomeRecordingRequest, OutcomeResponse, True,
    ),
    MockSbiOperation(
        "saarthiMockCreateComplaintV1", ContractCategory.outcome_operations,
        "Create a data-minimised synthetic complaint record.",
        ComplaintCreationRequest, ComplaintCreationResponse, True,
    ),
    MockSbiOperation(
        "saarthiMockGetComplaintV1", ContractCategory.outcome_operations,
        "Read synthetic complaint status without exposing free-form source data.",
        ComplaintQueryRequest, ComplaintResponse,
    ),
)


_OPERATIONS_BY_ID = {operation.operation_id: operation for operation in OPERATIONS}


def get_mock_operation(operation_id: str) -> MockSbiOperation:
    """Return one internal operation definition, raising on unmapped names."""

    try:
        return _OPERATIONS_BY_ID[operation_id]
    except KeyError as error:
        raise KeyError(f"unknown Saarthi mock operation: {operation_id}") from error


def validate_mock_request(operation_id: str, payload: dict[str, Any]) -> ContractModel:
    """Strictly validate a transport-neutral synthetic request payload."""

    return get_mock_operation(operation_id).request_model.model_validate(payload)


def validate_mock_response(operation_id: str, payload: dict[str, Any]) -> ContractModel:
    """Strictly validate a synthetic response, including its synthetic marker."""

    return get_mock_operation(operation_id).response_model.model_validate(payload)


def mock_contract_manifest() -> dict[str, Any]:
    """Return the complete JSON-serialisable 28-operation contract pack."""

    return {
        "contractId": CONTRACT_ID,
        "version": CONTRACT_VERSION,
        "contractOwner": CONTRACT_OWNER,
        "title": "Saarthi Internal Mock SBI Boundary",
        "disclaimer": DISCLAIMER,
        "syntheticOnly": SYNTHETIC_ONLY,
        "official_mapping": OFFICIAL_MAPPING,
        "transport": "UNMAPPED_TRANSPORT_NEUTRAL",
        "operationCount": len(OPERATIONS),
        "operations": [operation.manifest_entry() for operation in OPERATIONS],
    }


def assert_development_only(deployment_mode: str) -> None:
    """Fail closed if a future adapter tries to mount this mock outside development."""

    if deployment_mode != "development":
        raise RuntimeError("Saarthi mock SBI contracts are development-only")
