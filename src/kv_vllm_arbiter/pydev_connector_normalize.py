"""Normalize patched pydev OffloadingConnector failure-semantics artifacts."""

from __future__ import annotations

import json
import math
import statistics
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from kv_vllm_arbiter.pydev_connector_failure import load_jsonl


OBSERVATION_REQUIREMENTS = (
    "claim_metadata_before_lifecycle",
    "store_offload_to_cpu_path",
    "reuse_lookup_hit_requiring_load",
    "cpu_to_gpu_restore_success",
    "claim_metadata_ordering",
)

FAILURE_REQUIREMENTS = (
    "claim_metadata_before_lifecycle",
    "store_offload_to_cpu_path",
    "restore_required_before_failure",
    "controlled_cpu_to_gpu_load_failure",
    "claim_scoped_restoration_failed",
    "fail_closed_active_request_refused",
    "scheduler_side_restoration_failed",
    "scheduler_side_active_request_refused",
    "scheduler_side_claim_match",
    "scheduler_event_before_or_at_termination",
    "ordered_failure_semantics",
    "no_fallback_recompute_counted_as_satisfaction",
)

COMPACT_EVENT_KEYS = (
    "event",
    "event_sequence",
    "monotonic_ns",
    "request_id",
    "claim_id",
    "resident_claim_id",
    "predicate_id",
    "prefix_id",
    "reusable_object_id",
    "cache_identity",
    "request_token_map_id",
    "job_id",
    "transfer_type",
    "success",
    "transfer_size",
    "key_count",
    "num_hit_tokens",
    "will_load_async",
    "failure_reason",
    "outcome_claim_id",
    "blocking_claim_ids",
    "claim_scoped_outcome_type",
    "scheduler_finish_status",
    "finish_status",
    "finish_reason",
    "invalid_block_ids",
    "invalid_block_count",
    "scheduler_failure_policy",
    "scheduler_side_failure_outcome",
    "scheduler_side_refusal",
    "native_scheduler_refusal",
    "native_scheduler_admission_refusal",
)


@dataclass(frozen=True)
class Provenance:
    parent_commit: str | None
    artifact_commit: str | None
    vllm_base_commit: str | None
    vllm_patch_commits: list[dict[str, str]]
    runner_path: str | None
    vllm_source_path: str | None = None
    vllm_source_head: str | None = None
    vllm_source_status_short: str | None = None
    vllm_source_clean: bool | None = None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def collect_provenance(
    *,
    parent_dir: Path | None,
    artifact_dir: Path | None,
    vllm_source: Path | None,
    runner_path: str | None,
) -> Provenance:
    patch_commits: list[dict[str, str]] = []
    vllm_base_commit = None
    vllm_source_path = str(vllm_source) if vllm_source is not None else None
    vllm_source_head = None
    vllm_source_status_short = None
    vllm_source_clean = None
    if vllm_source is not None:
        vllm_source_head = git_output(vllm_source, "rev-parse", "HEAD")
        vllm_source_status_short = git_output(vllm_source, "status", "--short")
        vllm_source_clean = vllm_source_status_short == ""
        vllm_base_commit = git_output(
            vllm_source,
            "merge-base",
            "HEAD",
            "origin/main",
            allow_failure=True,
        )
        if not vllm_base_commit:
            vllm_base_commit = git_output(
                vllm_source,
                "rev-parse",
                "HEAD~3",
                allow_failure=True,
            )
        revision_range = f"{vllm_base_commit}..HEAD" if vllm_base_commit else "HEAD~3..HEAD"
        for line in git_output(
            vllm_source,
            "log",
            "--reverse",
            "--format=%H%x00%s",
            revision_range,
            allow_failure=True,
        ).splitlines():
            if "\x00" not in line:
                continue
            commit, subject = line.split("\x00", 1)
            patch_commits.append({"commit": commit, "subject": subject})

    return Provenance(
        parent_commit=git_output(parent_dir, "rev-parse", "HEAD") if parent_dir else None,
        artifact_commit=git_output(artifact_dir, "rev-parse", "HEAD") if artifact_dir else None,
        vllm_base_commit=vllm_base_commit,
        vllm_patch_commits=patch_commits,
        runner_path=runner_path,
        vllm_source_path=vllm_source_path,
        vllm_source_head=vllm_source_head,
        vllm_source_status_short=vllm_source_status_short,
        vllm_source_clean=vllm_source_clean,
    )


def git_output(path: Path | None, *args: str, allow_failure: bool = False) -> str | None:
    if path is None:
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        if allow_failure:
            return ""
        return None
    return completed.stdout.strip()


def normalize_summary(
    summary_path: Path,
    *,
    provenance: Provenance,
    repetition_id: str | None = None,
    run_set_id: str | None = None,
) -> dict[str, Any]:
    raw = load_json(summary_path)
    events = _load_events_for_summary(summary_path, raw)
    gate_summary = raw.get("evaluation", {}).get("gate_summary", {})
    claim_id = gate_summary.get("claim_id") or _first_claim_id(events)
    request_records = raw.get("request_records", [])
    resident_record = _request_record(request_records, "resident")
    reuse_record = _request_record(request_records, "reuse")
    ordered_sequence = [_compact_event(event) for event in sorted(events, key=_event_order)]
    transfer_metrics = raw.get("transfer_metrics", {})
    observation_missing = gate_summary.get("observation_missing_requirements", [])
    failure_missing = gate_summary.get("failure_missing_requirements", [])
    obligations = _obligations(raw, observation_missing, failure_missing)
    latency = _latencies_ns(events, claim_id)
    scenario = str(raw.get("scenario") or summary_path.parent.name)
    run_id = str(raw.get("run_id") or "")

    normalized = {
        "schema_version": 1,
        "scenario_id": scenario,
        "run_id": run_id,
        "repetition_id": repetition_id or _infer_repetition_id(summary_path, run_id),
        "run_set_id": run_set_id or _infer_run_set_id(summary_path),
        "parent_commit": provenance.parent_commit,
        "artifact_commit": provenance.artifact_commit,
        "vllm_source_path": provenance.vllm_source_path,
        "vllm_source_head": provenance.vllm_source_head,
        "vllm_source_status_short": provenance.vllm_source_status_short,
        "vllm_source_clean": provenance.vllm_source_clean,
        "vllm_import_path_matches_source": _path_is_under(
            raw.get("runtime", {}).get("vllm_file"),
            provenance.vllm_source_path,
        ),
        "vllm_base_commit": provenance.vllm_base_commit,
        "vllm_patch_commits": provenance.vllm_patch_commits,
        **_patch_commit_aliases(provenance.vllm_patch_commits),
        "model": raw.get("model"),
        "gpu": raw.get("runtime", {}).get("device0"),
        "runner_path": provenance.runner_path or raw.get("python"),
        "python": raw.get("python"),
        "runtime": raw.get("runtime", {}),
        "connector_config": raw.get("connector_config") or _default_connector_config(raw),
        "claim_id": claim_id,
        "predicate_id": _first_nonempty(events, "predicate_id"),
        "event_count": int(raw.get("event_count") or len(events)),
        "event_bytes": int(raw.get("event_bytes") or _event_bytes(raw)),
        "ordered_event_sequence": ordered_sequence,
        "obligations_satisfied": obligations["satisfied"],
        "obligations_missing": obligations["missing"],
        "observation_gate_result": bool(
            raw.get("evaluation", {}).get("connector_observation_success")
        ),
        "failure_outcome_gate_result": bool(
            raw.get("evaluation", {}).get("restoration_failure_outcome_success")
        ),
        "scheduler_side_failure_outcome_present": bool(
            gate_summary.get("scheduler_side_failure_outcome_present")
        ),
        "scheduler_side_refusal_present": bool(
            gate_summary.get("scheduler_side_refusal_present")
        ),
        "scheduler_side_claim_match": bool(
            gate_summary.get("scheduler_side_claim_match")
        ),
        "scheduler_event_before_or_at_termination": bool(
            gate_summary.get("scheduler_event_before_or_at_termination")
        ),
        "native_scheduler_admission_refusal": bool(
            gate_summary.get("native_scheduler_admission_refusal")
        ),
        "connector_level_outcome_present": bool(
            gate_summary.get("connector_level_outcome_present")
        ),
        "finish_status": gate_summary.get("finish_status"),
        "finish_reason": gate_summary.get("finish_reason"),
        "blocking_claim_ids": gate_summary.get("blocking_claim_ids") or [],
        "event_sequence_valid": _expected_event_sequence_valid(raw),
        "resident_request_wall_time_s": _record_number(resident_record, "wall_latency_s"),
        "reuse_request_wall_time_s": _record_number(reuse_record, "wall_latency_s"),
        "reuse_cached_tokens": _record_number(reuse_record, "num_cached_tokens"),
        "output_tokens": _total_output_tokens(request_records),
        "worker_transfer_count": int(transfer_metrics.get("worker_transfer_count") or 0),
        "transfer_directions": transfer_metrics.get("directions") or [],
        "transfer_bytes": [
            item
            for item in (transfer_metrics.get("worker_transfer_sizes") or [])
            if item is not None
        ],
        "transfer_bytes_total": sum(
            int(item)
            for item in (transfer_metrics.get("worker_transfer_sizes") or [])
            if item is not None
        ),
        "analyzer_runtime_ns": _record_number(
            raw.get("evaluation", {}), "analyzer_runtime_ns"
        ),
        "failure_to_outcome_latency_ns": latency["load_failed_to_refusal_ns"],
        "restoration_failed_to_active_request_refused_latency_ns": latency[
            "restoration_failed_to_refusal_ns"
        ],
        "final_request_outcome_label": _final_request_outcome_label(request_records),
        "raw_summary_path": str(summary_path),
        "raw_event_path": str(_event_path(summary_path, raw)),
        "claim_boundary": raw.get("claim_boundary")
        or gate_summary.get("claim_boundary")
        or (
            "Local patched pydev vLLM OffloadingConnector plus scheduler-side "
            "invalid-KV-load boundary mechanism only; not upstream ResidentClaim "
            "support, not production offload performance, and not pre-admission "
            "refusal."
        ),
    }
    return normalized


def _patch_commit_aliases(
    patch_commits: list[dict[str, str]],
) -> dict[str, str | None]:
    aliases: dict[str, str | None] = {
        "vllm_observation_patch_commit": None,
        "vllm_failure_semantics_patch_commit": None,
        "vllm_scheduler_boundary_patch_commit": None,
        "vllm_patch_stack_head": None,
    }
    for item in patch_commits:
        commit = item.get("commit")
        subject = item.get("subject", "").lower()
        if not commit:
            continue
        aliases["vllm_patch_stack_head"] = commit
        if "connector telemetry" in subject:
            aliases["vllm_observation_patch_commit"] = commit
        elif "load failure semantics" in subject:
            aliases["vllm_failure_semantics_patch_commit"] = commit
        elif "scheduler boundary" in subject:
            aliases["vllm_scheduler_boundary_patch_commit"] = commit
    return aliases


def _path_is_under(child: str | None, parent: str | None) -> bool | None:
    if not child or not parent:
        return None
    try:
        child_path = Path(child).resolve()
        parent_path = Path(parent).resolve()
        return child_path == parent_path or child_path.is_relative_to(parent_path)
    except OSError:
        return str(child).startswith(str(parent))


def aggregate_normalized(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    row_list = list(rows)
    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in row_list:
        by_scenario[str(row["scenario_id"])].append(row)

    scenarios = {}
    for scenario, items in sorted(by_scenario.items()):
        scenarios[scenario] = {
            "runs": len(items),
            "observation_gate_pass_rate": _rate(
                item["observation_gate_result"] for item in items
            ),
            "failure_outcome_gate_pass_rate": _rate(
                item["failure_outcome_gate_result"] for item in items
            ),
            "event_sequence_valid_rate": _rate(
                item["event_sequence_valid"] for item in items
            ),
            "final_request_outcomes": dict(
                sorted(Counter(item["final_request_outcome_label"] for item in items).items())
            ),
            "resident_wall_time_s": _summary_stats(
                item.get("resident_request_wall_time_s") for item in items
            ),
            "reuse_wall_time_s": _summary_stats(
                item.get("reuse_request_wall_time_s") for item in items
            ),
            "event_bytes": _summary_stats(item.get("event_bytes") for item in items),
            "analyzer_runtime_ns": _summary_stats(
                item.get("analyzer_runtime_ns") for item in items
            ),
            "failure_to_outcome_latency_ns": _summary_stats(
                item.get("failure_to_outcome_latency_ns") for item in items
            ),
            "restoration_failed_to_active_request_refused_latency_ns": _summary_stats(
                item.get("restoration_failed_to_active_request_refused_latency_ns")
                for item in items
            ),
            "reuse_cached_tokens": _summary_stats(
                item.get("reuse_cached_tokens") for item in items
            ),
            "worker_transfer_count": _summary_stats(
                item.get("worker_transfer_count") for item in items
            ),
            "transfer_bytes_total": _summary_stats(
                item.get("transfer_bytes_total") for item in items
            ),
        }

    return {
        "schema_version": 1,
        "runs": len(row_list),
        "scenarios": scenarios,
    }


def render_aggregate_markdown(aggregate: dict[str, Any]) -> str:
    lines = [
        "# Pydev Connector Failure-Semantics Repetition Summary",
        "",
        "Scope: local patched pydev vLLM OffloadingConnector mechanism with scheduler-side invalid-KV-load boundary evidence; not upstream vLLM support, production offload performance, or scheduler-native pre-admission refusal.",
        "",
        "| Scenario | Runs | Observation pass | Failure-outcome pass | Event-sequence valid | Resident median/p95 s | Reuse median/p95 s | Event bytes median/p95 | Analyzer median/p95 ns | Failure->outcome median/p95 ns | Restore-failed->refused median/p95 ns | Outcomes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for scenario, data in aggregate.get("scenarios", {}).items():
        lines.append(
            "| "
            f"`{scenario}` | "
            f"{data['runs']} | "
            f"{_format_rate(data['observation_gate_pass_rate'])} | "
            f"{_format_rate(data['failure_outcome_gate_pass_rate'])} | "
            f"{_format_rate(data['event_sequence_valid_rate'])} | "
            f"{_format_median_p95(data['resident_wall_time_s'])} | "
            f"{_format_median_p95(data['reuse_wall_time_s'])} | "
            f"{_format_median_p95(data['event_bytes'])} | "
            f"{_format_median_p95(data['analyzer_runtime_ns'])} | "
            f"{_format_median_p95(data['failure_to_outcome_latency_ns'])} | "
            f"{_format_median_p95(data['restoration_failed_to_active_request_refused_latency_ns'])} | "
            f"{', '.join(f'{key}={value}' for key, value in data['final_request_outcomes'].items())} |"
        )
    lines.append("")
    return "\n".join(lines)


def _load_events_for_summary(summary_path: Path, raw: dict[str, Any]) -> list[dict[str, Any]]:
    path = _event_path(summary_path, raw)
    return load_jsonl(path) if path.exists() else []


def _event_path(summary_path: Path, raw: dict[str, Any]) -> Path:
    event_path = raw.get("event_path")
    if event_path:
        return Path(event_path)
    return summary_path.with_name("vllm_runtime_events.jsonl")


def _event_bytes(raw: dict[str, Any]) -> int:
    event_path = raw.get("event_path")
    if not event_path:
        return 0
    path = Path(event_path)
    return path.stat().st_size if path.exists() else 0


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    return {key: event[key] for key in COMPACT_EVENT_KEYS if key in event}


def _first_claim_id(events: list[dict[str, Any]]) -> str | None:
    for event in sorted(events, key=_event_order):
        claim_id = _event_claim_id(event)
        if claim_id:
            return claim_id
    return None


def _event_claim_id(event: dict[str, Any]) -> str | None:
    claim_id = event.get("claim_id") or event.get("resident_claim_id")
    return str(claim_id) if claim_id else None


def _first_nonempty(events: list[dict[str, Any]], key: str) -> Any | None:
    for event in sorted(events, key=_event_order):
        value = event.get(key)
        if value is not None:
            return value
    return None


def _event_order(event: dict[str, Any]) -> int:
    return int(event.get("event_sequence", event.get("timestamp_ns", 0)) or 0)


def _request_record(records: list[dict[str, Any]], role: str) -> dict[str, Any] | None:
    return next((record for record in records if record.get("role") == role), None)


def _record_number(record: dict[str, Any] | None, key: str) -> int | float | None:
    if not record:
        return None
    value = record.get(key)
    if value is None:
        return None
    return value


def _total_output_tokens(records: list[dict[str, Any]]) -> int:
    return sum(int(record.get("num_output_tokens") or 0) for record in records)


def _final_request_outcome_label(records: list[dict[str, Any]]) -> str:
    if not records:
        return "no_request_records"
    final = records[-1]
    return str(final.get("connector_outcome") or final.get("status") or "unknown")


def _obligations(
    raw: dict[str, Any],
    observation_missing: list[str],
    failure_missing: list[str],
) -> dict[str, list[str]]:
    obs_missing = set(observation_missing)
    fail_missing = set(failure_missing)
    if "fallback_recompute_counted_as_satisfaction" in fail_missing:
        fail_missing.add("no_fallback_recompute_counted_as_satisfaction")
    missing = sorted({f"observation:{item}" for item in obs_missing}.union(
        {f"failure:{item}" for item in fail_missing}
    ))
    satisfied = sorted(
        {f"observation:{item}" for item in OBSERVATION_REQUIREMENTS if item not in obs_missing}
        .union(
            {
                f"failure:{item}"
                for item in FAILURE_REQUIREMENTS
                if item not in fail_missing
            }
        )
    )
    if raw.get("evaluation", {}).get("restoration_failure_outcome_success"):
        satisfied.append("failure:ordered_failure_semantics")
    return {"satisfied": sorted(set(satisfied)), "missing": missing}


def _expected_event_sequence_valid(raw: dict[str, Any]) -> bool:
    scenario = raw.get("scenario")
    evaluation = raw.get("evaluation", {})
    gate_summary = evaluation.get("gate_summary", {})
    controls = gate_summary.get("controls", {})
    observation = bool(evaluation.get("connector_observation_success"))
    failure = bool(evaluation.get("restoration_failure_outcome_success"))
    event_count = int(raw.get("event_count") or 0)

    if scenario == "success_no_event_path":
        return event_count == 0 and not observation and not failure
    if scenario == "success_path":
        return observation and not failure
    if scenario == "claimed_load_failure":
        return failure
    if scenario == "wrong_claim_failure":
        return observation and not failure and bool(controls.get("wrong_claim_failure_rejected"))
    if scenario == "unclaimed_load_failure":
        return not failure and bool(controls.get("unclaimed_failure_rejected"))
    if scenario == "fallback_recompute":
        return not failure and bool(
            controls.get("fallback_recompute_rejected")
            or controls.get("fallback_recompute_counted_as_satisfaction")
        )
    if scenario == "generic_counter_only":
        return not observation and not failure and bool(
            controls.get("generic_counter_only_rejected")
        )
    if scenario == "multi_claim_targeted_failure":
        multi = raw.get("multi_claim_attribution", {})
        return failure and bool(multi.get("attribution_success"))
    if scenario == "ordinary_offload_no_claim":
        return (
            event_count > 0
            and not observation
            and not failure
            and bool(controls.get("ordinary_offload_without_claim_rejected"))
        )
    return False


def _latencies_ns(events: list[dict[str, Any]], claim_id: str | None) -> dict[str, int | None]:
    event_list = sorted(events, key=_event_order)
    refusal = _first_event(event_list, "active_request_refused", claim_id=claim_id)
    load_failed = _first_event(event_list, "offload_load_job_failed", claim_id=claim_id)
    restoration_failed = _first_event(
        event_list, "resident_claim_restoration_failed", claim_id=claim_id
    )
    return {
        "load_failed_to_refusal_ns": _monotonic_delta_ns(load_failed, refusal),
        "restoration_failed_to_refusal_ns": _monotonic_delta_ns(
            restoration_failed, refusal
        ),
    }


def _first_event(
    events: list[dict[str, Any]],
    event_name: str,
    *,
    claim_id: str | None,
) -> dict[str, Any] | None:
    for event in events:
        if event.get("event") != event_name:
            continue
        if claim_id is not None and _event_claim_id(event) != claim_id:
            continue
        return event
    return None


def _monotonic_delta_ns(
    start: dict[str, Any] | None,
    end: dict[str, Any] | None,
) -> int | None:
    if start is None or end is None:
        return None
    if "monotonic_ns" not in start or "monotonic_ns" not in end:
        return None
    return int(end["monotonic_ns"]) - int(start["monotonic_ns"])


def _default_connector_config(raw: dict[str, Any]) -> dict[str, Any]:
    policy = "recompute" if raw.get("scenario") == "fallback_recompute" else "fail"
    return {
        "kv_connector": "OffloadingConnector",
        "kv_role": "kv_both",
        "kv_load_failure_policy": policy,
        "kv_connector_extra_config": {
            "block_size": 64,
            "cpu_bytes_to_use": 536870912,
            "store_threshold": 1,
        },
    }


def _infer_repetition_id(summary_path: Path, run_id: str) -> str | None:
    parts = summary_path.parts
    for part in parts:
        if part.startswith("rep_") or part.startswith("rep-"):
            return part.replace("_", "-")
    marker = ":rep-"
    if marker in run_id:
        return "rep-" + run_id.split(marker, 1)[1]
    return None


def _infer_run_set_id(summary_path: Path) -> str | None:
    parts = list(summary_path.parts)
    if "repetitions" not in parts:
        return None
    index = parts.index("repetitions")
    if index + 1 < len(parts):
        return parts[index + 1]
    return None


def _rate(values: Iterable[bool]) -> dict[str, Any]:
    items = [bool(value) for value in values]
    passed = sum(1 for value in items if value)
    total = len(items)
    return {"passed": passed, "total": total, "rate": passed / total if total else None}


def _summary_stats(values: Iterable[Any]) -> dict[str, Any]:
    cleaned = [float(value) for value in values if value is not None]
    if not cleaned:
        return {"count": 0, "min": None, "median": None, "p95": None, "max": None}
    ordered = sorted(cleaned)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "median": statistics.median(ordered),
        "p95": _nearest_rank_percentile(ordered, 0.95),
        "max": ordered[-1],
    }


def _nearest_rank_percentile(ordered_values: list[float], percentile: float) -> float:
    index = max(0, math.ceil(percentile * len(ordered_values)) - 1)
    return ordered_values[index]


def _format_rate(value: dict[str, Any]) -> str:
    rate = value.get("rate")
    if rate is None:
        return "-"
    return f"{value['passed']}/{value['total']} ({rate:.3f})"


def _format_median_p95(value: dict[str, Any]) -> str:
    if not value or value.get("count") == 0:
        return "-"
    return f"{value['median']:.6g}/{value['p95']:.6g}"
