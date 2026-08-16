# Signal LM Training Kit

This folder is an isolated, production-ready training scaffold for the Saarthi signal classifier.
It is intentionally separate from the main application code so current behavior (`rules` mode, APIs, and governance contracts) remains unchanged.

## What this gives you

- A deterministic synthetic dataset converter tied to the canonical 20-case journey contract.
- Reproducible SFT/LoRA fine-tuning pipeline with selectable base model.
- Optional single-batch GPU-first training path.
- Lightweight prompt-inference CLI for quick checkpoint smoke tests.

Also included:

- `signal-lm-training-kit/Makefile` for one-command runbook targets:
  - `make -C . prepare`
  - `make -C . train-dryrun`
  - `make -C . train`
  - `make -C . infer`

## Prerequisites

- NVIDIA GPU + CUDA-enabled PyTorch build.
- A Python 3.10+ environment.
- `transformers`, `peft`, `trl`, `datasets`, `torch`, `bitsandbytes`, `accelerate`.

Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r signal-lm-training-kit/requirements.txt
```

## Dataset preparation

### 1) Build SFT dataset from canonical 20-case fixture

This repo already includes a ready seed at:

```bash
signal-lm-training-kit/data/synthetic_signal_sft.jsonl
```

Use it directly, or regenerate from the canonical fixture if you want a deterministic rebuild:

```bash
python3 signal-lm-training-kit/scripts/build_signal_sft_dataset.py \
  --output signal-lm-training-kit/data/synthetic_signal_sft.jsonl
```

Or one-command:

```bash
make -C . prepare
```

### 2) Use an existing JSONL seed (or any compatible JSONL)

If you already have a JSONL dataset in the same prompt/completion schema:

```bash
python3 signal-lm-training-kit/scripts/build_signal_sft_dataset.py \
  --seed-jsonl /path/to/your_seed.jsonl \
  --use-seed \
  --output signal-lm-training-kit/data/synthetic_signal_sft.jsonl
```

## Configure training

Default config is in:

- `signal-lm-training-kit/configs/default_signal_lm_train.yaml`

You can override values through CLI:

```bash
python3 signal-lm-training-kit/scripts/train_signal_lm.py \
  --config signal-lm-training-kit/configs/default_signal_lm_train.yaml \
  --dataset signal-lm-training-kit/data/synthetic_signal_sft.jsonl \
  --output-dir signal-lm-training-kit/outputs/first-run \
  --base-model meta-llama/Llama-3.1-8B-Instruct
```

### Dry run

Preview resolved plan + validations before running heavy compute:

```bash
python3 signal-lm-training-kit/scripts/train_signal_lm.py \
  --config signal-lm-training-kit/configs/default_signal_lm_train.yaml \
  --dataset signal-lm-training-kit/data/synthetic_signal_sft.jsonl \
  --dry-run
```

## Inference smoke test

Use any exported checkpoint:

```bash
python3 signal-lm-training-kit/scripts/infer_signal_lm.py \
  --checkpoint signal-lm-training-kit/outputs/first-run/final \
  --signal "DEBT_OPPORTUNITY — card interest is above threshold"
```

## Model swap support

Change the base model by editing config or CLI override:

```bash
python3 signal-lm-training-kit/scripts/train_signal_lm.py \
  --config signal-lm-training-kit/configs/default_signal_lm_train.yaml \
  --base-model meta-llama/Llama-3.1-70B-Instruct \
  --dataset signal-lm-training-kit/data/synthetic_signal_sft.jsonl \
  --output-dir signal-lm-training-kit/outputs/run-llama70b
```

## Scope guarantees

- This folder prepares and runs training/inference tooling only.
- It does not modify runtime application decision behavior.
- External users can replace datasets and base models without touching backend code.

## Recommended governance handoff

1. Keep all model artifacts under `signal-lm-training-kit/outputs/*`.
2. After each run, archive the generated `config_resolved.json` and training logs.
3. Only promote checkpoints after policy/legal approval.
