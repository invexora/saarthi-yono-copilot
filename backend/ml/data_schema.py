"""Typed schema helpers for synthetic signal detection training data."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from pathlib import Path


DATASET_VERSION = "saarthi-signal-synthetic-seed-v1"


@dataclass(frozen=True)
class SyntheticSignalExample:
    customer_signal: str
    persona_context: str
    policy_constraints: dict[str, Any]
    correct_action: str
    rationale: str
    dataset_version: str = DATASET_VERSION
    signal_category: str | None = None
    notes: str | None = None
    source_row_id: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


SCHEMA_FIELDS = {
    "customer_signal": str,
    "persona_context": str,
    "policy_constraints": dict,
    "correct_action": str,
    "rationale": str,
}

OPTIONAL_FIELDS = {
    "dataset_version": str,
    "signal_category": str,
    "notes": str,
    "source_row_id": str,
}


def _as_type(value: Any, expected_type: type):
    if not isinstance(value, expected_type):
        raise TypeError(f"Expected {expected_type.__name__}, got {type(value).__name__}")


def validate_record(record: dict[str, Any]) -> SyntheticSignalExample:
    for field, field_type in SCHEMA_FIELDS.items():
        if field not in record:
            raise ValueError(f"Missing required field: {field}")
        _as_type(record[field], field_type)
        value = record[field]
        if isinstance(value, str):
            if not value.strip():
                raise ValueError(f"Field {field} must be non-empty")
        elif isinstance(value, dict) and not value:
            raise ValueError(f"Field {field} must be non-empty")

    for field, field_type in OPTIONAL_FIELDS.items():
        if field in record and record[field] is not None and not isinstance(record[field], field_type):
            raise TypeError(f"Field {field} must be {field_type.__name__}")

    if record["correct_action"] not in {"eligible", "support_only", "rejected", "hold", "defer"}:
        raise ValueError("Unsupported correct_action value")

    dataset_version = str(record.get("dataset_version", DATASET_VERSION)).strip()
    if not dataset_version:
        raise ValueError("dataset_version must be non-empty")

    return SyntheticSignalExample(
        customer_signal=str(record["customer_signal"]).strip(),
        persona_context=str(record["persona_context"]).strip(),
        policy_constraints=record["policy_constraints"],
        correct_action=str(record["correct_action"]).strip(),
        rationale=str(record["rationale"]).strip(),
        dataset_version=dataset_version,
        signal_category=(str(record["signal_category"]).strip() if record.get("signal_category") else None),
        notes=(str(record["notes"]).strip() if record.get("notes") else None),
        source_row_id=(str(record["source_row_id"]).strip() if record.get("source_row_id") else None),
    )


def load_records(path: str | Path) -> list[SyntheticSignalExample]:
    """Load and validate every JSONL record in ``path``."""
    schema_path = Path(path)
    if not schema_path.exists():
        raise FileNotFoundError(f"seed file not found: {schema_path}")

    rows: list[SyntheticSignalExample] = []
    for line_number, raw_line in enumerate(schema_path.read_text().splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            import json
            payload = json.loads(raw_line)
            rows.append(validate_record(payload))
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid record at line {line_number}: {error}") from error

    return rows


def records_as_jsonl(rows: list[SyntheticSignalExample]) -> str:
    import json

    return "\n".join(json.dumps(row.to_record(), ensure_ascii=False, sort_keys=True) for row in rows) + "\n"
