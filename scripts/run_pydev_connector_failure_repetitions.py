#!/usr/bin/env python3
"""Run repeated patched pydev OffloadingConnector failure-semantics scenarios."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
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


DEFAULT_OUT_DIR = ROOT / "artifacts" / "pydev_connector_failure_semantics"
DEFAULT_PARENT_DIR = ROOT.parents[1]
DEFAULT_VLLM_SOURCE = (
    Path(os.environ["VLLM_KV_RESIDENCY_VLLM_SOURCE"]).expanduser()
    if os.environ.get("VLLM_KV_RESIDENCY_VLLM_SOURCE")
    else None
)
DEFAULT_RUNNER = os.environ.get("VLLM_AUDIT_PYTHON")
DEFAULT_TARGETS = {
    "success_no_event_path": 30,
    "success_path": 30,
    "ordinary_offload_no_claim": 10,
    "claimed_load_failure": 30,
    "wrong_claim_failure": 10,
    "unclaimed_load_failure": 10,
    "fallback_recompute": 10,
    "generic_counter_only": 1,
    "multi_claim_targeted_failure": 3,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--parent-dir", type=Path, default=DEFAULT_PARENT_DIR)
    parser.add_argument("--repo-dir", type=Path, default=ROOT)
    parser.add_argument(
        "--vllm-source",
        type=Path,
        default=DEFAULT_VLLM_SOURCE,
        help=(
            "Optional patched vLLM checkout used for sys.path and provenance. "
            "Defaults to VLLM_KV_RESIDENCY_VLLM_SOURCE when set."
        ),
    )
    parser.add_argument(
        "--runner",
        default=DEFAULT_RUNNER,
        help=(
            "Python executable that imports the patched vLLM connector mechanism. "
            "Defaults to VLLM_AUDIT_PYTHON."
        ),
    )
    parser.add_argument("--run-set-id", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-model-len", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--gpu-memory-utilization", type=float, default=None)
    parser.add_argument("--kv-cache-memory-bytes", type=int, default=None)
    parser.add_argument(
        "--scenario",
        action="append",
        choices=sorted(DEFAULT_TARGETS),
        help="Scenario to run. May be repeated. Default runs all target scenarios.",
    )
    parser.add_argument(
        "--count",
        action="append",
        default=[],
        metavar="SCENARIO=N",
        help="Override one scenario repetition count.",
    )
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop after the first non-zero scenario subprocess.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_external_inputs(args)
    run_set_id = args.run_set_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_root = args.out_dir / "repetitions" / run_set_id
    run_root.mkdir(parents=True, exist_ok=True)
    targets = _targets(args)
    provenance = collect_provenance(
        parent_dir=args.parent_dir,
        artifact_dir=args.repo_dir,
        vllm_source=args.vllm_source,
        runner_path=args.runner,
    )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_set_id": run_set_id,
        "targets": targets,
        "runner": args.runner,
        "vllm_source": str(args.vllm_source) if args.vllm_source is not None else None,
        "runs": [],
    }
    rows = []
    scenario_script = ROOT / "scripts" / "run_pydev_connector_failure_semantics.py"
    exit_code = 0

    for scenario, count in targets.items():
        for repetition in range(1, count + 1):
            repetition_id = f"rep-{repetition:03d}"
            run_id = f"pydev-connector-failure:{scenario}:{repetition_id}"
            raw_out_dir = run_root / scenario / repetition_id
            log_path = raw_out_dir / "run.log"
            raw_out_dir.mkdir(parents=True, exist_ok=True)
            command = _scenario_command(
                args,
                scenario_script=scenario_script,
                scenario=scenario,
                raw_out_dir=raw_out_dir,
                run_id=run_id,
            )
            started = time.perf_counter()
            completed = subprocess.run(
                command,
                cwd=str(ROOT),
                env=os.environ.copy(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            elapsed_s = time.perf_counter() - started
            log_path.write_text(completed.stdout, encoding="utf-8")
            summary_path = raw_out_dir / scenario / "summary.json"
            run_record = {
                "scenario": scenario,
                "repetition_id": repetition_id,
                "run_id": run_id,
                "returncode": completed.returncode,
                "elapsed_s": round(elapsed_s, 6),
                "summary_path": str(summary_path),
                "log_path": str(log_path),
            }
            if summary_path.exists():
                row = normalize_summary(
                    summary_path,
                    provenance=provenance,
                    repetition_id=repetition_id,
                    run_set_id=run_set_id,
                )
                rows.append(row)
                write_json(summary_path.with_name("normalized_summary.json"), row)
                run_record["event_sequence_valid"] = row["event_sequence_valid"]
                run_record["observation_gate_result"] = row["observation_gate_result"]
                run_record["failure_outcome_gate_result"] = row[
                    "failure_outcome_gate_result"
                ]
            else:
                run_record["missing_summary"] = True
            manifest["runs"].append(run_record)

            print(
                f"{scenario} {repetition_id}: rc={completed.returncode} "
                f"elapsed={elapsed_s:.3f}s"
            )
            if completed.returncode != 0:
                exit_code = completed.returncode
                if args.stop_on_failure:
                    break
        if exit_code and args.stop_on_failure:
            break

    aggregate = aggregate_normalized(rows)
    manifest["completed_normalized_runs"] = len(rows)
    manifest["aggregate_path"] = str(run_root / "aggregate.json")
    write_json(run_root / "manifest.json", manifest)
    write_json(run_root / "aggregate.json", aggregate)
    write_jsonl(run_root / "normalized_summaries.jsonl", rows)
    (run_root / "aggregate.md").write_text(
        render_aggregate_markdown(aggregate),
        encoding="utf-8",
    )

    latest = args.out_dir / "latest_repetition_summary.json"
    write_json(
        latest,
        {
            "run_set_id": run_set_id,
            "run_root": str(run_root),
            "manifest": str(run_root / "manifest.json"),
            "aggregate": str(run_root / "aggregate.json"),
            "normalized_summaries": str(run_root / "normalized_summaries.jsonl"),
        },
    )
    print(f"wrote repetition aggregate to {run_root / 'aggregate.json'}")
    return exit_code


def _targets(args: argparse.Namespace) -> dict[str, int]:
    targets = dict(DEFAULT_TARGETS)
    for override in args.count:
        if "=" not in override:
            raise SystemExit(f"invalid --count override: {override}")
        scenario, value = override.split("=", 1)
        if scenario not in targets:
            raise SystemExit(f"unknown scenario in --count: {scenario}")
        targets[scenario] = int(value)
    if args.scenario:
        selected = set(args.scenario)
        targets = {
            scenario: count
            for scenario, count in targets.items()
            if scenario in selected
        }
    return targets


def normalize_optional_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    return path.expanduser()


def resolve_runner(runner: str | None) -> str | None:
    if not runner:
        return None
    candidate = Path(runner).expanduser()
    if candidate.exists():
        return str(candidate)
    return shutil.which(runner)


def validate_external_inputs(args: argparse.Namespace) -> None:
    args.vllm_source = normalize_optional_path(args.vllm_source)
    if args.vllm_source is not None and not args.vllm_source.exists():
        raise SystemExit(
            "patched vLLM source path does not exist: "
            f"{args.vllm_source}. Set "
            "VLLM_KV_RESIDENCY_VLLM_SOURCE=/path/to/vllm-checkout "
            "or pass --vllm-source /path/to/vllm-checkout."
        )
    resolved_runner = resolve_runner(args.runner)
    if resolved_runner is None:
        raise SystemExit(
            "a Python runner that imports the patched vLLM connector mechanism "
            "is required. Set VLLM_AUDIT_PYTHON=/path/to/python-with-patched-vllm "
            "or pass --runner /path/to/python-with-patched-vllm."
        )
    args.runner = resolved_runner


def _scenario_command(
    args: argparse.Namespace,
    *,
    scenario_script: Path,
    scenario: str,
    raw_out_dir: Path,
    run_id: str,
) -> list[str]:
    command = [
        args.runner,
        str(scenario_script),
        "--scenario",
        scenario,
        "--out-dir",
        str(raw_out_dir),
        "--run-id",
        run_id,
    ]
    if args.vllm_source is not None:
        command.extend(["--vllm-source", str(args.vllm_source)])
    optional_args = (
        ("--model", args.model),
        ("--max-model-len", args.max_model_len),
        ("--max-tokens", args.max_tokens),
        ("--gpu-memory-utilization", args.gpu_memory_utilization),
        ("--kv-cache-memory-bytes", args.kv_cache_memory_bytes),
    )
    for flag, value in optional_args:
        if value is not None:
            command.extend([flag, str(value)])
    return command


if __name__ == "__main__":
    raise SystemExit(main())
