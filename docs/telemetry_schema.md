# Telemetry Schema

Claim-level telemetry is part of the contribution. Without it, reviewers can argue that cache-hit outputs are only indirect symptoms.

## Event Format

Use JSON Lines for experiment traces.

Every event should include:

```json
{
  "schema_version": 1,
  "timestamp_ns": 0,
  "run_id": "string",
  "event": "string",
  "request_id": "string",
  "claim_id": "string or null",
  "prefix_id": "string or null",
  "policy": "string",
  "usable_blocks": 0
}
```

Lifecycle/outcome hook events also include an explicit ordering and identity
tuple:

```json
{
  "event_sequence": 1,
  "lifecycle_generation": 1,
  "offload_generation": 1,
  "predicate_id": "predicate:leading-prefix-8",
  "materialization_predicate": "leading_prefix_at_least(8)",
  "reusable_object_id": "kv-object:reference-prefix",
  "request_token_map_id": "token-map:reference-prefix-v1",
  "cache_identity": "patched-vllm-reference-cache:v1"
}
```

## Event Types

| Event | Required meaning |
|---|---|
| `resident_claim_created` | A future-reuse resident claim was registered. |
| `resident_block_materialized` | A logical resident block maps to a physical KV block. |
| `resident_claim_accepted` | Runtime accepted a resident claim under current capacity. |
| `resident_claim_refused` | Runtime refused a resident claim. |
| `active_request_admitted` | Active request entered service. |
| `active_request_deferred` | Active request was delayed due to resident protection or capacity. |
| `active_request_refused` | Active request was refused under current claims and capacity. |
| `future_reuse_admitted` | Produced active KV was admitted for future reuse. |
| `future_reuse_denied` | Produced active KV was not admitted for future reuse. |
| `allocation_victim_selected` | Allocator selected a physical block as a victim. |
| `resident_claim_harmed` | A resident claim lost useful footprint or protected blocks. |
| `resident_claim_preserved` | Resident claim survived an active pressure event. |
| `resident_claim_relaxed` | Resident claim was downgraded by policy. |
| `resident_claim_offloaded` | Resident state moved to a slower tier. |
| `resident_claim_restore_required` | Later reuse reached a claimed object that cannot satisfy the predicate from primary-resident state alone. |
| `resident_claim_restored` | Claimed state was restored from the offload tier before predicate-satisfying reuse. |
| `resident_claim_reuse_after_restore` | Reuse satisfied the materialization predicate after ordered restoration. |
| `resident_claim_restoration_failed` | Controlled restoration-unavailable/failure path fired for a claim. |
| `active_live_bounded` | Active live KV was bounded by recompute, offload, or another mechanism. |

## Block Event Fields

Block-level events should include:

```json
{
  "logical_block_position": 0,
  "physical_block_id": 0,
  "block_hash": "string or null",
  "ref_count": 0,
  "free_queue_rank": 0,
  "is_protected_resident": true,
  "victim_reason": "string or null"
}
```

## Claim Fields

Claim events should include:

```json
{
  "resident_blocks_required": 0,
  "resident_blocks_materialized": 0,
  "useful_threshold_blocks": 0,
  "leading_blocks_survived": 0,
  "predicted_value": 0.0,
  "value_lost": 0.0,
  "confidence": 0.0,
  "protection_mode": "hard_exclude"
}
```

Offload lifecycle events should include either concrete `block_ids` or
`block_count_footprint`, plus `cache_tier`, `cache_tier_from`,
`cache_tier_to`, and `restored_from_offload_tier` when restoration is claimed.
Fallback recompute is not a restoration event for the offloadable contract.

Restoration-failure events must carry `claim_scoped_outcome_type` and
`outcome_claim_id`, and the allowed outcome types are `refusal`, `demotion`,
`expiry`, and `harm`.

For `predicate="leading_prefix_at_least"`, `resident_blocks_materialized` is not
the materialization predicate by itself. The runtime must evaluate
`leading_blocks_survived >= resident_blocks_required` over logical block
positions. A trace that preserves many tail blocks while losing logical block
0 is not materialized, even if the raw surviving-block count is high.

## Active Request Fields

Active events should include:

```json
{
  "active_live_blocks_required": 0,
  "active_live_blocks_current": 0,
  "active_chunks": [20, 20, 20, 10],
  "future_reuse_requested": true,
  "future_reuse_admitted": false,
  "arbiter_action": "defer_active"
}
```

## Minimum Acceptance Trace

For the 60/70/80 protected-resident run, the trace must show:

1. 60 resident blocks materialized and protected.
2. Active request requires 70 live blocks.
3. Usable capacity is 80 blocks.
4. Arbiter rejects or defers active allocation, or selects another explicit action.
5. No protected resident block appears as an ordinary victim.
6. Resident claim is preserved or explicitly demoted/offloaded with value accounting.
