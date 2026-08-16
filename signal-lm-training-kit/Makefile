.PHONY: prepare train train-dryrun infer

PYTHON ?= python3
KIT_DIR := signal-lm-training-kit
CONFIG := $(KIT_DIR)/configs/default_signal_lm_train.yaml
DATASET := $(KIT_DIR)/data/synthetic_signal_sft.jsonl
OUTDIR ?= $(KIT_DIR)/outputs/quick-start
MODEL ?= meta-llama/Llama-3.1-8B-Instruct
SIGNAL ?= "DEBT_OPPORTUNITY — card interest is above threshold"

prepare:
	$(PYTHON) $(KIT_DIR)/scripts/build_signal_sft_dataset.py --output $(DATASET)

train-dryrun:
	$(PYTHON) $(KIT_DIR)/scripts/train_signal_lm.py --config $(CONFIG) --dataset $(DATASET) --output-dir $(OUTDIR) --base-model $(MODEL) --dry-run

train:
	$(PYTHON) $(KIT_DIR)/scripts/train_signal_lm.py --config $(CONFIG) --dataset $(DATASET) --output-dir $(OUTDIR) --base-model $(MODEL)

infer:
	$(PYTHON) $(KIT_DIR)/scripts/infer_signal_lm.py --checkpoint $(OUTDIR)/final --signal $(SIGNAL)
