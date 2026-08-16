"""Generate a deterministic synthetic training seed from canonical 20-case fixtures."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

try:
    from .data_schema import DATASET_VERSION, SyntheticSignalExample, records_as_jsonl, validate_record
except ImportError:
    from backend.ml.data_schema import DATASET_VERSION, SyntheticSignalExample, records_as_jsonl, validate_record


DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "test_demo_journey_contract.py"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "synthetic_training_seed.jsonl"


def _load_journeys(path: Path):
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "JOURNEYS":
                    journeys = ast.literal_eval(node.value)
                    break
            else:
                continue
            break
    else:
        raise ValueError("JOURNEYS fixture not found")

    return journeys


def _record_from_journey(journey):
    (
        source_row_id,
        segment,
        customer_signal,
        signal_category,
        _product_id,
        delivery_mode,
        outcome,
        actionable,
    ) = journey

    return validate_record({
        "customer_signal": customer_signal,
        "persona_context": json.dumps({
            "segment": segment,
            "journey_id": source_row_id,
        }, sort_keys=True),
        "policy_constraints": {
            "segment": segment,
            "delivery_mode": delivery_mode,
            "outcome": outcome,
            "actionable": bool(actionable),
        },
        "correct_action": outcome if outcome in {"eligible", "support_only", "rejected", "hold", "defer"} else "support_only",
        "rationale": (
            f"Seed contract expects {signal_category} actioned as {outcome}; "
            f"delivery mode {delivery_mode} with segment {segment}."
        ),
        "dataset_version": DATASET_VERSION,
        "signal_category": signal_category,
        "notes": "canonical integrated-demo journey contract",
        "source_row_id": source_row_id,
    })


def generate_seed(fixture_path: Path, output_path: Path) -> list[SyntheticSignalExample]:
    journeys = _load_journeys(fixture_path)
    records = [_record_from_journey(journey) for journey in journeys]
    if len(records) != 20:
        raise ValueError(f"Expected 20 fixture rows, found {len(records)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(records_as_jsonl(records), encoding="utf-8")
    return records


def _build_parser():
    parser = argparse.ArgumentParser(description="Emit deterministic JSONL seed from fixture")
    parser.add_argument(
        "--journey-fixture",
        default=str(DEFAULT_FIXTURE_PATH),
        help="Path to fixture module containing JOURNEYS.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output JSONL path for synthetic seed.",
    )
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()

    output_path = Path(args.output)
    fixture_path = Path(args.journey_fixture)

    records = generate_seed(fixture_path, output_path)
    print(f"Synthetic seed emitted: {output_path}")
    print(f"Rows: {len(records)}")
    print(f"Version: {records[0].dataset_version if records else DATASET_VERSION}")


if __name__ == "__main__":
    main()
