# ResidentClaim Conformance Artifact

Generated on May 17, 2026 for Paper 1:

> Resident KV Claims: A Conformance Contract for Future Reuse under Active KV Pressure

## Command

From the repository root:

```bash
make conformance
```

The direct vLLM BlockPool probes use `VLLM_AUDIT_PYTHON` when it is set, or the
current Python interpreter otherwise. See `docs/vllm_target.md` for the patched
vLLM branch and environment variables.

## Result

`results.json` reports `8 / 8` passing litmus tests:

| Litmus | Status |
|---|---|
| L1 no accepted claim, no claim harm | pass |
| L2 write no-admit separation | pass |
| L3 accepted hard-claim infeasibility | pass |
| L4 demotion before loss | pass |
| L5 expiry before loss | pass |
| L6 materialization predicate failure | pass |
| L7 trace reconstruction | pass |
| L8 soft priority is not hard-claim lowering | pass |

The canonical L3 trace contains the direct active/refusal attribution:

```json
{
  "event": "active_request_refused",
  "blocking_claim_ids": ["claim:resident"],
  "protected_resident_blocks": 60,
  "active_live_blocks_required": 70,
  "resident_plus_active_blocks": 130,
  "usable_blocks": 80,
  "capacity_shortfall_blocks": 50,
  "feasibility": "infeasible_preserve_resident_and_active"
}
```

## Key Files

| File | Role | SHA-256 |
|---|---|---|
| `results.json` | Machine-readable conformance results | `94f8623bde219a61aa5581bc10b15dbcb87244c404bd4e867c6855d6482e73cf` |
| `summary.md` | Human-readable conformance table | `87f85af8aef4af15e827c51d8350faee10360976b3cf2272fd83f4bf388b3cb0` |
| `L3_hard_claim_infeasibility.jsonl` | Canonical claim acceptance/materialization/refusal trace | `a0ce8df42f2dc660ceecbc555138847a028ee541f2a383f8811006500329714b` |
| `L3_hard_claim_infeasibility_summary.json` | Canonical trace summary | `51215b027f99842c7e224e07817bb12ecd5bd28ef58866d909a15c82dbdbbcb7` |
| `../live_scheduler_pressure/summary.json` | End-to-end `vllm.LLM.generate` pressure trace | `6eade50b7735cee3cc74ba9fd892f67672d823a236570a743390f1d2cf5e8d3b` |
| `../capacity_sweep/capacity_sweep_results.json` | Capacity-region sweep | `52e6235970a6091ef8ef2cf389d91c77b63a742f3f84fdc15965cff8ad863192` |
| `../prior_art/prior_art_boundary.json` | Prior-art semantic boundary matrix | `2c94abb8b244a20ee851e509280768726b82141ed4e9e4fc8990c944318f732b` |
