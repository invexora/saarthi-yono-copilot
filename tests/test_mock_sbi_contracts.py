import json
import unittest
from collections import Counter

from pydantic import ValidationError

from backend.mock_sbi_contracts import (
    CONTRACT_ID,
    CONTRACT_VERSION,
    OFFICIAL_MAPPING,
    OPERATIONS,
    ContractCategory,
    assert_development_only,
    get_mock_operation,
    mock_contract_manifest,
    validate_mock_request,
    validate_mock_response,
)


class MockSbiContractPackTests(unittest.TestCase):
    def test_pack_has_exact_versioned_operation_inventory(self):
        self.assertEqual(CONTRACT_ID, "invexora.saarthi.mock-sbi-boundary")
        self.assertEqual(CONTRACT_VERSION, "1.0.0")
        self.assertEqual(len(OPERATIONS), 28)
        self.assertEqual(len({operation.operation_id for operation in OPERATIONS}), 28)
        self.assertEqual(
            Counter(operation.category for operation in OPERATIONS),
            {
                ContractCategory.identity_consent: 6,
                ContractCategory.accounts_signals: 7,
                ContractCategory.product_decision_support: 5,
                ContractCategory.engagement_fulfilment: 5,
                ContractCategory.outcome_operations: 5,
            },
        )

    def test_every_operation_is_saarthi_owned_synthetic_and_unmapped(self):
        for operation in OPERATIONS:
            with self.subTest(operation_id=operation.operation_id):
                self.assertTrue(operation.operation_id.startswith("saarthiMock"))
                self.assertTrue(operation.operation_id.endswith("V1"))
                self.assertTrue(operation.synthetic_only)
                self.assertEqual(operation.official_mapping, OFFICIAL_MAPPING)
                self.assertTrue(operation.purpose)

    def test_manifest_is_machine_readable_and_has_no_claimed_transport_path(self):
        manifest = mock_contract_manifest()
        serialized = json.dumps(manifest, sort_keys=True)

        self.assertEqual(manifest["operationCount"], 28)
        self.assertTrue(manifest["syntheticOnly"])
        self.assertEqual(manifest["official_mapping"], OFFICIAL_MAPPING)
        self.assertIn("Not an official SBI", manifest["disclaimer"])
        self.assertNotIn('"path"', serialized)
        self.assertNotIn("/v1/", serialized)
        self.assertEqual(len(manifest["operations"]), 28)

    def test_every_operation_exports_strict_request_and_response_schemas(self):
        for entry in mock_contract_manifest()["operations"]:
            with self.subTest(operation_id=entry["operationId"]):
                self.assertEqual(entry["requestSchema"]["type"], "object")
                self.assertEqual(entry["responseSchema"]["type"], "object")
                self.assertFalse(entry["requestSchema"]["additionalProperties"])
                self.assertFalse(entry["responseSchema"]["additionalProperties"])
                response_schema = json.dumps(entry["responseSchema"], sort_keys=True)
                self.assertIn("synthetic_only", response_schema)
                self.assertIn("correlation_id", response_schema)
                self.assertIn("audit_ref", response_schema)

    def test_mutating_operations_require_idempotency_and_reconciliation_fields(self):
        for operation in OPERATIONS:
            if not operation.mutating:
                continue
            with self.subTest(operation_id=operation.operation_id):
                request_schema = json.dumps(operation.request_model.model_json_schema())
                response_schema = json.dumps(operation.response_model.model_json_schema())
                self.assertIn("idempotency_key", request_schema)
                self.assertIn("idempotency_key", response_schema)
                self.assertIn("reconciliation_status", response_schema)

    def test_transport_neutral_request_and_response_validation(self):
        request = validate_mock_request(
            "saarthiMockVerifyStepUpV1",
            {
                "context": {
                    "contract_version": CONTRACT_VERSION,
                    "correlation_id": "corr-demo-0001",
                    "actor_ref": "synthetic-customer-001",
                    "actor_role": "customer",
                    "purpose": "authorize_demo_action",
                    "consent_ref": "synthetic-consent-001",
                    "idempotency_key": "step-up-demo-0001",
                },
                "challenge_ref": "synthetic-challenge-001",
                "proof_ref": "synthetic-proof-001",
            },
        )
        self.assertEqual(request.challenge_ref, "synthetic-challenge-001")

        response = validate_mock_response(
            "saarthiMockVerifyStepUpV1",
            {
                "contract_version": CONTRACT_VERSION,
                "synthetic_only": True,
                "correlation_id": "corr-demo-0001",
                "audit_ref": "synthetic-audit-001",
                "idempotency_key": "step-up-demo-0001",
                "reconciliation_status": "not_required",
                "status": "verified",
                "step_up_ref": "synthetic-step-up-001",
                "expires_at": "2026-08-13T12:00:00+05:30",
            },
        )
        self.assertTrue(response.synthetic_only)

    def test_contracts_reject_unmarked_or_extra_payloads(self):
        with self.assertRaises(ValidationError):
            validate_mock_response(
                "saarthiMockVerifyStepUpV1",
                {
                    "contract_version": CONTRACT_VERSION,
                    "synthetic_only": False,
                    "correlation_id": "corr-demo-0001",
                    "audit_ref": "synthetic-audit-001",
                    "idempotency_key": "step-up-demo-0001",
                    "reconciliation_status": "not_required",
                    "status": "verified",
                    "step_up_ref": "synthetic-step-up-001",
                    "expires_at": None,
                },
            )

        with self.assertRaises(ValidationError):
            validate_mock_request(
                "saarthiMockListAccountsV1",
                {
                    "context": {
                        "contract_version": CONTRACT_VERSION,
                        "correlation_id": "corr-demo-0002",
                        "actor_ref": "synthetic-customer-001",
                        "actor_role": "customer",
                        "purpose": "demo_account_context",
                        "consent_ref": "synthetic-consent-001",
                    },
                    "customer_ref": "synthetic-customer-001",
                    "unmapped_official_field": "must-fail",
                },
            )

    def test_mock_boundary_fails_closed_outside_development(self):
        assert_development_only("development")
        for mode in ("production", "staging", "pilot"):
            with self.subTest(mode=mode), self.assertRaisesRegex(RuntimeError, "development-only"):
                assert_development_only(mode)

    def test_unknown_operation_is_not_guessed(self):
        with self.assertRaisesRegex(KeyError, "unknown Saarthi mock operation"):
            get_mock_operation("sbiOfficialGetAccounts")


if __name__ == "__main__":
    unittest.main()
