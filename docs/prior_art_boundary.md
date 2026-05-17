# Prior-Art Boundary

This repo must treat existing runtimes as serious systems.

## Safe Claim

Existing runtimes expose many useful primitives. The missing piece is the unified claim lifecycle:

```text
prediction
-> useful-footprint claim
-> active-live feasibility check
-> explicit conflict action
-> future reusable admission decision
-> claim-level harm/refusal telemetry
```

## Unsafe Claim

Do not claim that current runtimes lack KV retention primitives.

That is false for the current evidence. TensorRT-LLM in particular exposes priority, duration, eviction, scheduler, offload, and event mechanisms that overlap strongly with the desired toolbox.

## Comparator Checklist

For vLLM, SGLang, and TensorRT-LLM, document:

- prefix-cache or context-block reuse surface;
- retention priority or equivalent;
- hard pin/reserve behavior, if exposed;
- active request scheduler behavior under no-evict or protected blocks;
- offload and demotion support;
- write/no-write admission support;
- telemetry events and whether they attach to resident claims;
- whether public API can represent useful-footprint thresholds;
- what happens in the 60 resident / 70 active / 80 usable case.

## Current Starting Hypothesis

| Runtime | Starting position |
|---|---|
| vLLM | Clean live counterexample and easiest implementation target. |
| SGLang | Strong radix-cache/protected-accounting/offload pieces; needs source or live pressure probe. |
| TensorRT-LLM | Strongest prior art; must be bounded carefully, not dismissed. |

## Required Output

Produce a table with this shape:

| Runtime | Strongest relevant primitives | Can express useful resident footprint? | Can refuse/defer active under protected resident claim? | Can separate no-admit from active allocation? | Claim-level harm telemetry? | Boundary verdict |
|---|---|---|---|---|---|---|

Use source links, docs, or live traces for every cell.

Generate the current boundary artifact with:

```bash
make prior-art
```
