# Saarthi Internal Mock SBI Contract Pack

Version: `1.0.0`

This directory documents Invexora/Saarthi's **transport-neutral, synthetic-only**
boundary for development without SBI InnoHub sandbox access. It is not an SBI
or SBI InnoHub API specification, endpoint catalogue, payload definition,
scope, or certification.

Every operation has:

- a Saarthi-owned, versioned `operationId`;
- a stated purpose;
- strict Pydantic request and response schemas;
- `syntheticOnly: true`;
- `official_mapping: TBD_AFTER_INNOHUB_ACCESS`; and
- no asserted external URL or transport path.

The source of truth is
[`backend/mock_sbi_contracts.py`](../backend/mock_sbi_contracts.py). Its
`mock_contract_manifest()` function returns a JSON-serialisable contract pack
including the generated schemas for all operations. The module only validates
contracts; it does not mount HTTP routes, call SBI, or execute a financial
action. `assert_development_only()` fails closed for any runtime other than
`development`.

## Operation inventory

| Domain | operationId | Internal purpose |
|---|---|---|
| Identity and consent | `saarthiMockVerifyStepUpV1` | Validate a synthetic step-up reference |
| Identity and consent | `saarthiMockGetDecisionContextV1` | Read minimised decision context |
| Identity and consent | `saarthiMockListConsentsV1` | Read purpose-consent records |
| Identity and consent | `saarthiMockUpdateConsentV1` | Grant or revoke purpose consent |
| Identity and consent | `saarthiMockGetPreferencesV1` | Read engagement preferences |
| Identity and consent | `saarthiMockUpdatePreferencesV1` | Update one engagement preference |
| Accounts and signals | `saarthiMockListAccountsV1` | Read pseudonymous account references |
| Accounts and signals | `saarthiMockGetAccountBalanceV1` | Read a synthetic account balance |
| Accounts and signals | `saarthiMockListTransactionsV1` | Read categorised synthetic transactions |
| Accounts and signals | `saarthiMockListLiabilitiesV1` | Read minimised liabilities |
| Accounts and signals | `saarthiMockListCardsV1` | Read masked card references and status |
| Accounts and signals | `saarthiMockListHoldingsV1` | Read banded deposits, investments, pensions, and insurance holdings |
| Accounts and signals | `saarthiMockListActivitySignalsV1` | Read versioned signal and feature-set references |
| Product and decision support | `saarthiMockListProductsV1` | Read the effective-dated synthetic catalogue |
| Product and decision support | `saarthiMockGetProductV1` | Read one versioned product |
| Product and decision support | `saarthiMockGetProductTermsV1` | Read rates, disclosures, and key-fact references |
| Product and decision support | `saarthiMockEvaluateEligibilityV1` | Evaluate referenced, minimised eligibility features |
| Product and decision support | `saarthiMockListCandidateOffersV1` | Read offers backed by eligibility evidence |
| Engagement and fulfilment | `saarthiMockExecuteActionV1` | Execute a synthetic recommendation-bound action |
| Engagement and fulfilment | `saarthiMockGetActionStatusV1` | Read downstream and reconciliation status |
| Engagement and fulfilment | `saarthiMockCancelActionV1` | Request cancellation of a synthetic action |
| Engagement and fulfilment | `saarthiMockListActionDocumentsV1` | Read digest-addressed document references |
| Engagement and fulfilment | `saarthiMockSendNotificationV1` | Queue a template-bound synthetic notification |
| Outcome and operations | `saarthiMockCreateCaseV1` | Create a data-minimised support or review case |
| Outcome and operations | `saarthiMockGetCaseV1` | Read synthetic case status |
| Outcome and operations | `saarthiMockRecordOutcomeV1` | Record an idempotent outcome with evidence digest |
| Outcome and operations | `saarthiMockCreateComplaintV1` | Create a data-minimised complaint |
| Outcome and operations | `saarthiMockGetComplaintV1` | Read synthetic complaint status |

Counts: **6 identity/consent + 7 accounts/signals + 5 product/decision
support + 5 engagement/fulfilment + 5 outcome/operations = 28 operations**.

OIDC discovery and JWKS are intentionally excluded from these 28 application
contracts. Production already has an independent OIDC/JWKS verifier contract;
an SBI tenant URL, issuer, audience, algorithms, scopes, and key-set mapping
must come from authenticated SBI onboarding, not from this mock pack.

## Usage

```python
from backend.mock_sbi_contracts import (
    mock_contract_manifest,
    validate_mock_request,
    validate_mock_response,
)

manifest = mock_contract_manifest()
request = validate_mock_request("saarthiMockListAccountsV1", payload)
response = validate_mock_response("saarthiMockListAccountsV1", result)
```

No operation should be mapped to an SBI path, payload, OAuth scope, or error
code until the authenticated InnoHub artefact for that operation has been
received, reviewed, and recorded in a new contract version.
