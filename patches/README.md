# Patches

This directory contains the vLLM prototype patch and short patch notes.

Patch contents:

- `vllm_resident_claim_prototype.patch`: patch against vLLM base commit
  `b1388b1fbf5aaef47937fabe98931211684666a6`.
- `vllm_runtime_metadata_joinability.patch`: incremental metadata patch against
  the local `resident-kv-claims-vllm-prototype` checkout at `1954509`. It adds
  request-joinable runtime metadata JSONL and proxy/runtime id fields on
  arbiter telemetry.
- `vllm_prototype_notes.md`: behavior boundary and evidence commands.

The patch is prototype-grade. It is meant to make the paper's conformance
behavior inspectable, not to define an upstream-ready API.
