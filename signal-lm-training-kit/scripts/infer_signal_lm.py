#!/usr/bin/env python3
"""Run inference against a trained signal LM checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Signal LM inference helper")
    parser.add_argument("--checkpoint", required=True, help="Fine-tuned checkpoint directory")
    parser.add_argument("--signal", required=True, help="Raw customer signal text")
    parser.add_argument("--max-new-tokens", type=int, default=180)
    parser.add_argument("--temperature", type=float, default=0.1)
    return parser


def build_prompt(signal: str) -> str:
    return (
        "Classify this customer signal. Return JSON with keys: signal_category, recommended_action, rationale.\n\n"
        f"customer_signal: {signal}\n"
        "Output format: {\"signal_category\": str, \"recommended_action\": str, \"rationale\": str}\n"
    )


def main() -> None:
    args = _build_parser().parse_args()
    ckpt = Path(args.checkpoint)
    if not ckpt.exists():
        raise FileNotFoundError(f"checkpoint not found: {ckpt}")

    model_id = str(ckpt)
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=dtype, device_map="auto")

    gen = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
    )

    prompt = build_prompt(args.signal)
    generated = gen(
        prompt,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        do_sample=args.temperature > 0,
        pad_token_id=tokenizer.eos_token_id,
    )[0]["generated_text"]

    response = generated[len(prompt) :].strip()
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        parsed = {"raw": response}

    print(json.dumps({"model": model_id, "prompt": signal_short(args.signal), "response": parsed}, indent=2))


def signal_short(signal: str) -> str:
    return signal[:120] if len(signal) > 120 else signal


if __name__ == "__main__":
    main()
