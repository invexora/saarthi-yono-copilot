"""Fine-tuning plan/validation scaffold for signal LM (no training execution in phase 1)."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

from .data_schema import DATASET_VERSION, load_records


@dataclass(frozen=True)
class ParsedConfig:
    base_model: str
    output_dir: Path
    dataset_path: Path
    dataset_version: str
    max_seq_length: int
    batch_size: int
    gradient_accumulation_steps: int
    epochs: int
    max_steps: int
    learning_rate: float
    eval_steps: int
    save_steps: int
    logging_steps: int
    warmup_steps: int
    max_grad_norm: float
    seed: int
    model_path_root: Path
    require_dataset_validation: bool
    allow_non_dry_run: bool


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text()) or {}
    except Exception as error:
        # Lightweight fallback for environments without PyYAML or malformed YAML.
        if isinstance(error, ModuleNotFoundError):
            return _fallback_key_value_yaml(path)
        raise


def _fallback_key_value_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current = data
    stack: list[tuple[int, dict[str, Any]]] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        while stack and indent <= stack[-1][0]:
            stack.pop()
            if stack:
                current = stack[-1][1]
            else:
                current = data
        if ":" not in stripped:
            continue
        key, raw = [part.strip() for part in stripped.split(":", 1)]
        if raw:
            value: Any = raw.strip().strip('"')
            if value.lower() in {"true", "false"}:
                value = value.lower() == "true"
            else:
                try:
                    value = int(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        pass
            current[key] = value
        else:
            next_dict: dict[str, Any] = {}
            current[key] = next_dict
            stack.append((indent, current))
            current = next_dict
    return data


def _ensure_int(value: Any, name: str, minimum: int = 1) -> int:
    if not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _ensure_float(value: Any, name: str, minimum: float = 0.0, maximum: float = 1.0) -> float:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            raise TypeError(f"{name} must be numeric")
    elif not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    value = float(value)
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def _ensure_path(value: Any, name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{name} must be a path string")
    return Path(value)


def _validate_path_strategy(config: ParsedConfig) -> None:
    if ".." in str(config.output_dir) or ".." in str(config.model_path_root):
        raise ValueError("model-path strategy rejects directory traversal in output/model_root")

    resolved_root = config.model_path_root.resolve()
    resolved_output = config.output_dir.resolve()
    if resolved_output != resolved_root and not str(resolved_output).startswith(f"{resolved_root}{os.sep}"):
        raise ValueError("output_dir must be under model_path_root for controlled writes")


def _validate_dataset_shape(config: ParsedConfig) -> int:
    rows = load_records(config.dataset_path)
    if not rows:
        raise ValueError("dataset_path must contain at least one row")
    if len(rows) != 20:
        raise ValueError(f"expected 20 rows in synthetic seed, found {len(rows)}")

    wrong_versions = {row.dataset_version for row in rows if row.dataset_version != config.dataset_version}
    if wrong_versions:
        raise ValueError(f"unexpected dataset_version values: {sorted(wrong_versions)}")

    if len({row.source_row_id for row in rows}) != len(rows):
        raise ValueError("source_row_id must be unique")
    return len(rows)


def _validate_budgets(config: ParsedConfig) -> None:
    _ensure_int(config.epochs, "training epochs", minimum=1)
    _ensure_int(config.max_steps, "max_steps", minimum=1)
    if config.max_steps > 50000:
        raise ValueError("max_steps is capped at 50000 in readiness validation")
    _ensure_int(config.batch_size, "batch_size", minimum=1)
    _ensure_int(config.gradient_accumulation_steps, "gradient_accumulation_steps", minimum=1)
    _ensure_int(config.eval_steps, "eval_steps", minimum=1)
    _ensure_int(config.save_steps, "save_steps", minimum=1)
    _ensure_int(config.logging_steps, "logging_steps", minimum=1)
    _ensure_int(config.warmup_steps, "warmup_steps", minimum=0)
    _ensure_float(config.learning_rate, "learning_rate", minimum=0.0, maximum=1.0)
    if not 128 <= config.max_seq_length <= 8192:
        raise ValueError("max_seq_length must be within 128-8192")


def _validate_dataset_exists(config: ParsedConfig) -> None:
    if not config.dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {config.dataset_path}")
    if not config.dataset_path.is_file():
        raise ValueError(f"Dataset path is not a file: {config.dataset_path}")


def load_plan(config_path: Path, data_override: str | None = None, output_override: str | None = None) -> ParsedConfig:
    payload = _load_yaml(config_path)

    if not isinstance(payload, dict):
        raise ValueError("Configuration must be a YAML dictionary")

    base_model = str(payload.get("base", {}).get("model", {}).get("base_model", "")).strip()
    if not base_model:
        raise ValueError("Missing base.model.base_model")

    dataset = payload.get("data", {})
    dataset_path = _ensure_path(dataset.get("dataset_path"), "data.dataset_path")
    dataset_version = str(dataset.get("dataset_version", DATASET_VERSION))
    max_seq_length = _ensure_int(dataset.get("max_seq_length", 1024), "data.max_seq_length", minimum=128)

    training = payload.get("training", {})
    model_path_root = _ensure_path(payload.get("control", {}).get("model_path_root", "backend/ml"), "control.model_path_root")
    output_dir = _ensure_path(training.get("output_dir", "backend/ml/model-runs/signal-detector"), "training.output_dir")
    if output_override:
        output_dir = Path(output_override)

    dataset_path = dataset_path if not data_override else Path(data_override)
    parsed = ParsedConfig(
        base_model=base_model,
        output_dir=output_dir,
        dataset_path=dataset_path,
        dataset_version=dataset_version,
        max_seq_length=max_seq_length,
        batch_size=_ensure_int(training.get("batch_size", 2), "training.batch_size", minimum=1),
        gradient_accumulation_steps=_ensure_int(training.get("gradient_accumulation_steps", 1), "training.gradient_accumulation_steps", minimum=1),
        epochs=_ensure_int(training.get("epochs", 1), "training.epochs", minimum=1),
        max_steps=_ensure_int(training.get("max_steps", 1000), "training.max_steps", minimum=1),
        learning_rate=_ensure_float(training.get("learning_rate", 2e-4), "training.learning_rate", minimum=0.0, maximum=1.0),
        eval_steps=_ensure_int(training.get("eval_steps", 100), "training.eval_steps", minimum=1),
        save_steps=_ensure_int(training.get("save_steps", 100), "training.save_steps", minimum=1),
        logging_steps=_ensure_int(training.get("logging_steps", 50), "training.logging_steps", minimum=1),
        warmup_steps=_ensure_int(training.get("warmup_steps", 0), "training.warmup_steps", minimum=0),
        max_grad_norm=_ensure_float(training.get("max_grad_norm", 1.0), "training.max_grad_norm", minimum=0.0, maximum=10.0),
        seed=_ensure_int(training.get("seed", 42), "training.seed", minimum=1),
        model_path_root=model_path_root,
        require_dataset_validation=bool(payload.get("control", {}).get("require_dataset_validation", True)),
        allow_non_dry_run=bool(payload.get("control", {}).get("allow_non_dry_run", False)),
    )

    _validate_dataset_exists(parsed)
    _validate_dataset_shape(parsed)
    _validate_budgets(parsed)
    _validate_path_strategy(parsed)
    return parsed


def _build_plan(config: ParsedConfig) -> dict[str, Any]:
    return {
        "mode": "dry-run-only",
        "model_path_root": str(config.model_path_root),
        "dataset_path": str(config.dataset_path),
        "dataset_version": config.dataset_version,
        "base_model": config.base_model,
        "output_dir": str(config.output_dir),
        "training": {
            "base_batches_per_step": config.batch_size,
            "gradient_accumulation_steps": config.gradient_accumulation_steps,
            "effective_batch_size": config.batch_size * config.gradient_accumulation_steps,
            "epochs": config.epochs,
            "max_steps": config.max_steps,
            "learning_rate": config.learning_rate,
            "max_seq_length": config.max_seq_length,
            "eval_steps": config.eval_steps,
            "save_steps": config.save_steps,
            "logging_steps": config.logging_steps,
            "seed": config.seed,
        },
        "controls": {
            "require_dataset_validation": config.require_dataset_validation,
            "allow_non_dry_run": config.allow_non_dry_run,
        },
        "preflight_checks": [
            "dataset_shape=20",
            "dataset_schema_valid",
            "no_nonfinite_hyperparams",
            "output_under_model_root",
            "sequence_bounds_checked",
        ],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and plan SLM fine-tune execution")
    parser.add_argument("--config", default=str(Path(__file__).with_name("finetune_config.yaml")))
    parser.add_argument("--data", default=None, help="Optional dataset override")
    parser.add_argument("--output", default=None, help="Optional output directory override")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print run plan only")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    config = load_plan(Path(args.config), args.data, args.output)
    plan = _build_plan(config)

    if not args.dry_run:
        if not config.allow_non_dry_run:
            raise RuntimeError(
                "Non-dry-run execution is intentionally blocked in readiness phase. "
                "Re-run with --dry-run for validated plan and runbook output."
            )
        print("Refusing to execute training. Use --dry-run only.")
        return

    print(json.dumps(plan, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
