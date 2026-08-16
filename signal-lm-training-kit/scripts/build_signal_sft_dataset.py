#!/usr/bin/env python3
"""Build deterministic SFT dataset rows from Saarthi journey fixture or existing JSONL seed."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

KIT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_SEED_FIELDS = {
    "customer_signal": str,
    "persona_context": str,
    "policy_constraints": dict,
    "correct_action": str,
}
VALID_ACTIONS = {"eligible", "support_only", "rejected", "hold", "defer"}
DEFAULT_DATASET_VERSION = "saarthi-signal-synthetic-seed-v1"
LOCAL_DEFAULT_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "test_demo_journey_contract.py"
DEFAULT_SEED_PATH = KIT_ROOT / "data" / "synthetic_signal_sft.jsonl"
DEFAULT_OUTPUT = KIT_ROOT / "data" / "synthetic_signal_sft.jsonl"


def _find_repository_fixtures() -> Path | None:
    candidate = LOCAL_DEFAULT_FIXTURE
    if candidate.exists():
        return candidate
    return None


def _load_fixture_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "JOURNEYS":
                journeys = ast.literal_eval(node.value)
                break
        else:
            continue
        break
    else:
        raise RuntimeError("Could not find JOURNEYS fixture")

    rows: list[dict[str, Any]] = []
    for journey in journeys:
        if not isinstance(journey, (list, tuple)):
            continue
        # Contract tuple in tests: id, segment, customer_signal, signal_category,
        # product_id, delivery_mode, outcome, actionable
        if len(journey) < 8:
            raise ValueError("Malformed JOURNEYS fixture row")
        source_row_id, segment, customer_signal, signal_category, _product_id, delivery_mode, outcome, actionable = journey[:8]
        action = str(outcome).strip() if str(outcome).strip() in VALID_ACTIONS else "support_only"
        prompt = (
            "Classify this customer signal for SBI intervention policy. "
            "Return JSON only with keys: signal_category, recommended_action, rationale.\n\n"
            f"customer_signal: {customer_signal}\n"
            f"segment: {segment}\n"
            f"journey_id: {source_row_id}\n"
            f"delivery_mode: {delivery_mode}\n"
            f"outcome: {outcome}\n"
            f"actionable: {bool(actionable)}\n"
            f"persona_context: {json.dumps({'segment': segment, 'journey_id': source_row_id}, sort_keys=True)}\n"
        )
        completion = json.dumps(
            {
                "signal_category": signal_category,
                "recommended_action": action,
                "rationale": (
                    f"Classify as {signal_category} with policy-aware action {action} "
                    f"based on {segment} context and journey {source_row_id}."
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        rows.append(
            {
                "prompt": prompt,
                "completion": completion,
                "metadata": {
                    "source_row_id": str(source_row_id),
                    "dataset_version": DEFAULT_DATASET_VERSION,
                    "signal_category": signal_category,
                    "correct_action": action,
                    "delivery_mode": delivery_mode,
                    "actionable": bool(actionable),
                },
            }
        )
    if len(rows) != 20:
        raise ValueError(f"Expected 20 fixture rows, found {len(rows)}")
    return rows


def _load_seed_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        payload = json.loads(raw_line)
        for field, field_type in REQUIRED_SEED_FIELDS.items():
            if field not in payload:
                raise ValueError(f"seed row {line_no} missing required field {field}")
            if not isinstance(payload[field], field_type):
                raise TypeError(f"seed row {line_no} field {field} must be {field_type.__name__}")
            if isinstance(payload[field], str) and not payload[field].strip():
                raise ValueError(f"seed row {line_no} has empty {field}")

        if payload["correct_action"] not in VALID_ACTIONS:
            raise ValueError(f"seed row {line_no} has invalid correct_action")

        completion_obj = {
            "signal_category": payload.get("signal_category", "stress"),
            "recommended_action": payload["correct_action"],
            "rationale": payload["rationale"].strip(),
        }
        rows.append(
            {
                "prompt": (
                    "Classify this customer signal for SBI intervention policy. "
                    "Return JSON only with keys: signal_category, recommended_action, rationale.\n\n"
                    f"customer_signal: {payload['customer_signal']}\n"
                    f"persona_context: {payload['persona_context']}\n"
                    f"policy_constraints: {json.dumps(payload['policy_constraints'], sort_keys=True)}\n"
                ),
                "completion": json.dumps(completion_obj, ensure_ascii=False, sort_keys=True),
                "metadata": {
                    "source_row_id": payload.get("source_row_id"),
                    "dataset_version": payload.get("dataset_version", DEFAULT_DATASET_VERSION),
                    "signal_category": payload.get("signal_category"),
                    "correct_action": payload["correct_action"],
                },
            }
        )
    if len(rows) == 0:
        raise ValueError("Seed file is empty")
    return rows


def build_dataset(fixture_path: Path, seed_path: Path | None, output_path: Path) -> list[dict[str, Any]]:
    if seed_path:
        rows = _load_seed_rows(seed_path)
    else:
        rows = _load_fixture_rows(fixture_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return rows


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate SFT-ready prompt/completion JSONL")
    parser.add_argument("--fixture", default=None, help="Optional path to journey fixture module containing JOURNEYS")
    parser.add_argument("--seed-jsonl", default=str(DEFAULT_SEED_PATH), help="Alternative source JSONL seed")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSONL path")
    parser.add_argument("--use-seed", action="store_true", help="Prefer seed-jsonl even if fixture is available")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    output_path = Path(args.output)
    seed_path = None
    fixture_path = Path(args.fixture) if args.fixture else _find_repository_fixtures()

    if args.use_seed:
        seed_path = Path(args.seed_jsonl)
        if not seed_path.exists():
            raise FileNotFoundError(f"seed source not found: {seed_path}")

    elif fixture_path is None:
        fallback_seed = Path(args.seed_jsonl)
        if not fallback_seed.exists():
            raise RuntimeError(
                "No input source found: provide --fixture (JOURNEYS contract) or an existing --seed-jsonl with --use-seed"
            )
        seed_path = fallback_seed
    else:
        if fixture_path.suffix != ".py":
            raise RuntimeError(f"fixture path must be a python file containing JOURNEYS: {fixture_path}")
        if not fixture_path.exists():
            raise RuntimeError(f"fixture path not found: {fixture_path}")

    if seed_path is not None:
        rows = _load_seed_rows(seed_path)
    else:
        rows = _load_fixture_rows(fixture_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    print(f"SFT dataset emitted: {output_path}")
    print(f"Rows: {len(rows)}")
    if rows:
        print(f"Dataset_version: {rows[0]['metadata'].get('dataset_version', DEFAULT_DATASET_VERSION)}")


if __name__ == "__main__":
    main()
