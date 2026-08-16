#!/usr/bin/env python3
"""Train (or dry-run validate) a LoRA SFT signal LM from prepared JSONL."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


KIT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ResolvedConfig:
    run_name: str
    model: str
    revision: str
    trust_remote_code: bool
    bf16: bool
    fp16: bool
    enable_4bit: bool
    enable_8bit: bool
    bnb_quant_type: str
    bnb_compute_dtype: str
    bnb_double_quant: bool
    dataset_path: Path
    prompt_field: str
    completion_field: str
    text_field: str
    max_seq_length: int
    split: str
    output_dir: Path
    train_batch_size: int
    eval_batch_size: int
    gradient_accumulation_steps: int
    num_train_epochs: int
    max_steps: int
    learning_rate: float
    warmup_steps: int
    max_grad_norm: float
    weight_decay: float
    lr_scheduler: str
    eval_steps: int
    logging_steps: int
    save_steps: int
    seed: int
    optim: str
    ddp_timeout_seconds: int
    lora_rank: int
    lora_alpha: int
    lora_dropout: float
    lora_target_modules: list[str]
    lora_modules_to_save: list[str]
    lora_bias: str
    validate_required_rows: int
    allow_cpu: bool
    base_model_override: str | None = None


def _ensure_int(value: Any, field: str, minimum: int = 1) -> int:
    if not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    if value < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    return value


def _ensure_float(value: Any, field: str, minimum: float = 0.0, maximum: float = 1.0) -> float:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError as error:
            raise TypeError(f"{field} must be numeric") from error
    elif isinstance(value, int):
        value = float(value)
    elif not isinstance(value, float):
        raise TypeError(f"{field} must be numeric")
    if not (minimum <= value <= maximum):
        raise ValueError(f"{field} must be in [{minimum}, {maximum}]")
    return value


def _ensure_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field} must be a non-empty string")
    return value.strip()


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config(path: Path, overrides: dict[str, Any]) -> ResolvedConfig:
    payload = _load_yaml(path)
    if not isinstance(payload, dict):
        raise ValueError("Config root must be a YAML object")

    dataset_cfg = payload.get("dataset", {})
    base_cfg = payload.get("base", {})
    training_cfg = payload.get("training", {})
    lora_cfg = payload.get("lora", {})
    control_cfg = payload.get("control", {})

    model = _ensure_str(overrides.get("base_model") or base_cfg.get("model", "meta-llama/Llama-3.1-8B-Instruct"), "base.model")
    dataset_path = Path(_ensure_str(dataset_cfg.get("path", "data/synthetic_signal_sft.jsonl"), "dataset.path"))
    if not dataset_path.is_absolute():
        dataset_path = (KIT_ROOT / dataset_path).resolve()
    output_dir = Path(overrides.get("output_dir") or training_cfg.get("output_dir", "outputs/default-run"))
    if not output_dir.is_absolute():
        output_dir = (KIT_ROOT / output_dir).resolve()

    run_name = _ensure_str(payload.get("run_name", "saarthi-signal-lm"), "run_name")

    precision = base_cfg.get("precision", {})
    quant = base_cfg.get("quantization", {})

    cfg = ResolvedConfig(
        run_name=run_name,
        model=model,
        revision=_ensure_str(base_cfg.get("revision", "main"), "base.revision"),
        trust_remote_code=bool(base_cfg.get("trust_remote_code", False)),
        bf16=bool(precision.get("bf16", True)),
        fp16=bool(precision.get("fp16", False)),
        enable_4bit=bool(quant.get("enable_4bit", True)),
        enable_8bit=bool(quant.get("enable_8bit", False)),
        bnb_quant_type=str(quant.get("bnb_4bit_quant_type", "nf4")),
        bnb_compute_dtype=str(quant.get("bnb_4bit_compute_dtype", "bfloat16")),
        bnb_double_quant=bool(quant.get("bnb_4bit_use_double_quant", True)),
        dataset_path=dataset_path,
        prompt_field=_ensure_str(dataset_cfg.get("prompt_field", "prompt"), "dataset.prompt_field"),
        completion_field=_ensure_str(dataset_cfg.get("completion_field", "completion"), "dataset.completion_field"),
        text_field=_ensure_str(dataset_cfg.get("text_field", "text"), "dataset.text_field"),
        max_seq_length=_ensure_int(dataset_cfg.get("max_seq_length", 1024), "dataset.max_seq_length", minimum=64),
        split=_ensure_str(dataset_cfg.get("split", "train"), "dataset.split"),
        output_dir=output_dir,
        train_batch_size=_ensure_int(training_cfg.get("train_batch_size", 1), "training.train_batch_size", minimum=1),
        eval_batch_size=_ensure_int(training_cfg.get("eval_batch_size", 1), "training.eval_batch_size", minimum=1),
        gradient_accumulation_steps=_ensure_int(
            training_cfg.get("gradient_accumulation_steps", 8),
            "training.gradient_accumulation_steps",
            minimum=1,
        ),
        num_train_epochs=_ensure_int(training_cfg.get("num_train_epochs", 1), "training.num_train_epochs", minimum=1),
        max_steps=_ensure_int(training_cfg.get("max_steps", 1200), "training.max_steps", minimum=1),
        learning_rate=_ensure_float(training_cfg.get("learning_rate", 2e-4), "training.learning_rate", minimum=1e-7, maximum=1.0),
        warmup_steps=_ensure_int(training_cfg.get("warmup_steps", 0), "training.warmup_steps", minimum=0),
        max_grad_norm=_ensure_float(training_cfg.get("max_grad_norm", 1.0), "training.max_grad_norm", minimum=0.0, maximum=10.0),
        weight_decay=_ensure_float(training_cfg.get("weight_decay", 0.01), "training.weight_decay", minimum=0.0, maximum=10.0),
        lr_scheduler=_ensure_str(training_cfg.get("lr_scheduler", "cosine"), "training.lr_scheduler"),
        eval_steps=_ensure_int(training_cfg.get("eval_steps", 200), "training.eval_steps", minimum=1),
        logging_steps=_ensure_int(training_cfg.get("logging_steps", 50), "training.logging_steps", minimum=1),
        save_steps=_ensure_int(training_cfg.get("save_steps", 200), "training.save_steps", minimum=1),
        seed=_ensure_int(training_cfg.get("seed", 42), "training.seed", minimum=1),
        optim=_ensure_str(training_cfg.get("optim", "paged_adamw_8bit"), "training.optim"),
        ddp_timeout_seconds=_ensure_int(training_cfg.get("ddp_timeout_seconds", 7200), "training.ddp_timeout_seconds", minimum=60),
        lora_rank=_ensure_int(lora_cfg.get("rank", 16), "lora.rank", minimum=1),
        lora_alpha=_ensure_int(lora_cfg.get("alpha", 32), "lora.alpha", minimum=1),
        lora_dropout=_ensure_float(lora_cfg.get("dropout", 0.05), "lora.dropout", minimum=0.0, maximum=1.0),
        lora_target_modules=list(lora_cfg.get("target_modules", ["q_proj", "k_proj", "v_proj", "o_proj"])),
        lora_modules_to_save=list(lora_cfg.get("modules_to_save", ["lm_head", "embed_tokens"])),
        lora_bias=_ensure_str(lora_cfg.get("bias", "none"), "lora.bias"),
        validate_required_rows=_ensure_int(control_cfg.get("validate_required_rows", 20), "control.validate_required_rows", minimum=0),
        allow_cpu=bool(control_cfg.get("allow_cpu", False)),
        base_model_override=overrides.get("base_model"),
    )

    return cfg


def _validate_dataset(cfg: ResolvedConfig) -> int:
    if not cfg.dataset_path.exists():
        raise FileNotFoundError(f"dataset file missing: {cfg.dataset_path}")
    rows = [line for line in cfg.dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) < 1:
        raise ValueError("dataset is empty")
    if cfg.validate_required_rows > 0 and len(rows) != cfg.validate_required_rows:
        raise ValueError(
            f"expected exactly {cfg.validate_required_rows} rows (canonical seed), found {len(rows)}"
        )
    for idx, raw_line in enumerate(rows[:3], start=1):
        payload = json.loads(raw_line)
        if cfg.prompt_field not in payload or cfg.completion_field not in payload:
            raise ValueError(f"dataset row {idx} missing prompt/completion")
        if not isinstance(payload[cfg.prompt_field], str) or not isinstance(payload[cfg.completion_field], str):
            raise ValueError(f"dataset row {idx} has non-string prompt/completion")
    return len(rows)


def _build_plan(cfg: ResolvedConfig, dataset_rows: int) -> dict[str, Any]:
    effective_batch = cfg.train_batch_size * cfg.gradient_accumulation_steps
    return {
        "mode": "ready",
        "run_name": cfg.run_name,
        "base_model": cfg.model,
        "model_revision": cfg.revision,
        "dataset_path": str(cfg.dataset_path),
        "dataset_rows": dataset_rows,
        "output_dir": str(cfg.output_dir),
        "quantization": {
            "enable_4bit": cfg.enable_4bit,
            "enable_8bit": cfg.enable_8bit,
            "bnb_4bit_quant_type": cfg.bnb_quant_type,
            "bnb_4bit_compute_dtype": cfg.bnb_compute_dtype,
            "bnb_4bit_use_double_quant": cfg.bnb_double_quant,
        },
        "training": {
            "max_seq_length": cfg.max_seq_length,
            "train_batch_size": cfg.train_batch_size,
            "gradient_accumulation_steps": cfg.gradient_accumulation_steps,
            "effective_batch_size": effective_batch,
            "num_train_epochs": cfg.num_train_epochs,
            "max_steps": cfg.max_steps,
            "learning_rate": cfg.learning_rate,
            "warmup_steps": cfg.warmup_steps,
            "eval_steps": cfg.eval_steps,
            "save_steps": cfg.save_steps,
            "logging_steps": cfg.logging_steps,
            "seed": cfg.seed,
            "optimizer": cfg.optim,
            "bf16": cfg.bf16,
            "fp16": cfg.fp16,
        },
        "lora": {
            "rank": cfg.lora_rank,
            "alpha": cfg.lora_alpha,
            "dropout": cfg.lora_dropout,
            "target_modules": cfg.lora_target_modules,
            "modules_to_save": cfg.lora_modules_to_save,
        },
        "controls": [
            f"dataset_validation_rows == {cfg.validate_required_rows}",
            "gpu_check",
            "schema_contract_check",
            "path_checks",
        ],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train signal LM using LoRA")
    parser.add_argument("--config", default=str(KIT_ROOT / "configs" / "default_signal_lm_train.yaml"))
    parser.add_argument("--dataset", default=None, help="Override training dataset path")
    parser.add_argument("--output-dir", default=None, help="Override output directory")
    parser.add_argument("--base-model", default=None, help="Pick a different base model")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def run_training(cfg: ResolvedConfig, dataset_rows: int) -> None:
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    if not torch.cuda.is_available() and not cfg.allow_cpu:
        raise RuntimeError(
            "No CUDA device found. Set control.allow_cpu=true in config to run on CPU."
        )

    quant_config = None
    if cfg.enable_4bit:
        compute_dtype = torch.bfloat16
        if cfg.bnb_compute_dtype == "float16":
            compute_dtype = torch.float16
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=cfg.bnb_quant_type,
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=cfg.bnb_double_quant,
        )
    elif cfg.enable_8bit:
        quant_config = BitsAndBytesConfig(load_in_8bit=True)

    tokenizer = AutoTokenizer.from_pretrained(cfg.model, revision=cfg.revision)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        cfg.model,
        revision=cfg.revision,
        quantization_config=quant_config,
        trust_remote_code=cfg.trust_remote_code,
        device_map="auto",
        torch_dtype=(
            torch.bfloat16
            if cfg.bf16
            else (torch.float16 if cfg.fp16 else None)
        ),
    )

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=cfg.lora_rank,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
        target_modules=cfg.lora_target_modules,
        bias=cfg.lora_bias,
        modules_to_save=cfg.lora_modules_to_save,
    )
    model = get_peft_model(model, lora_config)

    raw_dataset = load_dataset("json", data_files={cfg.split: str(cfg.dataset_path)})[cfg.split]

    def render_record(record: dict[str, Any]) -> dict[str, str]:
        prompt = record[cfg.prompt_field]
        completion = record[cfg.completion_field]
        return {cfg.text_field: prompt + "\n" + completion + "\n"}

    dataset = raw_dataset.map(render_record, remove_columns=raw_dataset.column_names)

    train_cfg = SFTConfig(
        output_dir=str(cfg.output_dir),
        dataset_text_field=cfg.text_field,
        max_seq_length=cfg.max_seq_length,
        max_steps=cfg.max_steps,
        num_train_epochs=cfg.num_train_epochs,
        per_device_train_batch_size=cfg.train_batch_size,
        per_device_eval_batch_size=cfg.eval_batch_size,
        gradient_accumulation_steps=cfg.gradient_accumulation_steps,
        optim=cfg.optim,
        weight_decay=cfg.weight_decay,
        learning_rate=cfg.learning_rate,
        warmup_steps=cfg.warmup_steps,
        max_grad_norm=cfg.max_grad_norm,
        lr_scheduler_type=cfg.lr_scheduler,
        evaluation_strategy="steps",
        eval_steps=cfg.eval_steps,
        logging_steps=cfg.logging_steps,
        save_strategy="steps",
        save_steps=cfg.save_steps,
        bf16=cfg.bf16,
        fp16=cfg.fp16,
        seed=cfg.seed,
        report_to="none",
        run_name=cfg.run_name,
        ddp_timeout=cfg.ddp_timeout_seconds,
        logging_dir=str(cfg.output_dir / "logs"),
    )

    trainer = SFTTrainer(
        model=model,
        args=train_cfg,
        train_dataset=dataset,
        tokenizer=tokenizer,
        eval_dataset=dataset.select(range(min(2, max(0, dataset_rows)))) if dataset_rows >= 2 else None,
    )

    trainer.train()
    trainer.save_model(str(cfg.output_dir / "final"))
    tokenizer.save_pretrained(str(cfg.output_dir / "final"))
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    (cfg.output_dir / "config_resolved.json").write_text(
        json.dumps(_build_plan(cfg, dataset_rows), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Training finished. Model saved to: {cfg.output_dir / 'final'}")


def main() -> None:
    args = _build_parser().parse_args()
    cfg = load_config(Path(args.config), {"base_model": args.base_model, "output_dir": args.output_dir})
    if args.dataset:
        cfg = cfg.__class__(**{**cfg.__dict__, "dataset_path": Path(args.dataset)})
    dataset_rows = _validate_dataset(cfg)
    plan = _build_plan(cfg, dataset_rows)

    print(json.dumps(plan, sort_keys=True, indent=2))
    if args.dry_run:
        print("Dry-run complete.")
        return

    run_training(cfg, dataset_rows)


if __name__ == "__main__":
    main()
