import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.database import DatabaseManager
from backend.signal_detection import (
    FEATURE_SCHEMA_VERSION,
    SbiSignalDetectionClient,
    SignalDetectionError,
    VersionedRuleSignalDetector,
    signal_digest,
)
from backend.settings import Settings


class VersionedSignalDetectorTests(unittest.TestCase):
    def test_regression_corpus_has_per_category_metrics_and_explicit_limitations(self):
        detector = VersionedRuleSignalDetector()
        report = detector.evaluation_report()

        self.assertEqual(report["evaluation_status"], "demo_approved")
        self.assertEqual(report["accuracy"], 1.0)
        self.assertEqual(report["macro_precision"], 1.0)
        self.assertEqual(report["macro_recall"], 1.0)
        self.assertEqual(report["sample_count"], 20)
        self.assertEqual(report["dataset_version"], "integrated-demo-contract-v1")
        self.assertEqual(set(report["per_category"]), {
            "friction", "opportunity", "lifeevent", "stress",
        })
        self.assertTrue(all(metrics["support"] == 5 for metrics in report["per_category"].values()))
        self.assertIn("not evidence of production", report["limitations"])
        self.assertTrue(detector.health()["ready"])

    def test_evidence_is_versioned_input_bound_and_uses_explicit_precedence(self):
        detector = VersionedRuleSignalDetector()
        signal = "Branch visit after credit card interest issue"
        result = detector.classify(signal)

        self.assertEqual(result["category"], "friction")
        self.assertEqual(result["input_digest"], signal_digest(signal))
        self.assertEqual(result["feature_schema_version"], FEATURE_SCHEMA_VERSION)
        self.assertIn("MULTI_CATEGORY_PRECEDENCE_APPLIED", result["reason_codes"])
        self.assertNotIn(signal, json.dumps(result))

    def test_confidence_threshold_fails_closed(self):
        detector = VersionedRuleSignalDetector(minimum_confidence=0.70)
        with self.assertRaisesRegex(SignalDetectionError, "confidence"):
            detector.classify("No recognized feature")
        self.assertFalse(detector.health()["ready"])


class SbiSignalDetectionClientTests(unittest.TestCase):
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(self.payload).encode()

    def test_adapter_binds_response_to_input_and_validates_approval(self):
        signal = "Recurring credit card interest"
        payload = {
            "category": "opportunity",
            "confidence": 0.93,
            "modelId": "sbi-signal-detector",
            "modelVersion": "42",
            "featureSchemaVersion": FEATURE_SCHEMA_VERSION,
            "reasonCodes": ["CARD_INTEREST_PATTERN"],
            "inputDigest": signal_digest(signal),
            "evaluationId": "sbi-eval-42",
            "evaluationStatus": "approved",
        }
        client = SbiSignalDetectionClient("https://signals.internal", "workload-token")
        with patch(
            "backend.signal_detection.urlopen",
            return_value=self.Response(payload),
        ) as request:
            result = client.classify(signal)

        self.assertEqual(result["category"], "opportunity")
        sent_request = request.call_args.args[0]
        sent_payload = json.loads(sent_request.data)
        self.assertEqual(sent_payload["inputDigest"], signal_digest(signal))
        self.assertEqual(sent_request.headers["Authorization"], "Bearer workload-token")

        with patch(
            "backend.signal_detection.urlopen",
            return_value=self.Response({**payload, "inputDigest": "0" * 64}),
        ):
            with self.assertRaisesRegex(SignalDetectionError, "input_binding"):
                client.classify(signal)

    def test_evaluation_envelope_requires_approved_metrics_and_schema(self):
        payload = {
            "modelId": "sbi-signal-detector",
            "modelVersion": "42",
            "featureSchemaVersion": FEATURE_SCHEMA_VERSION,
            "evaluationId": "sbi-evaluation-42",
            "evaluationStatus": "approved",
            "datasetVersion": "sbi-holdout-2026-07",
            "sampleCount": 5000,
            "metrics": {
                "accuracy": 0.94,
                "macroPrecision": 0.92,
                "macroRecall": 0.91,
                "perCategory": {"stress": {"recall": 0.95}},
            },
            "limitations": ["Approved population and observation window only"],
        }
        client = SbiSignalDetectionClient("https://signals.internal", "workload-token")
        with patch(
            "backend.signal_detection.urlopen",
            return_value=self.Response(payload),
        ):
            report = client.evaluation_report()
        self.assertEqual(report["sample_count"], 5000)
        self.assertEqual(report["macro_recall"], 0.91)

        with patch(
            "backend.signal_detection.urlopen",
            return_value=self.Response({**payload, "evaluationStatus": "draft"}),
        ):
            with self.assertRaisesRegex(SignalDetectionError, "evaluation_invalid"):
                client.evaluation_report()


class SignalDetectionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "signal-api.db")
        self.db = DatabaseManager(db_path)
        self.settings = Settings(
            db_path=db_path,
            auth_mode="development",
            decision_secret="signal-api-decision-secret-at-least-32-characters",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def headers(customer_id, role="customer", idempotency_key=None):
        headers = {
            "X-Saarthi-Demo-Customer": customer_id,
            "X-Saarthi-Demo-Role": role,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def test_orchestration_masks_signal_before_detector_and_persists_provenance(self):
        class CapturingDetector:
            mode = "test"

            def __init__(self):
                self.signals = []

            def classify(self, signal):
                self.signals.append(signal)
                return {
                    "category": "opportunity",
                    "confidence": 0.91,
                    "model_id": "capturing-detector",
                    "model_version": "test-v1",
                    "feature_schema_version": FEATURE_SCHEMA_VERSION,
                    "matched_feature_codes": ["TEST_OPPORTUNITY"],
                    "reason_codes": ["TEST_CLASSIFICATION"],
                    "input_digest": signal_digest(signal),
                    "evaluation_id": "test-evaluation-v1",
                    "evaluation_status": "approved",
                }

            def health(self):
                return {"name": "signal_detection", "mode": "test", "ready": True, "detail": "fixed"}

            def evaluation_report(self):
                return VersionedRuleSignalDetector().evaluation_report()

        detector = CapturingDetector()
        customer_id = "SBI-SIGNAL-API-001"
        with TestClient(create_app(self.settings, self.db, signal_detector=detector)) as client:
            client.post(
                "/api/v1/consent/grant",
                json={"purpose": "personalization"},
                headers=self.headers(customer_id),
            )
            response = client.post(
                "/api/v1/orchestrate",
                json={
                    "signal": "Credit card interest for private@example.com",
                    "segment": "corporate",
                },
                headers=self.headers(customer_id, idempotency_key="signal-contract-001"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("private@example.com", detector.signals[0])
        self.assertIn("[MASKED EMAIL]", detector.signals[0])
        body = response.json()
        self.assertEqual(body["signal_evidence"]["model_id"], "capturing-detector")
        self.assertIn("EVALUATED_SIGNAL_EVIDENCE", body["reason_codes"])
        stored = self.db.get_recommendation_context(body["recommendation_id"], customer_id)
        self.assertEqual(
            stored["evidence"]["signal_detection"]["input_digest"],
            body["signal_evidence"]["input_digest"],
        )

    def test_detector_failure_releases_idempotency_and_consumes_no_budget(self):
        class FailingDetector:
            mode = "test"
            calls = 0

            def classify(self, _):
                self.calls += 1
                raise SignalDetectionError("below threshold")

            def health(self):
                return {"name": "signal_detection", "mode": "test", "ready": True, "detail": "flaky"}

            def evaluation_report(self):
                raise SignalDetectionError("unavailable")

        detector = FailingDetector()
        customer_id = "SBI-SIGNAL-FAIL-001"
        headers = self.headers(customer_id, idempotency_key="signal-failure-retry-001")
        with TestClient(create_app(self.settings, self.db, signal_detector=detector)) as client:
            client.post(
                "/api/v1/consent/grant",
                json={"purpose": "personalization"},
                headers=self.headers(customer_id),
            )
            responses = [client.post(
                "/api/v1/orchestrate",
                json={"signal": "Unknown behavior", "segment": "corporate"},
                headers=headers,
            ) for _ in range(2)]

        self.assertEqual([response.status_code for response in responses], [503, 503])
        self.assertEqual(detector.calls, 2)
        self.assertEqual(self.db.get_nudge_budget_status(customer_id)["used"], 0)

    def test_model_evaluation_endpoint_is_role_gated(self):
        with TestClient(create_app(self.settings, self.db)) as client:
            denied = client.get(
                "/api/v1/governance/signal-model",
                headers=self.headers("SBI-SIGNAL-CUSTOMER"),
            )
            allowed = client.get(
                "/api/v1/governance/signal-model",
                headers=self.headers("SBI-SIGNAL-AUDITOR", "auditor"),
            )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["evaluation_status"], "demo_approved")
        self.assertIn("Synthetic regression corpus", allowed.json()["limitations"])


if __name__ == "__main__":
    unittest.main()
