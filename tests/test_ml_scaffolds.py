import json
import tempfile
import unittest
from pathlib import Path

from backend.ml.data_schema import DATASET_VERSION, load_records, validate_record
from backend.ml.finetune import _build_plan, load_plan
from backend.ml.generate_synthetic_dataset import DEFAULT_FIXTURE_PATH, generate_seed


class DataSchemaScaffoldTests(unittest.TestCase):
    def test_validate_record_rejects_missing_and_empty_fields(self):
        invalid_rows = [
            {},
            {"customer_signal": "", "persona_context": "{}", "policy_constraints": {}, "correct_action": "eligible", "rationale": "x"},
        ]

        with self.assertRaisesRegex(ValueError, "Missing required field"):
            validate_record(invalid_rows[0])
        with self.assertRaisesRegex(ValueError, "must be non-empty"):
            validate_record(invalid_rows[1])

    def test_validate_record_rejects_invalid_action(self):
        row = {
            "customer_signal": "tax_FRICTION",
            "persona_context": '{"segment": "corporate"}',
            "policy_constraints": {"segment": "corporate", "outcome": "eligible"},
            "correct_action": "invalid_action",
            "rationale": "test",
        }
        with self.assertRaisesRegex(ValueError, "Unsupported correct_action"):
            validate_record(row)


class SyntheticSeedScaffoldTests(unittest.TestCase):
    def test_generate_seed_is_deterministic_and_20_rows(self):
        with tempfile.TemporaryDirectory() as workspace:
            workspace_path = Path(workspace)
            first_output = workspace_path / "seed-first.jsonl"
            second_output = workspace_path / "seed-second.jsonl"

            first = generate_seed(DEFAULT_FIXTURE_PATH, first_output)
            second = generate_seed(DEFAULT_FIXTURE_PATH, second_output)

            self.assertEqual(len(first), 20)
            self.assertEqual(len(second), 20)
            self.assertEqual(first_output.read_text(), second_output.read_text())
            self.assertEqual(first, second)
            self.assertEqual({row.dataset_version for row in first}, {DATASET_VERSION})
            self.assertTrue(all(row.source_row_id for row in first))


class FineTuneScaffoldTests(unittest.TestCase):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    SEED_PATH = REPO_ROOT / "backend" / "data" / "synthetic_training_seed.jsonl"

    def _write_config(self, dataset_path: Path, output_dir: Path, workspace: Path) -> Path:
        config_path = workspace / "finetune_config.yaml"
        root = output_dir.parent
        config_text = f"""base:\n  model:\n    base_model: \"meta-llama/Llama-3.1-8B-Instruct\"\n\ndata:\n  dataset_path: \"{dataset_path}\"\n  dataset_version: \"{DATASET_VERSION}\"\n  max_seq_length: 1024\n\ntraining:\n  output_dir: \"{output_dir}\"\n  batch_size: 2\n  gradient_accumulation_steps: 4\n  epochs: 2\n  max_steps: 1200\n  eval_steps: 200\n  logging_steps: 50\n  save_steps: 200\n  warmup_steps: 100\n  learning_rate: 2e-4\n  max_grad_norm: 1.0\n  seed: 42\n\ncontrol:\n  model_path_root: \"{root}\"\n  allow_non_dry_run: false\n  require_dataset_validation: true\n  require_budget_validation: true\n"""
        config_path.write_text(config_text, encoding="utf-8")
        return config_path

    def test_load_plan_generates_dry_run_plan_for_valid_seed(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            output_dir = root / "signal-detector"
            output_dir.mkdir(parents=True, exist_ok=True)
            config_path = self._write_config(self.SEED_PATH, output_dir, Path(workspace))

            parsed = load_plan(config_path)
            plan = _build_plan(parsed)

            self.assertEqual(plan["mode"], "dry-run-only")
            self.assertEqual(plan["training"]["epochs"], 2)
            self.assertEqual(plan["training"]["max_steps"], 1200)
            self.assertIn("dataset_schema_valid", plan["preflight_checks"])
            self.assertEqual(plan["controls"]["allow_non_dry_run"], False)

    def test_load_plan_fails_on_malformed_seed_rows(self):
        base_rows = load_records(self.SEED_PATH)
        bad_rows = [record.to_record() for record in base_rows]
        bad_rows[0]["correct_action"] = "invalid_action"
        with tempfile.TemporaryDirectory(prefix="saarthi-bad-seed-") as seed_workspace:
            malformed_path = Path(seed_workspace) / "seed-bad.jsonl"
            malformed_path.write_text("\n".join(json.dumps(row) for row in bad_rows) + "\n", encoding="utf-8")

            with tempfile.TemporaryDirectory() as workspace:
                output_dir = Path(workspace) / "signal-detector"
                output_dir.mkdir(parents=True, exist_ok=True)
                config_path = self._write_config(malformed_path, output_dir, Path(workspace))
                with self.assertRaisesRegex(ValueError, "Unsupported correct_action"):
                    load_plan(config_path)


if __name__ == "__main__":
    unittest.main()
