# Pydev Connector Failure-Semantics Repetition Summary

Scope: local patched pydev vLLM OffloadingConnector mechanism only; not upstream vLLM support, production offload performance, or scheduler-native admission/refusal.

| Scenario | Runs | Observation pass | Failure-outcome pass | Event-sequence valid | Resident median/p95 s | Reuse median/p95 s | Event bytes median/p95 | Analyzer median/p95 ns | Failure->outcome median/p95 ns | Restore-failed->refused median/p95 ns | Outcomes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `claimed_load_failure` | 31 | 0/31 (0.000) | 31/31 (1.000) | 31/31 (1.000) | 0.18286/0.203255 | 0.002932/0.003262 | 22782/22782 | 94610/106410 | 163680/182290 | 87650/93850 | active_request_refused=31 |
| `fallback_recompute` | 11 | 11/11 (1.000) | 0/11 (0.000) | 11/11 (1.000) | 0.188555/0.209265 | 0.104362/0.10929 | 29138/29140 | 110151/118181 | - | - | fallback_recompute_not_claim_satisfaction=11 |
| `generic_counter_only` | 2 | 0/2 (0.000) | 0/2 (0.000) | 2/2 (1.000) | - | - | 386/394 | 19400/19580 | - | - | no_request_records=2 |
| `success_no_event_path` | 31 | 0/31 (0.000) | 0/31 (0.000) | 31/31 (1.000) | 0.199507/0.211063 | 0.097991/0.103685 | 0/0 | 16170/17460 | - | - | served=31 |
| `success_path` | 31 | 31/31 (1.000) | 0/31 (0.000) | 31/31 (1.000) | 0.181699/0.204786 | 0.091195/0.105039 | 18196/18196 | 70600/79680 | - | - | served=31 |
| `unclaimed_load_failure` | 11 | 0/11 (0.000) | 0/11 (0.000) | 11/11 (1.000) | 0.187065/0.217786 | 0.002677/0.00297 | 5553/5553 | 38550/41540 | - | - | not_claim_scoped=11 |
| `wrong_claim_failure` | 11 | 11/11 (1.000) | 0/11 (0.000) | 11/11 (1.000) | 0.186566/0.220388 | 0.092683/0.116147 | 18553/18553 | 69960/81210 | - | - | served=11 |
