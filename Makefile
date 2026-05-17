PYTHON ?= python
VLLM_AUDIT_PYTHON ?= python

.PHONY: test matrix doctor native-blockpool-probe native-summary no-admit-probe claim-metadata-probe hard-claim-probe classify-hard-claim capacity-sweep prior-art live-scheduler live-scheduler-pressure claim-lifecycle conformance

test:
	uv run --with pytest pytest -q

matrix:
	$(PYTHON) scripts/generate_expected_matrix.py

doctor:
	$(PYTHON) scripts/check_env.py

native-blockpool-probe:
	$(VLLM_AUDIT_PYTHON) scripts/run_blockpool_contract_probe.py

native-summary:
	$(PYTHON) scripts/summarize_native_trace.py --markdown

no-admit-probe:
	$(VLLM_AUDIT_PYTHON) scripts/run_no_admit_probe.py

claim-metadata-probe:
	$(VLLM_AUDIT_PYTHON) scripts/run_claim_metadata_probe.py

hard-claim-probe:
	$(VLLM_AUDIT_PYTHON) scripts/run_hard_claim_probe.py

classify-hard-claim:
	$(PYTHON) scripts/classify_hard_claim_outcome.py

capacity-sweep:
	$(PYTHON) scripts/run_capacity_sweep.py

prior-art:
	$(PYTHON) scripts/generate_prior_art_boundary.py

live-scheduler:
	$(VLLM_AUDIT_PYTHON) scripts/run_live_scheduler_path.py

live-scheduler-pressure:
	$(VLLM_AUDIT_PYTHON) scripts/run_live_scheduler_pressure.py

claim-lifecycle:
	$(VLLM_AUDIT_PYTHON) scripts/run_claim_lifecycle_probes.py

conformance:
	$(PYTHON) scripts/run_conformance_suite.py
