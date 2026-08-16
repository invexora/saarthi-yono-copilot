"""Evaluate signal model scaffolding artifacts against synthetic seed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.signal_detection import ModelSignalDetector, SignalDetectionError, VersionedRuleSignalDetector, evaluate_signal_detector
from .data_schema import DATASET_VERSION, validate_record

DEFAULT_DATA = Path(__file__).resolve().parents[1] / "data" / "synthetic_training_seed.jsonl"


def _load_seed_rows(path: Path):
    rows = []
    for line_no, raw_line in enumerate(path.read_text().splitlines(), start=1):
        if not raw_line.strip():
            continue
        payload = json.loads(raw_line)
        try:
            rows.append(validate_record(payload))
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid seed row at line {line_no}: {error}") from error
    return rows


def _build_policy_summary(rows, predicted_categories):
    compatible = 0
    details = []
    for row, predicted in zip(rows, predicted_categories):
        expected = row.signal_category
        pass_case = predicted == expected
        if pass_case:
            compatible += 1
        details.append({
            "source_row_id": row.source_row_id,
            "expected": expected,
            "predicted": predicted,
            "policy_constraint_action": row.correct_action,
            "compatible": pass_case,
        })
    total = len(rows)
    return {
        "total": total,
        "compatible": compatible,
        "incompatible": total - compatible,
        "compatibility_rate": compatible / total if total else 0.0,
        "items": details,
    }


def evaluate(detector, rows):
    cases = [(row.customer_signal, row.signal_category) for row in rows]
    baseline = evaluate_signal_detector(detector, cases=cases)

    predicted_categories = []
    for row, _ in cases:
        evidence = detector.classify(row)
        predicted_categories.append(evidence["category"])

    policy_summary = _build_policy_summary(rows, predicted_categories)
    warnings = []
    if not getattr(detector, "model_version", ""):
        warnings.append("detector has no explicit model version")

    result = {
        **baseline,
        "policy_compatibility": policy_summary,
        "warnings": warnings,
    }
    result["dataset_version"] = baseline.get("dataset_version", DATASET_VERSION)
    return result


def _build_parser():
    parser = argparse.ArgumentParser(description="Evaluate signal model against synthetic seed")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--detector", default="rules", choices=("rules", "model"))
    parser.add_argument("--model-path", default=None)
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()

    data_path = Path(args.data)
    rows = _load_seed_rows(data_path)
    if len(rows) != 20:
        raise RuntimeError("seed must contain 20 rows")

    if args.detector == "model":
        detector = ModelSignalDetector(
            model_path=args.model_path,
            base_model="meta-llama/Llama-3.1-8B-Instruct",
            minimum_confidence=0.60,
            config={"seed_version": DATASET_VERSION},
        )
    else:
        detector = VersionedRuleSignalDetector()

    try:
        evaluation = evaluate(detector, rows)
    except SignalDetectionError as error:
        print("WARNING: " + str(error))
        if args.detector != "model":
            raise
        evaluation = {
            "evaluation_id": "saarthi-signal-model-eval-pending",
            "dataset_version": DATASET_VERSION,
            "sample_count": len(rows),
            "accuracy": 0.0,
            "macro_precision": 0.0,
            "macro_recall": 0.0,
            "per_category": {},
            "policy_compatibility": {
                "total": len(rows),
                "compatible": 0,
                "incompatible": len(rows),
                "compatibility_rate": 0.0,
                "items": [],
            },
            "warnings": [
                "No trained checkpoint available. Run dry-run fine-tune plan and install checkpoint before model evaluation.",
            ],
        }

    if args.detector == "model" and evaluation["sample_count"] == 20:
        evaluation["warnings"].insert(0, "Model mode evaluation used placeholder detector wiring; checkpoint required for production")
    print(json.dumps(evaluation, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
