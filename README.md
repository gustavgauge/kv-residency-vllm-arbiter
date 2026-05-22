# Resident KV Claims vLLM Arbiter

This repository is the public runtime artifact for **Resident KV Claims: A
Conformance Contract for Future Reuse under Active KV Pressure**. It contains a
minimal vLLM prototype, litmus tests, generated traces, and analysis scripts for
checking whether future KV reuse is exposed as an accepted runtime claim rather
than only as an eviction hint.

The central question is simple:

```text
protected resident KV + active live KV <= usable KV memory
```

When that inequality fails, a runtime should not turn accepted resident claims
into ordinary cache victims without reporting the outcome. It should
preserve, demote, expire, offload, defer, refuse, or otherwise report an
explicit claim-level outcome.

## What This Artifact Demonstrates

- **No accepted claim, no harm:** ordinary prefix-cache eviction is not labeled
  claim harm unless a resident claim was accepted first.
- **Write no-admit separation:** refusing future reuse for an active request
  does not reduce that request's active live KV footprint.
- **Hard claim infeasibility:** a protected resident claim can make active-side
  refusal/defer the explicit outcome under insufficient KV capacity.
- **Materialization semantics:** preserving scattered blocks is different from
  preserving the useful leading-prefix predicate the application cares about.
- **Conformance boundary:** soft priority and TTL-like retention are useful
  primitives but are not a sound lowering of hard resident claims by themselves.
- **Offload lifecycle/outcome witness:** a reference state-machine hook emits
  claim-scoped offload, restore-before-reuse, restoration failure, and
  claim-scoped refusal events. This is a conformance witness, not production
  host-offload performance.

## Repository Layout

```text
artifacts/
  conformance/              # ResidentClaim litmus results and summaries
  offload_lifecycle/        # reference offload hook traces and metrics
  native_blockpool/         # native allocator counterexample trace
  no_admit/                 # write no-admit negative control
  claim_metadata/           # accepted-claim metadata trace
  hard_claim/               # hard resident claim refusal trace
  capacity_sweep/           # capacity-region sweep
  claim_lifecycle/          # demotion/expiry-before-loss traces
  live_scheduler_pressure/  # vllm.LLM.generate pressure-path evidence
  prior_art/                # semantic boundary matrix
docs/
  contract.md               # ResidentClaim contract
  telemetry_schema.md       # event schema
  evaluation_plan.md        # litmus and sweep plan
  prior_art_boundary.md     # comparator checklist
  vllm_target.md            # patched-vLLM setup
patches/
  vllm_prototype_notes.md   # files changed and behavior boundary
scripts/                    # artifact regeneration and analysis
src/kv_vllm_arbiter/        # conformance and trace-summary helpers
tests/                      # fast regression tests
```

## Quick Start

Run the pure Python checks:

```bash
uv run --with pytest pytest -q
python scripts/check_env.py
python scripts/generate_expected_matrix.py
```

The vLLM-backed probes require a Python environment that imports the patched
vLLM prototype. Configure it explicitly:

```bash
export VLLM_AUDIT_PYTHON=/path/to/python-with-patched-vllm
export VLLM_KV_RESIDENCY_VLLM_SOURCE=/path/to/vllm-checkout
export VLLM_KV_RESIDENCY_MODEL=HuggingFaceTB/SmolLM2-135M-Instruct
```

The companion vLLM branch should be named:

```text
resident-kv-claims-vllm-prototype
```

## Regenerate Artifacts

```bash
make native-blockpool-probe
make native-summary
make no-admit-probe
make claim-metadata-probe
make hard-claim-probe
make classify-hard-claim
make capacity-sweep
make claim-lifecycle
make conformance
make prior-art
make live-scheduler-pressure
python scripts/run_offload_lifecycle_hook_eval.py
```

`make live-scheduler` is optional supporting evidence for prefix-cache hits and
request-level latency through `vllm.LLM.generate`; the paper contribution does
not rely on a speedup claim.

## Key Evidence

- `artifacts/conformance/results.json`: seven trace/materialization checks plus
  one capability-classification check.
- `artifacts/conformance/L3_hard_claim_infeasibility.jsonl`: accepted claim,
  materialized predicate, active infeasibility, and attributed refusal.
- `artifacts/capacity_sweep/capacity_sweep_results.json`: transition around
  the `60 resident + 70 active = 130 usable blocks` boundary.
- `artifacts/live_scheduler_pressure/summary.json`: live scheduler-path pressure
  trace with protected resident headroom affecting active request handling.
- `artifacts/prior_art/prior_art_boundary.md`: semantic comparison against
  adjacent runtime primitives.

## Scope

This is a semantics and conformance artifact. It is not a production vLLM fork,
not a performance benchmark, not a learned predictor, and not a claim that
existing runtimes lack KV-retention primitives. The claim is narrower:
accepted future-reuse intent needs materialization predicates, explicit
active/resident conflict outcomes, and claim-level telemetry.
