# Patches

This directory contains the vLLM prototype patch and short patch notes.

Patch contents:

- `vllm_resident_claim_prototype.patch`: patch against vLLM base commit
  `b1388b1fbf5aaef47937fabe98931211684666a6`.
- `vllm_runtime_metadata_joinability.patch`: incremental metadata patch against
  the local `resident-kv-claims-vllm-prototype` checkout. It adds
  request-joinable runtime metadata JSONL and proxy/runtime id fields on
  arbiter telemetry.
- `vllm_pressure_capacity_telemetry.patch`: incremental telemetry correction
  against the local checkout after `vllm_runtime_metadata_joinability.patch`.
  It prevents missing capacity from being encoded as `usable_blocks=0` and emits
  actual allocatable capacity on scheduler pressure/admission rows.
- Local prototype head used while preparing this artifact: `743e2f9`
  (`Fix resident KV leading-prefix predicate fidelity`).
- `vllm_prototype_notes.md`: behavior boundary and evidence commands.

The patch is prototype-grade. It is meant to make the paper's conformance
behavior inspectable, not to define an upstream-ready API.
