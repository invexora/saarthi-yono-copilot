# SLM Readiness Roadmap (Detection Layer)

## Current State

- Signal detection defaults to `rules` mode and remains unchanged for customer flow behavior.
- A model-backed `ModelSignalDetector` path is available behind `SAARTHI_SIGNAL_DETECTION_MODE=model`.
- Rule evidence contract is preserved (`category`, `confidence`, `model_id`, `model_version`, `feature_schema_version`, `reason_codes`, `input_digest`, `evaluation_id`, `evaluation_status`).
- Synthetic seed generation uses the canonical 20-case fixture from `tests/test_demo_journey_contract.py`.
- Fine-tuning execution is not performed in this phase; `--dry-run` provides validated planning output only.

## What is Built Now

1. **Architecture / wiring complete**
   - `backend/signal_detection.py` includes `ModelSignalDetector` and `create_signal_detector` branch for `model` mode.
   - `backend/settings.py` supports new model-mode vars:
     - `SAARTHI_SIGNAL_DETECTION_MODE`
     - `SAARTHI_SIGNAL_MODEL_PATH`
     - `SAARTHI_SIGNAL_FINETUNE_BASE_MODEL`
     - `SAARTHI_SIGNAL_DETECTION_MODEL_CONFIG`
     - `SAARTHI_SIGNAL_DETECTION_FINETUNE_ROOT`
   - `backend/.` governance endpoint `/api/v1/governance/signal-model` returns pending status when model checkpoint is unavailable.

2. **Synthetic corpus and schema**
   - `backend/ml/data_schema.py`: typed schema and row validator for seed rows.
   - `backend/ml/generate_synthetic_dataset.py`: writes `backend/data/synthetic_training_seed.jsonl` deterministically from 20 canonical fixture rows.

3. **Fine-tune scaffold (deferred execution)**
   - `backend/ml/finetune.py`: validates config, model path strategy, dataset shape/schema, and training bounds.
   - `backend/ml/finetune_config.yaml`: default base-model and training plan placeholders.
   - Non-dry-run execution is guarded off.

4. **Evaluation scaffold**
   - `backend/ml/evaluate.py`: baseline category metrics and policy-compatibility summary from synthetic seed.
   - Warns explicitly when no checkpoint is available for model mode.

## What Is Scaffolded but Not Live

- Actual checkpoint loading and inference runtime.
- Full `transformers`/`peft`/`trl` execution with approved compute budget.
- Formal rollout activation across live customer paths.

## Blockers

- Approved representative production data access from SBI for privacy-safe fine-tuning and validation.
- Signed artifact and approval sign-off for model checkpoint promotion.
- Runtime resource approval for large-model training.

## Timeline After Data Approval

1. Populate seed and config review.
2. Run `backend/ml/finetune.py --dry-run` and archive output.
3. Add approved training compute and remove readiness execution guard.
4. Run first deterministic training job and produce checkpoint under `signal_detection_mode=model`.
5. Re-run evaluation with real checkpoint and switch rollout controls after governance sign-off.
6. Open model mode for controlled production-like shadow evaluation.

## Readiness statement

Architecture/integration ready; training is gated on approved representative data access.
