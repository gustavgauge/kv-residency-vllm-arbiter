#!/usr/bin/env python3
"""Summarize a native active/resident KV telemetry JSONL trace."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kv_vllm_arbiter.trace_summary import (  # noqa: E402
    format_native_harm_markdown,
    load_jsonl,
    summarize_native_harm,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "jsonl",
        type=Path,
        nargs="?",
        default=ROOT
        / "artifacts"
        / "native_blockpool"
        / "native_blockpool_60_70_80.jsonl",
    )
    parser.add_argument("--markdown", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = summarize_native_harm(load_jsonl(args.jsonl))
    if args.markdown:
        print(format_native_harm_markdown(summary))
    else:
        import json

        print(json.dumps(summary.to_record(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
