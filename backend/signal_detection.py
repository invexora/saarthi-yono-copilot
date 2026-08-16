import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.ml.data_schema import DATASET_VERSION


CATEGORIES = ("friction", "opportunity", "lifeevent", "stress")
MODEL_ID = "saarthi-signal-rules"
MODEL_VERSION = "2026.08.3"
FEATURE_SCHEMA_VERSION = "signal-features-v2"

# The integrated demo sends a versioned signal code before the human-readable
# description. Treat that code as the deterministic contract; the phrase
# features below remain a fallback for unstructured prototype inputs.
SIGNAL_CODE_PREFIXES = {
    "friction": (
        "tax_friction",
        "branch_friction",
        "kyc_friction",
    ),
    "opportunity": (
        "debt_opportunity",
        "fd_opportunity",
        "auto_sweep_opportunity",
        "repayment_restructuring",
        "investment_opportunity",
    ),
    "lifeevent": (
        "life_event",
    ),
    "stress": (
        "overdraft_alert",
        "financial_stress",
    ),
}

FEATURES = {
    "friction": (
        ("FRICTION_BRANCH", "branch"),
        ("FRICTION_DEPOSIT", "deposit"),
        ("FRICTION_QUEUE", "queue"),
        ("FRICTION_FAILED_TXN", "failed transaction"),
    ),
    "opportunity": (
        ("OPPORTUNITY_INTEREST", "interest"),
        ("OPPORTUNITY_CARD", "credit card"),
        ("OPPORTUNITY_DEBT", "debt"),
        ("OPPORTUNITY_LOAN", "loan"),
    ),
    "lifeevent": (
        ("LIFEEVENT_SALARY", "salary"),
        ("LIFEEVENT_RETIREMENT", "retirement"),
        ("LIFEEVENT_GRADUATION", "graduation"),
        ("LIFEEVENT_PENSION", "pension credited"),
    ),
    "stress": (
        ("STRESS_HARDSHIP", "hardship"),
        ("STRESS_MISSED_PAYMENT", "missed payment"),
        ("STRESS_OVERDRAFT", "overdraft"),
        ("STRESS_DISTRESS", "financial stress"),
    ),
}

EVALUATION_CASES = (
    ("TAX_FRICTION — Quarterly counter advance tax payment detected", "friction"),
    ("DEBT_OPPORTUNITY — CC interest ₹4,200/mo exceeds consolidation threshold", "opportunity"),
    ("LIFE_EVENT — 30% salary increase detected over 3 consecutive months", "lifeevent"),
    ("OVERDRAFT_ALERT — Overdraft account utilization at 95%", "stress"),
    ("BRANCH_FRICTION — 4 counter deposit visits in the last 30 days", "friction"),
    ("FD_OPPORTUNITY — ₹50,000 idle savings exceeding 90-day liquidity buffer", "opportunity"),
    ("LIFE_EVENT — Policy maturity payout credit of ₹3,00,000 detected", "lifeevent"),
    ("FINANCIAL_STRESS — High pharmacy/medical merchant cash withdrawals", "stress"),
    ("BRANCH_FRICTION — 12 counter cash deposits in the last 15 days", "friction"),
    ("AUTO_SWEEP_OPPORTUNITY — Idle current account balance of ₹6,40,000", "opportunity"),
    ("LIFE_EVENT — GST refund credit of ₹1,50,000 detected", "lifeevent"),
    ("FINANCIAL_STRESS — Delayed accounts receivable, 98% draft utilization", "stress"),
    ("KYC_FRICTION — KYC compliance alert and 2 physical branch KYC queries", "friction"),
    ("REPAYMENT_RESTRUCTURING — High credit card balances exceeding stress index", "opportunity"),
    ("LIFE_EVENT — Monthly cash savings buffer below threshold", "lifeevent"),
    ("FINANCIAL_STRESS — Missed EMI (Home Loan) after salary reduction", "stress"),
    ("BRANCH_FRICTION — 2 branch visits for education loan statement queries", "friction"),
    ("INVESTMENT_OPPORTUNITY — ₹18,000 stipend with zero investment allocation", "opportunity"),
    ("LIFE_EVENT — First salary credit of ₹35,000 detected (new employment)", "lifeevent"),
    ("FINANCIAL_STRESS — Education loan EMI due with no regular income detected", "stress"),
)


class SignalDetectionError(RuntimeError):
    pass


def signal_digest(signal):
    return hashlib.sha256(signal.encode()).hexdigest()


def evaluate_signal_detector(detector, cases=EVALUATION_CASES):
    counts = {
        category: {"true_positive": 0, "false_positive": 0, "false_negative": 0}
        for category in CATEGORIES
    }
    correct = 0
    for signal, expected in cases:
        try:
            predicted = detector.classify(signal)["category"]
        except SignalDetectionError:
            predicted = None
        if predicted == expected:
            correct += 1
        for category in CATEGORIES:
            if predicted == category and expected == category:
                counts[category]["true_positive"] += 1
            elif predicted == category:
                counts[category]["false_positive"] += 1
            elif expected == category:
                counts[category]["false_negative"] += 1
    per_category = {}
    for category, values in counts.items():
        tp = values["true_positive"]
        precision_denominator = tp + values["false_positive"]
        recall_denominator = tp + values["false_negative"]
        per_category[category] = {
            "precision": round(tp / precision_denominator, 6) if precision_denominator else 0.0,
            "recall": round(tp / recall_denominator, 6) if recall_denominator else 0.0,
            "support": recall_denominator,
        }
    return {
        "evaluation_id": "integrated-demo-rules-2026.08.3",
        "dataset_version": "integrated-demo-contract-v1",
        "sample_count": len(cases),
        "accuracy": round(correct / len(cases), 6),
        "macro_precision": round(sum(v["precision"] for v in per_category.values()) / len(CATEGORIES), 6),
        "macro_recall": round(sum(v["recall"] for v in per_category.values()) / len(CATEGORIES), 6),
        "per_category": per_category,
        "limitations": (
            "Synthetic regression corpus covering the 20-journey integrated-demo contract; "
            "not evidence of production population "
            "performance, calibration, fairness, drift, or customer benefit."
        ),
    }


class VersionedRuleSignalDetector:
    mode = "rules"

    def __init__(self, minimum_confidence=0.60):
        self.minimum_confidence = minimum_confidence

    def classify(self, signal):
        normalized = " ".join(signal.lower().split())
        signal_code = normalized.split("—", 1)[0].strip()
        explicit_category = next(
            (
                category
                for category in CATEGORIES
                if signal_code in SIGNAL_CODE_PREFIXES[category]
            ),
            None,
        )
        matches = {
            category: [code for code, phrase in FEATURES[category] if phrase in normalized]
            for category in CATEGORIES
        }
        if explicit_category:
            category = explicit_category
            confidence = 0.99
            reason_codes = ["EXPLICIT_SIGNAL_CONTRACT_MATCH"]
            matches[category] = [f"SIGNAL_CODE_{signal_code.upper()}", *matches[category]]
        else:
            matched_categories = [category for category in CATEGORIES if matches[category]]
        if not explicit_category and matched_categories:
            category = matched_categories[0]
            ambiguous = len(matched_categories) > 1
            confidence = 0.65 if ambiguous else min(0.99, 0.75 + 0.05 * len(matches[category]))
            reason_codes = ["VERSIONED_FEATURE_MATCH"]
            if ambiguous:
                reason_codes.append("MULTI_CATEGORY_PRECEDENCE_APPLIED")
        elif not explicit_category:
            category = "stress"
            confidence = 0.60
            reason_codes = ["CONSERVATIVE_STRESS_FALLBACK"]
        if confidence < self.minimum_confidence:
            raise SignalDetectionError("signal_confidence_below_threshold")
        return {
            "category": category,
            "confidence": confidence,
            "model_id": MODEL_ID,
            "model_version": MODEL_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "matched_feature_codes": matches[category],
            "reason_codes": reason_codes,
            "input_digest": signal_digest(signal),
            "evaluation_id": "integrated-demo-rules-2026.08.3",
            "evaluation_status": "demo_approved",
        }

    def health(self):
        evaluation = evaluate_signal_detector(self)
        ready = (
            evaluation["accuracy"] >= 0.95
            and evaluation["macro_recall"] >= 0.90
            and evaluation["macro_precision"] >= 0.90
            and self.minimum_confidence <= 0.60
        )
        return {
            "name": "signal_detection",
            "mode": self.mode,
            "ready": ready,
            "detail": (
                f"model={MODEL_ID}:{MODEL_VERSION}; evaluation={evaluation['evaluation_id']}; "
                f"accuracy={evaluation['accuracy']}"
            ),
        }

    def evaluation_report(self):
        return {
            "model_id": MODEL_ID,
            "model_version": MODEL_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "evaluation_status": "demo_approved",
            **evaluate_signal_detector(self),
        }



class ModelSignalDetector:
    mode = "model"
    READY_WARNING = "SLM not yet trained or loaded"
    MODEL_ID_PREFIX = "saarthi-signal-lm"
    PENDING_MODEL_VERSION = "pending"

    def __init__(
        self,
        model_path: str | None,
        base_model: str | None = None,
        minimum_confidence: float = 0.60,
        config: dict[str, Any] | None = None,
    ):
        self.model_path = model_path.strip() if model_path else None
        self.base_model = base_model or "meta-llama/Llama-3.1-8B-Instruct"
        self.minimum_confidence = minimum_confidence
        self.config = config or {}
        self.model_id = f"{self.MODEL_ID_PREFIX}:{self.base_model.split('/')[-1]}"

    @property
    def model_version(self):
        return self.PENDING_MODEL_VERSION

    def _ensure_model_available(self):
        if not self.model_path:
            raise SignalDetectionError(self.READY_WARNING)
        model_path = Path(self.model_path)
        if not model_path.exists():
            raise SignalDetectionError(f"SLM checkpoint_missing: {self.model_path}")
        if not (model_path.is_file() or model_path.is_dir()):
            raise SignalDetectionError(f"SLM checkpoint_invalid: {self.model_path}")

    def classify(self, signal):
        self._ensure_model_available()
        raise SignalDetectionError("SLM inference is blocked in readiness-only mode")

    def health(self):
        checkpoint_ready = (
            bool(self.model_path)
            and Path(self.model_path).exists()
            and (Path(self.model_path).is_file() or Path(self.model_path).is_dir())
        )
        detail = self.READY_WARNING
        if self.model_path:
            if checkpoint_ready:
                detail = f"model checkpoint discovered: {self.model_path}"
            elif not Path(self.model_path).exists():
                detail = f"model checkpoint not found: {self.model_path}"
            else:
                detail = f"model checkpoint path invalid: {self.model_path}"
        return {
            "name": "signal_detection", "mode": self.mode, "ready": checkpoint_ready,
            "detail": detail,
        }

    def evaluation_report(self):
        if not self.health()["ready"]:
            return {
                "model_id": self.model_id,
                "model_version": self.model_version,
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "evaluation_id": "saarthi-signal-lm-ready-2026.08.3",
                "evaluation_status": "pending",
                "dataset_version": DATASET_VERSION,
                "sample_count": 0,
                "accuracy": 0.0,
                "macro_precision": 0.0,
                "macro_recall": 0.0,
                "per_category": {},
                "limitations": (
                    "Model checkpoint not available. Fine-tuning and deployment are deferred until SBI-approved dataset access; "
                    "run the synthetic dataset/fine-tune dry-run path and install a trained checkpoint."
                ),
            }

        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "evaluation_id": "saarthi-signal-lm-ready-2026.08.3",
            "evaluation_status": "pending",
            "dataset_version": DATASET_VERSION,
            "sample_count": 0,
            "accuracy": 0.0,
            "macro_precision": 0.0,
            "macro_recall": 0.0,
            "per_category": {},
            "limitations": (
                "Model checkpoint exists but readiness remains deferred. "
                "Run training and checkpointed deployment before switching model mode to active inference."
            ),
        }



class SbiSignalDetectionClient:
    mode = "sbi_api"

    def __init__(self, base_url, service_token, minimum_confidence=0.60, timeout_seconds=3.0):
        if not base_url or not service_token:
            raise RuntimeError("SBI signal detection URL and service token are required")
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.minimum_confidence = minimum_confidence
        self.timeout_seconds = timeout_seconds

    def _request(self, path, *, method="GET", payload=None):
        body = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else None
        headers = {
            "Authorization": f"Bearer {self.service_token}",
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method,
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read())

    def classify(self, signal):
        expected_digest = signal_digest(signal)
        payload = self._request(
            "/v1/signals/classify",
            method="POST",
            payload={
                "signal": signal,
                "inputDigest": expected_digest,
                "featureSchemaVersion": FEATURE_SCHEMA_VERSION,
            },
        )
        required = {
            "category", "confidence", "modelId", "modelVersion",
            "featureSchemaVersion", "reasonCodes", "inputDigest",
            "evaluationId", "evaluationStatus",
        }
        if not required.issubset(payload):
            raise SignalDetectionError("signal_detection_response_incomplete")
        if payload["category"] not in CATEGORIES:
            raise SignalDetectionError("signal_detection_category_invalid")
        if not isinstance(payload["confidence"], (int, float)) or not 0 <= payload["confidence"] <= 1:
            raise SignalDetectionError("signal_detection_confidence_invalid")
        if payload["confidence"] < self.minimum_confidence:
            raise SignalDetectionError("signal_confidence_below_threshold")
        if payload["inputDigest"] != expected_digest:
            raise SignalDetectionError("signal_detection_input_binding_failed")
        if payload["featureSchemaVersion"] != FEATURE_SCHEMA_VERSION:
            raise SignalDetectionError("signal_feature_schema_unsupported")
        if payload["evaluationStatus"] != "approved":
            raise SignalDetectionError("signal_model_not_approved")
        identity_limits = {"modelId": 120, "modelVersion": 60, "evaluationId": 200}
        if not all(
            isinstance(payload[field], str) and 1 <= len(payload[field]) <= maximum
            for field, maximum in identity_limits.items()
        ):
            raise SignalDetectionError("signal_model_identity_invalid")
        if not isinstance(payload["reasonCodes"], list) or not payload["reasonCodes"] or not all(
            isinstance(code, str) and 1 <= len(code) <= 100 for code in payload["reasonCodes"]
        ):
            raise SignalDetectionError("signal_reason_codes_invalid")
        return {
            "category": payload["category"],
            "confidence": float(payload["confidence"]),
            "model_id": str(payload["modelId"]),
            "model_version": str(payload["modelVersion"]),
            "feature_schema_version": payload["featureSchemaVersion"],
            "matched_feature_codes": [],
            "reason_codes": payload["reasonCodes"],
            "input_digest": payload["inputDigest"],
            "evaluation_id": str(payload["evaluationId"]),
            "evaluation_status": payload["evaluationStatus"],
        }

    def health(self):
        try:
            payload = self._request("/health")
            ready = payload.get("status") == "ok"
            return {
                "name": "signal_detection", "mode": self.mode, "ready": ready,
                "detail": "connected" if ready else "provider_not_ready",
            }
        except (HTTPError, URLError, OSError, ValueError, RuntimeError) as error:
            return {
                "name": "signal_detection", "mode": self.mode, "ready": False,
                "detail": type(error).__name__,
            }

    def evaluation_report(self):
        try:
            payload = self._request("/v1/signals/model")
        except (HTTPError, URLError, OSError, ValueError, RuntimeError) as error:
            raise SignalDetectionError("signal_model_evaluation_unavailable") from error
        required = {
            "modelId", "modelVersion", "featureSchemaVersion", "evaluationId",
            "evaluationStatus", "datasetVersion", "sampleCount", "metrics", "limitations",
        }
        if not required.issubset(payload) or payload["evaluationStatus"] != "approved":
            raise SignalDetectionError("signal_model_evaluation_invalid")
        if payload["featureSchemaVersion"] != FEATURE_SCHEMA_VERSION:
            raise SignalDetectionError("signal_feature_schema_unsupported")
        if not isinstance(payload["metrics"], dict) or not isinstance(payload["limitations"], list):
            raise SignalDetectionError("signal_model_evaluation_invalid")
        metrics = payload["metrics"]
        metric_values = [
            metrics.get("accuracy"), metrics.get("macroPrecision"), metrics.get("macroRecall"),
        ]
        if (
            not isinstance(payload["sampleCount"], int)
            or payload["sampleCount"] < 1
            or not all(isinstance(value, (int, float)) and 0 <= value <= 1 for value in metric_values)
            or not isinstance(metrics.get("perCategory"), dict)
        ):
            raise SignalDetectionError("signal_model_evaluation_invalid")
        return {
            "model_id": str(payload["modelId"]),
            "model_version": str(payload["modelVersion"]),
            "feature_schema_version": payload["featureSchemaVersion"],
            "evaluation_id": str(payload["evaluationId"]),
            "evaluation_status": payload["evaluationStatus"],
            "dataset_version": str(payload["datasetVersion"]),
            "sample_count": int(payload["sampleCount"]),
            "accuracy": metrics["accuracy"],
            "macro_precision": metrics["macroPrecision"],
            "macro_recall": metrics["macroRecall"],
            "per_category": metrics["perCategory"],
            "limitations": " ".join(str(item) for item in payload["limitations"]),
        }


def _normalize_model_config(raw_config):
    if raw_config is None:
        return {}
    if isinstance(raw_config, dict):
        return raw_config
    if isinstance(raw_config, str):
        if not raw_config.strip():
            return {}
        try:
            return json.loads(raw_config)
        except json.JSONDecodeError as error:
            raise RuntimeError("SAARTHI_SIGNAL_DETECTION_MODEL_CONFIG must be JSON when provided") from error
    raise RuntimeError("SAARTHI_SIGNAL_DETECTION_MODEL_CONFIG must be a JSON object")


def create_signal_detector(settings):
    if settings.signal_detection_mode == "sbi_api":
        return SbiSignalDetectionClient(
            settings.signal_detection_url,
            settings.signal_detection_token,
            settings.signal_detection_minimum_confidence,
        )
    if settings.signal_detection_mode == "model":
        return ModelSignalDetector(
            settings.signal_model_path,
            settings.signal_finetune_base_model,
            settings.signal_detection_minimum_confidence,
            _normalize_model_config(settings.signal_detection_model_config),
        )
    return VersionedRuleSignalDetector(settings.signal_detection_minimum_confidence)
