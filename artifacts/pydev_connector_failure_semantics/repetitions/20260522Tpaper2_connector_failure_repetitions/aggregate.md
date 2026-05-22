# Pydev Connector Failure-Semantics Repetition Summary

Scope: local patched pydev vLLM OffloadingConnector mechanism only; not upstream vLLM support, production offload performance, or scheduler-native admission/refusal.

| Scenario | Runs | Observation pass | Failure-outcome pass | Event-sequence valid | Resident median/p95 s | Reuse median/p95 s | Event bytes median/p95 | Analyzer median/p95 ns | Failure->outcome median/p95 ns | Restore-failed->refused median/p95 ns | Outcomes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `claimed_load_failure` | 30 | 0/30 (0.000) | 30/30 (1.000) | 30/30 (1.000) | 0.19142/0.203255 | 0.0030435/0.003262 | 22782/22782 | 95505/106410 | 165430/182290 | 88445/93850 | active_request_refused=30 |
| `fallback_recompute` | 10 | 10/10 (1.000) | 0/10 (0.000) | 10/10 (1.000) | 0.194839/0.209265 | 0.0990155/0.10929 | 29138.5/29140 | 111986/118181 | - | - | fallback_recompute_not_claim_satisfaction=10 |
| `generic_counter_only` | 1 | 0/1 (0.000) | 0/1 (0.000) | 1/1 (1.000) | - | - | 394/394 | 19580/19580 | - | - | no_request_records=1 |
| `success_no_event_path` | 30 | 0/30 (0.000) | 0/30 (0.000) | 30/30 (1.000) | 0.198664/0.211063 | 0.097817/0.103508 | 0/0 | 16135/17460 | - | - | served=30 |
| `success_path` | 30 | 30/30 (1.000) | 0/30 (0.000) | 30/30 (1.000) | 0.181648/0.204786 | 0.091304/0.105039 | 18196/18196 | 70705/79680 | - | - | served=30 |
| `unclaimed_load_failure` | 10 | 0/10 (0.000) | 0/10 (0.000) | 10/10 (1.000) | 0.182716/0.202425 | 0.0026665/0.002897 | 5553/5553 | 38305/41540 | - | - | not_claim_scoped=10 |
| `wrong_claim_failure` | 10 | 10/10 (1.000) | 0/10 (0.000) | 10/10 (1.000) | 0.192827/0.220388 | 0.094687/0.116147 | 18553/18553 | 70315/81210 | - | - | served=10 |
