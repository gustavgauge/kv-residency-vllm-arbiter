# Prior-Art Boundary

This table is a bounded source/API audit, not a live comparator run. It treats existing runtimes, orchestration layers, and agentic-serving systems as serious prior art and avoids the unsafe claim that existing systems lack KV-retention primitives.

| Runtime | Strongest relevant primitives | Can express useful resident footprint? | Can refuse/defer active under protected resident claim? | Can separate no-admit from active allocation? | Claim-level harm telemetry? | Boundary verdict |
|---|---|---|---|---|---|---|
| vLLM | Hash-chain prefix blocks, request priority, prefix-cache events, internal request-to-block maps, and the prototype hooks. | Prototype yes; native public API no. | Prototype yes via hard exclusion; native no resident-claim API. | Prototype yes; native public API not found. | Prototype yes; native telemetry insufficient. | Implementation target and live counterexample: native/no-admit can serve active while harming resident reusable KV below 130 usable blocks; hard exclusion converts conflict into active refusal. |
| SGLang | Radix cache for finished and unfinished requests, priority-aware eviction, lock refs, protected_size/evictable_size accounting. | Partial: radix paths and protected accounting exist, but no audited first-class useful-footprint claim/refusal lifecycle. | Partial/unclear from source audit: lock refs protect resident nodes from eviction, but a future-reuse claim admission contract and explicit active conflict action were not identified. | Partial: finished insertion can be disabled in code paths, but this is not the same as the active/resident contract. | Not established by this audit. | Serious comparator with stronger resident-accounting pieces than native vLLM; still not shown to expose the full claim lifecycle. |
| TensorRT-LLM | Block reuse, prioritized LRU, retention priority/duration, host offload, scheduler no-evict policies, internal pinning, and KV events. | Partial: token-range retention priorities can describe valuable spans, but audited API is priority/duration rather than useful-footprint claim admission/refusal. | Partial: scheduler policies can pause/restart or guarantee no eviction once started, and internal pinning exists; not shown as a single future-resident claim conflict contract. | Not established as the same per-request active/no-write split. | Strong block events and priority/cache-level fields; not full future-claim harm/refusal telemetry. | Strongest prior art. It refutes any claim that runtimes lack primitives, but supports the narrower claim that the full active/resident ownership contract is fragmented. |
| Dynamo | Agent hints, cache-control metadata, TTL-style pinning, KV-aware routing, prefetch hooks, and KV-event-driven orchestration. | Partial: orchestration metadata can express reuse intent, but the audited docs do not define a backend-accepted materialization predicate. | Partial/unclear: routing may avoid conflict, but active refusal attributed to a resident claim is not the documented unit. | Partial: cache-control can affect retention, but active-live allocation separation is not the same public contract. | KV events support routing and cache indexes; accepted-claim harm/refusal blame is not established. | Strong orchestration comparator. It supports the need for a portable backend conformance contract rather than refuting it. |
| Continuum | TTL-based KV retention for multi-turn agents, queueing/reload cost modeling, vLLM implementation, and agentic workload evaluation. | Strong for agentic TTL retention, but framed as retention policy rather than portable accepted-claim materialization conformance. | Partial: retained KV is modeled as GPU-memory opportunity cost, but claim-level active refusal semantics are not the contribution. | Not the central public mechanism. | Not established as accepted-claim harm/refusal telemetry. | Closest systems threat for a later admission-control paper; Path 1 must distinguish contract semantics from TTL retention policy. |
| KVFlow | Workflow-structure-aware prefix caching and CPU-GPU KV prefetching for LLM-based multi-agent workflows. | Strong future-reuse policy comparator; not framed as an accepted runtime responsibility with predicate-breaking telemetry. | Not established as active/resident infeasibility contract. | Not established as the same semantic split. | Not established by this audit. | Threatens broad predictive-residency language; less direct against the conformance-contract framing. |
| Pie | Programmable inference handlers with application-specific access to serving-loop behavior and KV strategies. | Programmability may express custom policies, but does not itself define a portable ResidentClaim contract. | Handler-dependent; not a backend conformance guarantee. | Handler-dependent. | Handler-dependent; not a portable schema. | Shows that implementation flexibility differs from runtime-level semantic accountability. |
| Marconi | Admission and eviction based on reuse likelihood and compute savings relative to KV footprint. | Strong value/footprint comparator, especially for broad admission claims; not an active/resident claim conformance contract. | Not established by this audit. | Not established by this audit. | Not established by this audit. | Weakens broad value-aware novelty claims; compatible with a narrow contract/conformance contribution. |
| vLLM + Mooncake | Distributed KV storage and transfer for KV-cache-centric disaggregated serving. | Storage can preserve or restore KV beyond local GPU capacity, but does not define the accepted-claim contract by itself. | May route or transfer around local conflicts; claim-level refusal semantics are still a separate contract question. | Not established as the same semantic split. | Storage events are not the same as predicate-level claim harm/refusal. | Relevant capacity-extension path; complements rather than replaces active/resident conformance semantics. |

## Evidence

### vLLM
- `artifact:capacity_sweep/capacity_sweep_summary.md`
- `source:vllm/v1/core/block_pool.py`
- `source:vllm/v1/core/kv_cache_manager.py`

### SGLang
- `sglang@bbe9c7e:python/sglang/srt/mem_cache/radix_cache.py:446`
- `sglang@bbe9c7e:python/sglang/srt/mem_cache/radix_cache.py:493`
- `sglang@bbe9c7e:python/sglang/srt/mem_cache/radix_cache.py:568`
- `sglang@bbe9c7e:python/sglang/srt/mem_cache/radix_cache.py:594`
- `sglang@bbe9c7e:python/sglang/srt/mem_cache/radix_cache.py:631`

### TensorRT-LLM
- `tensorrt-llm@566fd230:docs/source/features/kvcache.md:7`
- `tensorrt-llm@566fd230:docs/source/features/kvcache.md:15`
- `tensorrt-llm@566fd230:docs/source/features/kvcache.md:17`
- `tensorrt-llm@566fd230:docs/source/features/kvcache.md:25`
- `tensorrt-llm@566fd230:docs/source/features/kvcache.md:102`
- `tensorrt-llm@566fd230:cpp/include/tensorrt_llm/executor/executor.h:576`
- `tensorrt-llm@566fd230:cpp/include/tensorrt_llm/executor/types.h:227`
- `tensorrt-llm@566fd230:cpp/tensorrt_llm/batch_manager/evictionPolicy.cpp:140`
- `tensorrt-llm@566fd230:cpp/tensorrt_llm/executor/executorImpl.cpp:2241`
- `tensorrt-llm@566fd230:cpp/include/tensorrt_llm/executor/executor.h:1713`
- `tensorrt-llm@566fd230:cpp/include/tensorrt_llm/executor/executor.h:1751`

### Dynamo
- `https://docs.dynamo.nvidia.com/dynamo/dev/user-guides/agents`
- `https://docs.dynamo.nvidia.com/dynamo/dev/user-guides/agents/sg-lang-for-agentic-workloads`

### Continuum
- `https://arxiv.org/abs/2511.02230`

### KVFlow
- `https://arxiv.org/abs/2507.07400`

### Pie
- `https://arxiv.org/abs/2510.24051`

### Marconi
- `https://arxiv.org/abs/2411.19379`

### vLLM + Mooncake
- `https://vllm.ai/blog/2026-05-06-mooncake-store`
