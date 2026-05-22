# Pydev Connector Failure-Semantics Repetition Summary

Scope: local patched pydev vLLM OffloadingConnector mechanism with scheduler-side invalid-KV-load boundary evidence; not upstream vLLM support, production offload performance, or scheduler-native pre-admission refusal.

| Scenario | Runs | Observation pass | Failure-outcome pass | Event-sequence valid | Resident median/p95 s | Reuse median/p95 s | Event bytes median/p95 | Analyzer median/p95 ns | Failure->outcome median/p95 ns | Restore-failed->refused median/p95 ns | Outcomes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `claimed_load_failure` | 30 | 0/30 (0.000) | 30/30 (1.000) | 30/30 (1.000) | 0.187152/0.204366 | 0.003159/0.003468 | 26702/26702 | 128560/146290 | 151544/174749 | 80319.5/92189 | active_request_refused=30 |
| `fallback_recompute` | 10 | 10/10 (1.000) | 0/10 (0.000) | 10/10 (1.000) | 0.189968/0.204347 | 0.096011/0.107244 | 31103/31104 | 146064/158690 | - | - | fallback_recompute_not_claim_satisfaction=10 |
| `generic_counter_only` | 1 | 0/1 (0.000) | 0/1 (0.000) | 1/1 (1.000) | - | - | 394/394 | 25750/25750 | - | - | no_request_records=1 |
| `ordinary_offload_no_claim` | 10 | 0/10 (0.000) | 0/10 (0.000) | 10/10 (1.000) | 0.179218/0.204158 | 0.0904345/0.103545 | 4603/4603 | 41535/46690 | - | - | served=10 |
| `success_no_event_path` | 30 | 0/30 (0.000) | 0/30 (0.000) | 30/30 (1.000) | 0.18047/0.203399 | 0.0912185/0.104254 | 0/0 | 22195/24850 | - | - | served=30 |
| `success_path` | 30 | 30/30 (1.000) | 0/30 (0.000) | 30/30 (1.000) | 0.186532/0.204368 | 0.0933355/0.104347 | 18213/18213 | 79685/93420 | - | - | served=30 |
| `unclaimed_load_failure` | 10 | 0/10 (0.000) | 0/10 (0.000) | 10/10 (1.000) | 0.191329/0.203023 | 0.0027965/0.00298 | 5567/5568 | 47510/51000 | - | - | not_claim_scoped=10 |
| `wrong_claim_failure` | 10 | 10/10 (1.000) | 0/10 (0.000) | 10/10 (1.000) | 0.200806/0.203255 | 0.102791/0.1047 | 18570/18570 | 86470/92699 | - | - | served=10 |
