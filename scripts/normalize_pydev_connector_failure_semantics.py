#!/usr/bin/env python3
"""Normalize pydev OffloadingConnector failure-semantics artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kv_vllm_arbiter.pydev_connector_normalize import (  # noqa: E402
    aggregate_normalized,
    collect_provenance,
    normalize_summary,
    render_aggregate_markdown,
    write_json,
    write_jsonl,
)


DEFAULT_PARENT_DIR = ROOT.parents[1]
DEFAULT_VLLM_SOURCE = Path("/home/krooksn/ai/runtimes/vllm/repo")
DEFAULT_RUNNER = "/home/krooksn/ai/bin/vllm-pydev-python"
DEFAULT_ARTIFACT_DIR = ROOT / "artifacts" / "pydev_connector_failure_semantics"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--parent-dir", type=Path, default=DEFAULT_PARENT_DIR)
    parser.add_argument("--repo-dir", type=Path, default=ROOT)
    parser.add_argument("--vllm-source", type=Path, default=DEFAULT_VLLM_SOURCE)
    parser.add_argument("--runner", default=DEFAULT_RUNNER)
    parser.add_argument(
        "--run-set-id",
        default=None,
        help="Optional run-set id to stamp on normalized rows.",
    )
    parser.add_argument(
        "--aggregate-prefix",
        default="normalized",
        help="Output prefix for aggregate files inside artifact-dir.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    provenance = collect_provenance(
        parent_dir=args.parent_dir,
        artifact_dir=args.repo_dir,
        vllm_source=args.vllm_source,
        runner_path=args.runner,
    )
    summary_paths = sorted(args.artifact_dir.rglob("summary.json"))
    rows = []
    for summary_path in summary_paths:
        if summary_path.name != "summary.json":
            continue
        row = normalize_summary(
            summary_path,
            provenance=provenance,
            run_set_id=args.run_set_id,
        )
        rows.append(row)
        write_json(summary_path.with_name("normalized_summary.json"), row)

    aggregate = aggregate_normalized(rows)
    write_json(args.artifact_dir / f"{args.aggregate_prefix}_aggregate.json", aggregate)
    write_jsonl(args.artifact_dir / f"{args.aggregate_prefix}_summaries.jsonl", rows)
    (args.artifact_dir / f"{args.aggregate_prefix}_aggregate.md").write_text(
        render_aggregate_markdown(aggregate),
        encoding="utf-8",
    )
    print(
        f"normalized {len(rows)} summaries under {args.artifact_dir} "
        f"to {args.aggregate_prefix}_aggregate.json"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
