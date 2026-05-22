# Public Artifact Notes

This branch is public evidence for the ResidentClaim lifecycle/outcome
mechanism. It records a local patched vLLM connector mechanism and accompanying
analysis harnesses for checking claim-scoped offload, restore-before-reuse,
controlled restoration failure, scheduler-side invalid-KV-load boundary
outcomes, and explicit active-request outcome events.

This is not upstream or native vLLM ResidentClaim support. It is not a
production support statement, a performance benchmark, or a claim that vLLM
ships the ResidentClaim contract. The calibrated claim is narrower: a local
patched `OffloadingConnector` path can carry the lifecycle/outcome evidence
needed by the ResidentClaim contract under controlled failure injection. The
strongest checked-in run adds scheduler-side failure/refusal telemetry at the
invalid-KV-load handling boundary; it is still not pre-admission refusal.

## Historical Provenance Fields

Generated traces and summaries may contain absolute local paths, workstation
directory names, selected Python interpreter paths, and historical local vLLM
commit SHAs. Those fields are provenance artifacts from the original run. They
are not credentials and are not portable commands. They should not be read as
instructions for reproducing the artifact on another machine.

Canonical reproduction should use the environment-variable based commands in
the README and setup docs:

```bash
export VLLM_AUDIT_PYTHON=/path/to/python-with-patched-vllm
export VLLM_KV_RESIDENCY_VLLM_SOURCE=/path/to/vllm-checkout
export VLLM_KV_RESIDENCY_MODEL=HuggingFaceTB/SmolLM2-135M-Instruct
```

The historical connector-level repeated run set keeps its generated run-set id,
`20260522Tpaper2_connector_failure_repetitions`, because changing it would
rewrite provenance. The canonical scheduler-boundary repeated run set is
`20260522Tresident_claim_scheduler_boundary`.

## Public Evidence Footprint

The checked-in repeated-run footprint keeps the aggregate files and one
representative raw repetition per scenario. Full raw repetitions can be
regenerated locally with the repetition harness. The retained aggregate files
are:

- `artifacts/pydev_connector_failure_semantics/repetitions/20260522Tresident_claim_scheduler_boundary/aggregate.json`
- `artifacts/pydev_connector_failure_semantics/repetitions/20260522Tresident_claim_scheduler_boundary/aggregate.md`
- `artifacts/pydev_connector_failure_semantics/repetitions/20260522Tresident_claim_scheduler_boundary/normalized_summaries.jsonl`
- `artifacts/pydev_connector_failure_semantics/repetitions/20260522Tresident_claim_scheduler_boundary/manifest.json`

Representative raw traces are retained under each scenario's `rep-001`
directory. Extra raw repetition directories and `run.log` files are omitted from
public git because they mostly duplicate the aggregate rows and contain
environment noise. The manifest remains a historical record of the full
generated run set and may enumerate raw files that are reproducible but no
longer checked in.
