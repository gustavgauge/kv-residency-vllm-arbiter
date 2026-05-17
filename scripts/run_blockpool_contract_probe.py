#!/usr/bin/env python3
"""Run a vLLM BlockPool active/resident contract probe."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_PYTHON = os.environ.get("VLLM_AUDIT_PYTHON")
VLLM_SOURCE = os.environ.get("VLLM_KV_RESIDENCY_VLLM_SOURCE")


def ensure_vllm_runtime() -> None:
    if (
        os.environ.get("VLLM_KV_RESIDENCY_USE_SOURCE_TREE") == "1"
        and VLLM_SOURCE
    ):
        source = Path(VLLM_SOURCE).expanduser()
        if source.exists():
            sys.path.insert(0, str(source))
    try:
        import vllm  # noqa: F401
    except ModuleNotFoundError:
        if DEFAULT_AUDIT_PYTHON:
            audit_python = Path(DEFAULT_AUDIT_PYTHON).expanduser()
            if (
                audit_python.exists()
                and Path(sys.executable).resolve() != audit_python.resolve()
            ):
                os.execv(str(audit_python), [str(audit_python), *sys.argv])
        raise


def block_hash(index: int):
    from vllm.v1.core.kv_cache_utils import BlockHash

    return BlockHash(index.to_bytes(4, "big") * 8)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit BlockPool active/resident telemetry for 60/70/80."
    )
    parser.add_argument("--resident-blocks", type=int, default=60)
    parser.add_argument("--active-blocks", type=int, default=70)
    parser.add_argument("--usable-blocks", type=int, default=80)
    parser.add_argument("--block-size", type=int, default=16)
    parser.add_argument("--run-id", default="native-blockpool-60-70-80")
    parser.add_argument("--policy", default="native")
    parser.add_argument("--no-admit-active", action="store_true")
    parser.add_argument("--resident-claim", action="store_true")
    parser.add_argument("--enforce-hard-exclude", action="store_true")
    parser.add_argument("--claim-ttl-allocations", type=int, default=None)
    parser.add_argument("--on-conflict", choices=["refuse", "demote"], default="refuse")
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=ROOT
        / "artifacts"
        / "native_blockpool"
        / "native_blockpool_60_70_80.jsonl",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT
        / "artifacts"
        / "native_blockpool"
        / "native_blockpool_60_70_80_summary.json",
    )
    return parser.parse_args()


def load_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def artifact_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    ensure_vllm_runtime()

    from vllm.v1.core.block_pool import BlockPool

    args = parse_args()
    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.jsonl.write_text("")

    os.environ["VLLM_KV_RESIDENCY_TELEMETRY_PATH"] = str(args.jsonl)
    os.environ["VLLM_KV_RESIDENCY_RUN_ID"] = args.run_id
    os.environ["VLLM_KV_RESIDENCY_POLICY"] = args.policy
    os.environ["VLLM_KV_RESIDENCY_USABLE_BLOCKS"] = str(args.usable_blocks)
    if args.no_admit_active:
        os.environ["VLLM_KV_RESIDENCY_NO_ADMIT_REQUEST_IDS"] = "active"
    else:
        os.environ.pop("VLLM_KV_RESIDENCY_NO_ADMIT_REQUEST_IDS", None)
    if args.resident_claim:
        os.environ["VLLM_KV_RESIDENCY_CLAIM_REQUEST_IDS"] = "resident"
        os.environ["VLLM_KV_RESIDENCY_CLAIM_ID"] = "claim:resident"
        os.environ["VLLM_KV_RESIDENCY_PREFIX_ID"] = "resident"
        os.environ["VLLM_KV_RESIDENCY_USEFUL_THRESHOLD_BLOCKS"] = str(
            args.resident_blocks
        )
        os.environ["VLLM_KV_RESIDENCY_PREDICTED_VALUE"] = "1.0"
        os.environ["VLLM_KV_RESIDENCY_CONFIDENCE"] = "1.0"
        os.environ["VLLM_KV_RESIDENCY_PROTECTION_MODE"] = "hard_exclude"
        if args.claim_ttl_allocations is not None:
            os.environ["VLLM_KV_RESIDENCY_CLAIM_TTL_ALLOCATIONS"] = str(
                args.claim_ttl_allocations
            )
        else:
            os.environ.pop("VLLM_KV_RESIDENCY_CLAIM_TTL_ALLOCATIONS", None)
    else:
        os.environ.pop("VLLM_KV_RESIDENCY_CLAIM_REQUEST_IDS", None)
        os.environ.pop("VLLM_KV_RESIDENCY_CLAIM_TTL_ALLOCATIONS", None)
    if args.enforce_hard_exclude:
        os.environ["VLLM_KV_RESIDENCY_ENFORCE_PROTECTION"] = "hard_exclude"
        if args.on_conflict == "demote":
            os.environ["VLLM_KV_RESIDENCY_ON_CONFLICT"] = "demote"
        else:
            os.environ.pop("VLLM_KV_RESIDENCY_ON_CONFLICT", None)
    else:
        os.environ.pop("VLLM_KV_RESIDENCY_ENFORCE_PROTECTION", None)
        os.environ.pop("VLLM_KV_RESIDENCY_ON_CONFLICT", None)

    # vLLM reserves block 0 as the null block, so num_gpu_blocks is usable + 1.
    pool = BlockPool(
        num_gpu_blocks=args.usable_blocks + 1,
        enable_caching=True,
        hash_block_size=args.block_size,
    )

    resident_blocks = pool.get_new_blocks(
        args.resident_blocks, request_id="resident"
    )
    request = SimpleNamespace(
        request_id="resident",
        block_hashes=[
            block_hash(index) for index in range(1, args.resident_blocks + 1)
        ],
    )
    pool.cache_full_blocks(
        request=request,
        blocks=resident_blocks,
        num_cached_blocks=0,
        num_full_blocks=args.resident_blocks,
        block_size=args.block_size,
        kv_cache_group_id=0,
    )
    pool.free_blocks(reversed(resident_blocks))

    free_blocks_before_active = pool.get_num_free_blocks()
    active_allocation_error = None
    try:
        active_blocks = pool.get_new_blocks(args.active_blocks, request_id="active")
    except ValueError as exc:
        active_blocks = []
        active_allocation_error = str(exc)
        from vllm.v1.core.kv_residency_telemetry import emit_kv_residency_event

        conflict_fields = pool.kv_residency_conflict_fields(
            args.active_blocks,
            free_blocks_before_active,
        )
        emit_kv_residency_event(
            "active_request_refused",
            request_id="active",
            active_live_blocks_required=args.active_blocks,
            active_live_blocks_current=0,
            future_reuse_requested=not args.no_admit_active,
            future_reuse_admitted=False,
            arbiter_action="capacity_required",
            **conflict_fields,
        )
    if args.no_admit_active:
        from vllm.v1.core.kv_residency_telemetry import emit_kv_residency_event

        emit_kv_residency_event(
            "future_reuse_denied",
            request_id="active",
            active_live_blocks_required=args.active_blocks,
            active_live_blocks_current=len(active_blocks),
            future_reuse_requested=True,
            future_reuse_admitted=False,
            arbiter_action="write_no_admit",
        )

    events = load_events(args.jsonl)
    victim_events = [
        event for event in events if event["event"] == "allocation_victim_selected"
    ]
    active_victims = [
        event for event in victim_events if event["request_id"] == "active"
    ]
    resident_materialized = [
        event for event in events if event["event"] == "resident_block_materialized"
    ]
    protected_resident_materialized = [
        event
        for event in resident_materialized
        if event.get("is_protected_resident") is True
    ]
    cached_active_victims = [
        event
        for event in active_victims
        if event.get("victim_reason") == "cached_prefix_reuse"
    ]
    claim_events = [
        event
        for event in events
        if event["event"]
        in {
            "resident_claim_accepted",
            "resident_claim_materialized",
            "resident_claim_relaxed",
            "resident_claim_demoted",
            "resident_claim_expired",
            "resident_claim_harmed",
            "resident_claim_block_lost_after_release",
        }
    ]
    active_refusal_events = [
        event for event in events if event["event"] == "active_request_refused"
    ]
    materialized_by_block = {
        event["physical_block_id"]: event for event in resident_materialized
    }
    harmed_positions = [
        materialized_by_block[event["physical_block_id"]][
            "logical_block_position"
        ]
        for event in cached_active_victims
        if event["physical_block_id"] in materialized_by_block
    ]

    protection_active = (
        args.enforce_hard_exclude
        and args.on_conflict != "demote"
        and args.claim_ttl_allocations != 1
    )
    expected_harmed = (
        0
        if protection_active
        else max(0, args.active_blocks - (args.usable_blocks - args.resident_blocks))
    )
    summary = {
        "run_id": args.run_id,
        "policy": args.policy,
        "resident_blocks": args.resident_blocks,
        "active_live_blocks": args.active_blocks,
        "usable_blocks": args.usable_blocks,
        "active_allocated": len(active_blocks),
        "active_served": active_allocation_error is None,
        "active_allocation_error": active_allocation_error,
        "free_blocks_before_active": free_blocks_before_active,
        "active_future_reuse_admitted": (
            active_allocation_error is None and not args.no_admit_active
        ),
        "resident_materialized_events": len(resident_materialized),
        "protected_resident_materialized_events": len(
            protected_resident_materialized
        ),
        "protected_resident_physical_block_ids": [
            event["physical_block_id"] for event in protected_resident_materialized
        ],
        "claim_id": (
            protected_resident_materialized[0].get("claim_id")
            if protected_resident_materialized
            else None
        ),
        "prefix_id": (
            protected_resident_materialized[0].get("prefix_id")
            if protected_resident_materialized
            else None
        ),
        "protection_mode": (
            protected_resident_materialized[0].get("protection_mode")
            if protected_resident_materialized
            else None
        ),
        "useful_threshold_blocks": (
            protected_resident_materialized[0].get("useful_threshold_blocks")
            if protected_resident_materialized
            else None
        ),
        "claim_lifecycle_events": claim_events,
        "claim_lifecycle_event_counts": {
            event_name: sum(1 for event in claim_events if event["event"] == event_name)
            for event_name in sorted({event["event"] for event in claim_events})
        },
        "active_refusal_events": active_refusal_events,
        "blocking_claim_ids": sorted(
            {
                claim_id
                for event in active_refusal_events
                for claim_id in event.get("blocking_claim_ids", [])
            }
        ),
        "active_allocation_victim_events": len(active_victims),
        "cached_resident_victims": len(cached_active_victims),
        "expected_cached_resident_victims": expected_harmed,
        "remaining_cached_resident_blocks": len(pool.cached_block_hash_to_block),
        "harmed_logical_block_positions": sorted(harmed_positions),
        "jsonl": artifact_path(args.jsonl),
    }
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))

    if len(cached_active_victims) != expected_harmed:
        return 1
    if len(resident_materialized) != args.resident_blocks:
        return 1
    if args.resident_claim and len(protected_resident_materialized) != args.resident_blocks:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
