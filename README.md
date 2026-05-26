# Resident KV Claims vLLM Arbiter

This repository is the public runtime artifact for **Resident KV Claims: A
Conformance Contract for Future Reuse under Active KV Pressure**. It contains a
minimal vLLM prototype, litmus tests, generated traces, and analysis scripts for
checking whether future KV reuse is exposed as an accepted runtime claim rather
than only as an eviction hint.

## For Runtime Maintainers

This artifact checks whether accepted future-reuse KV state remains observable
and attributable under active KV pressure. It is a conformance/litmus artifact,
not a production vLLM fork, not a speedup benchmark, and not a claim that
upstream vLLM implements ResidentClaims.

Start with the spec before the traces.

## Spec / Contract

The contract is defined in [`docs/contract.md`](docs/contract.md). It names the
active/resident inequality, ResidentClaim objects, future-reuse admission,
protection modes, and required arbiter actions. Use it as the first file when
mapping this artifact onto another runtime.

The supporting evidence entry points are:

- `artifacts/conformance/README.md`: generated conformance summary;
- `patches/vllm_prototype_notes.md`: prototype boundary and changed files;
- `artifacts/live_scheduler_pressure/summary.json`: scheduler-path pressure
  evidence.

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

## Repository Layout

```text
artifacts/
  conformance/              # ResidentClaim litmus results and summaries
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

### No Patched vLLM Required

These commands check the local Python helpers and expected semantic matrix. They
do not import vLLM.

```bash
uv run --with pytest pytest -q
uv run python scripts/check_env.py
uv run python scripts/generate_expected_matrix.py
```

### Patched vLLM Required

The checked-in `artifacts/` directory is the public evidence bundle.
Regenerating vLLM-backed traces requires a Python environment that imports the
patched vLLM prototype. Configure it explicitly:

```bash
export VLLM_AUDIT_PYTHON=/path/to/python-with-patched-vllm
export VLLM_KV_RESIDENCY_VLLM_SOURCE=/path/to/vllm-checkout
export VLLM_KV_RESIDENCY_MODEL=HuggingFaceTB/SmolLM2-135M-Instruct
```

The companion vLLM branch should be named:

```text
resident-kv-claims-vllm-prototype
```

## Regenerate vLLM-Backed Artifacts

Run these only after configuring `VLLM_AUDIT_PYTHON` for the patched vLLM
prototype. Without that runtime, the BlockPool and scheduler probes will fail to
import `vllm`.

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

## What Would Change This Artifact

This artifact should change if a runtime exposes a native path, event, or
invariant that provides the obligations the contract requires:

- accepted claim identity;
- a materialization predicate for useful future reuse;
- ordered lifecycle events;
- a claim-scoped refusal, failure, demotion, expiry, or harm outcome under
  active/resident pressure.

Corrections to the boundary are useful. General endorsements are not required.

## Scope

This is a semantics and conformance artifact. It is not a production vLLM fork,
not a performance benchmark, not a learned predictor, and not a claim that
existing runtimes lack KV-retention primitives. The claim is narrower:
accepted future-reuse intent needs materialization predicates, explicit
active/resident conflict outcomes, and claim-level telemetry.
