# vLLM Target Setup

This artifact is designed to run against a patched vLLM checkout or a Python
environment where the same patch is installed. The patch source is the vLLM
branch:

```text
resident-kv-claims-vllm-prototype
```

The branch is based on upstream commit:

```text
b1388b1fbf5aaef47937fabe98931211684666a6
```

The local prototype head used for the predicate-fidelity update is:

```text
743e2f9 Fix resident KV leading-prefix predicate fidelity
```

## Environment Variables

Configure the runtime location explicitly:

```bash
export VLLM_AUDIT_PYTHON=/path/to/python-with-patched-vllm
export VLLM_KV_RESIDENCY_VLLM_SOURCE=/path/to/vllm-checkout
export VLLM_KV_RESIDENCY_MODEL=HuggingFaceTB/SmolLM2-135M-Instruct
```

`VLLM_AUDIT_PYTHON` is used by the make targets and connector repetition
harnesses that import vLLM. Most one-shot scripts fall back to the current
Python interpreter when it is not set; the connector repetition harness requires
an explicit runner because it launches child scenario processes.
`VLLM_KV_RESIDENCY_VLLM_SOURCE` is optional. The source tree is prepended to
`sys.path` by connector harnesses when set, and by other live probes when
`VLLM_KV_RESIDENCY_USE_SOURCE_TREE=1`.

Before collecting live evidence, confirm that the selected interpreter imports
the patched runtime:

```bash
$VLLM_AUDIT_PYTHON - <<'PY'
import inspect, vllm
print(vllm.__version__)
print(inspect.getfile(vllm))
PY
```

The imported vLLM tree should include:

```text
vllm/v1/core/kv_residency_telemetry.py
```

## Patch Boundary

The prototype exposes:

- active request admission, deferral, and refusal telemetry;
- write no-admit as a future-reuse admission control;
- resident claim metadata on materialized reusable KV blocks;
- hard resident exclusion from ordinary free-block victims;
- claim expiry/demotion events before loss;
- claim harm or post-release block-loss events after predicate-breaking loss;
- scheduler-visible refusal under protected resident pressure.

The prototype does not claim production performance, upstream API stability,
learned prediction, fairness policy, or multi-backend portability.

## Artifact Commands

Allocator-level probes:

```bash
make native-blockpool-probe
make native-summary
make no-admit-probe
make claim-metadata-probe
make hard-claim-probe
make classify-hard-claim
make capacity-sweep
```

Contract and comparison artifacts:

```bash
make conformance
make claim-lifecycle
make prior-art
```

Live scheduler probes:

```bash
make live-scheduler
make live-scheduler-pressure
```
