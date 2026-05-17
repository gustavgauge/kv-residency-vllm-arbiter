#!/usr/bin/env python3
"""Generate the prior-art boundary table."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "prior_art"


ROWS = [
    {
        "runtime": "vLLM",
        "strongest_relevant_primitives": (
            "Hash-chain prefix blocks, request priority, prefix-cache events, "
            "internal request-to-block maps, and the prototype hooks."
        ),
        "useful_resident_footprint": "Prototype yes; native public API no.",
        "active_defer_under_claim": "Prototype yes via hard exclusion; native no resident-claim API.",
        "separate_no_admit": "Prototype yes; native public API not found.",
        "claim_level_harm_telemetry": "Prototype yes; native telemetry insufficient.",
        "boundary_verdict": (
            "Implementation target and live counterexample: native/no-admit can "
            "serve active while harming resident reusable KV below 130 usable blocks; "
            "hard exclusion converts conflict into active refusal."
        ),
        "evidence": [
            "artifact:capacity_sweep/capacity_sweep_summary.md",
            "source:vllm/v1/core/block_pool.py",
            "source:vllm/v1/core/kv_cache_manager.py",
        ],
    },
    {
        "runtime": "SGLang",
        "strongest_relevant_primitives": (
            "Radix cache for finished and unfinished requests, priority-aware "
            "eviction, lock refs, protected_size/evictable_size accounting."
        ),
        "useful_resident_footprint": (
            "Partial: radix paths and protected accounting exist, but no audited "
            "first-class useful-footprint claim/refusal lifecycle."
        ),
        "active_defer_under_claim": (
            "Partial/unclear from source audit: lock refs protect resident nodes from "
            "eviction, but a future-reuse claim admission contract and explicit "
            "active conflict action were not identified."
        ),
        "separate_no_admit": (
            "Partial: finished insertion can be disabled in code paths, but this is "
            "not the same as the active/resident contract."
        ),
        "claim_level_harm_telemetry": "Not established by this audit.",
        "boundary_verdict": (
            "Serious comparator with stronger resident-accounting pieces than native "
            "vLLM; still not shown to expose the full claim lifecycle."
        ),
        "evidence": [
            "sglang@bbe9c7e:python/sglang/srt/mem_cache/radix_cache.py:446",
            "sglang@bbe9c7e:python/sglang/srt/mem_cache/radix_cache.py:493",
            "sglang@bbe9c7e:python/sglang/srt/mem_cache/radix_cache.py:568",
            "sglang@bbe9c7e:python/sglang/srt/mem_cache/radix_cache.py:594",
            "sglang@bbe9c7e:python/sglang/srt/mem_cache/radix_cache.py:631",
        ],
    },
    {
        "runtime": "TensorRT-LLM",
        "strongest_relevant_primitives": (
            "Block reuse, prioritized LRU, retention priority/duration, host "
            "offload, scheduler no-evict policies, internal pinning, and KV events."
        ),
        "useful_resident_footprint": (
            "Partial: token-range retention priorities can describe valuable spans, "
            "but audited API is priority/duration rather than useful-footprint "
            "claim admission/refusal."
        ),
        "active_defer_under_claim": (
            "Partial: scheduler policies can pause/restart or guarantee no eviction "
            "once started, and internal pinning exists; not shown as a single "
            "future-resident claim conflict contract."
        ),
        "separate_no_admit": "Not established as the same per-request active/no-write split.",
        "claim_level_harm_telemetry": (
            "Strong block events and priority/cache-level fields; not full future-claim "
            "harm/refusal telemetry."
        ),
        "boundary_verdict": (
            "Strongest prior art. It refutes any claim that runtimes lack primitives, "
            "but supports the narrower claim that the full active/resident ownership "
            "contract is fragmented."
        ),
        "evidence": [
            "tensorrt-llm@566fd230:docs/source/features/kvcache.md:7",
            "tensorrt-llm@566fd230:docs/source/features/kvcache.md:15",
            "tensorrt-llm@566fd230:docs/source/features/kvcache.md:17",
            "tensorrt-llm@566fd230:docs/source/features/kvcache.md:25",
            "tensorrt-llm@566fd230:docs/source/features/kvcache.md:102",
            "tensorrt-llm@566fd230:cpp/include/tensorrt_llm/executor/executor.h:576",
            "tensorrt-llm@566fd230:cpp/include/tensorrt_llm/executor/types.h:227",
            "tensorrt-llm@566fd230:cpp/tensorrt_llm/batch_manager/evictionPolicy.cpp:140",
            "tensorrt-llm@566fd230:cpp/tensorrt_llm/executor/executorImpl.cpp:2241",
            "tensorrt-llm@566fd230:cpp/include/tensorrt_llm/executor/executor.h:1713",
            "tensorrt-llm@566fd230:cpp/include/tensorrt_llm/executor/executor.h:1751",
        ],
    },
    {
        "runtime": "Dynamo",
        "strongest_relevant_primitives": (
            "Agent hints, cache-control metadata, TTL-style pinning, KV-aware "
            "routing, prefetch hooks, and KV-event-driven orchestration."
        ),
        "useful_resident_footprint": (
            "Partial: orchestration metadata can express reuse intent, but the "
            "audited docs do not define a backend-accepted materialization predicate."
        ),
        "active_defer_under_claim": (
            "Partial/unclear: routing may avoid conflict, but active refusal "
            "attributed to a resident claim is not the documented unit."
        ),
        "separate_no_admit": (
            "Partial: cache-control can affect retention, but active-live "
            "allocation separation is not the same public contract."
        ),
        "claim_level_harm_telemetry": (
            "KV events support routing and cache indexes; accepted-claim "
            "harm/refusal blame is not established."
        ),
        "boundary_verdict": (
            "Strong orchestration comparator. It supports the need for a "
            "portable backend conformance contract rather than refuting it."
        ),
        "evidence": [
            "https://docs.dynamo.nvidia.com/dynamo/dev/user-guides/agents",
            "https://docs.dynamo.nvidia.com/dynamo/dev/user-guides/agents/sg-lang-for-agentic-workloads",
        ],
    },
    {
        "runtime": "Continuum",
        "strongest_relevant_primitives": (
            "TTL-based KV retention for multi-turn agents, queueing/reload cost "
            "modeling, vLLM implementation, and agentic workload evaluation."
        ),
        "useful_resident_footprint": (
            "Strong for agentic TTL retention, but framed as retention policy "
            "rather than portable accepted-claim materialization conformance."
        ),
        "active_defer_under_claim": (
            "Partial: retained KV is modeled as GPU-memory opportunity cost, "
            "but claim-level active refusal semantics are not the contribution."
        ),
        "separate_no_admit": "Not the central public mechanism.",
        "claim_level_harm_telemetry": (
            "Not established as accepted-claim harm/refusal telemetry."
        ),
        "boundary_verdict": (
            "Closest systems threat for a later admission-control paper; Path 1 "
            "must distinguish contract semantics from TTL retention policy."
        ),
        "evidence": [
            "https://arxiv.org/abs/2511.02230",
        ],
    },
    {
        "runtime": "KVFlow",
        "strongest_relevant_primitives": (
            "Workflow-structure-aware prefix caching and CPU-GPU KV prefetching "
            "for LLM-based multi-agent workflows."
        ),
        "useful_resident_footprint": (
            "Strong future-reuse policy comparator; not framed as an accepted "
            "runtime responsibility with predicate-breaking telemetry."
        ),
        "active_defer_under_claim": (
            "Not established as active/resident infeasibility contract."
        ),
        "separate_no_admit": "Not established as the same semantic split.",
        "claim_level_harm_telemetry": "Not established by this audit.",
        "boundary_verdict": (
            "Threatens broad predictive-residency language; less direct against "
            "the conformance-contract framing."
        ),
        "evidence": [
            "https://arxiv.org/abs/2507.07400",
        ],
    },
    {
        "runtime": "Pie",
        "strongest_relevant_primitives": (
            "Programmable inference handlers with application-specific access "
            "to serving-loop behavior and KV strategies."
        ),
        "useful_resident_footprint": (
            "Programmability may express custom policies, but does not itself "
            "define a portable ResidentClaim contract."
        ),
        "active_defer_under_claim": (
            "Handler-dependent; not a backend conformance guarantee."
        ),
        "separate_no_admit": "Handler-dependent.",
        "claim_level_harm_telemetry": "Handler-dependent; not a portable schema.",
        "boundary_verdict": (
            "Shows that implementation flexibility differs from runtime-level "
            "semantic accountability."
        ),
        "evidence": [
            "https://arxiv.org/abs/2510.24051",
        ],
    },
    {
        "runtime": "Marconi",
        "strongest_relevant_primitives": (
            "Admission and eviction based on reuse likelihood and compute "
            "savings relative to KV footprint."
        ),
        "useful_resident_footprint": (
            "Strong value/footprint comparator, especially for broad admission "
            "claims; not an active/resident claim conformance contract."
        ),
        "active_defer_under_claim": "Not established by this audit.",
        "separate_no_admit": "Not established by this audit.",
        "claim_level_harm_telemetry": "Not established by this audit.",
        "boundary_verdict": (
            "Weakens broad value-aware novelty claims; compatible with a narrow "
            "contract/conformance contribution."
        ),
        "evidence": [
            "https://arxiv.org/abs/2411.19379",
        ],
    },
    {
        "runtime": "vLLM + Mooncake",
        "strongest_relevant_primitives": (
            "Distributed KV storage and transfer for KV-cache-centric "
            "disaggregated serving."
        ),
        "useful_resident_footprint": (
            "Storage can preserve or restore KV beyond local GPU capacity, but "
            "does not define the accepted-claim contract by itself."
        ),
        "active_defer_under_claim": (
            "May route or transfer around local conflicts; claim-level refusal "
            "semantics are still a separate contract question."
        ),
        "separate_no_admit": "Not established as the same semantic split.",
        "claim_level_harm_telemetry": (
            "Storage events are not the same as predicate-level claim harm/refusal."
        ),
        "boundary_verdict": (
            "Relevant capacity-extension path; complements rather than replaces "
            "active/resident conformance semantics."
        ),
        "evidence": [
            "https://vllm.ai/blog/2026-05-06-mooncake-store",
        ],
    },
]


def render_markdown(rows: list[dict]) -> str:
    lines = [
        "# Prior-Art Boundary",
        "",
        "This table is a bounded source/API audit, not a live comparator run. "
        "It treats existing runtimes, orchestration layers, and agentic-serving "
        "systems as serious prior art and avoids the unsafe claim that existing "
        "systems lack KV-retention primitives.",
        "",
        "| Runtime | Strongest relevant primitives | Can express useful resident footprint? | Can refuse/defer active under protected resident claim? | Can separate no-admit from active allocation? | Claim-level harm telemetry? | Boundary verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {runtime} | {strongest_relevant_primitives} | "
            "{useful_resident_footprint} | {active_defer_under_claim} | "
            "{separate_no_admit} | {claim_level_harm_telemetry} | "
            "{boundary_verdict} |".format(**row)
        )

    lines.extend(["", "## Evidence", ""])
    for row in rows:
        lines.append(f"### {row['runtime']}")
        for ref in row["evidence"]:
            lines.append(f"- `{ref}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"rows": ROWS}
    (OUT_DIR / "prior_art_boundary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    (OUT_DIR / "prior_art_boundary.md").write_text(render_markdown(ROWS))
    print(render_markdown(ROWS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
