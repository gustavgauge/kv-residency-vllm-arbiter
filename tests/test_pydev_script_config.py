import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_script(script_name: str):
    script_path = ROOT / "scripts" / script_name
    module_name = f"_test_{script_path.stem}_{id(script_path)}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_repetition_harness_requires_explicit_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VLLM_AUDIT_PYTHON", raising=False)
    monkeypatch.delenv("VLLM_KV_RESIDENCY_VLLM_SOURCE", raising=False)
    module = load_script("run_pydev_connector_failure_repetitions.py")

    with pytest.raises(SystemExit) as excinfo:
        module.validate_external_inputs(SimpleNamespace(vllm_source=None, runner=None))

    assert "VLLM_AUDIT_PYTHON" in str(excinfo.value)


def test_repetition_harness_accepts_current_python_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VLLM_KV_RESIDENCY_VLLM_SOURCE", raising=False)
    module = load_script("run_pydev_connector_failure_repetitions.py")
    args = SimpleNamespace(vllm_source=None, runner=sys.executable)

    module.validate_external_inputs(args)

    assert args.vllm_source is None
    assert module.resolve_runner(sys.executable) == sys.executable


def test_semantics_script_rejects_missing_explicit_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VLLM_KV_RESIDENCY_VLLM_SOURCE", raising=False)
    module = load_script("run_pydev_connector_failure_semantics.py")

    with pytest.raises(SystemExit) as excinfo:
        module.maybe_add_vllm_source(tmp_path / "missing-vllm")

    assert "VLLM_KV_RESIDENCY_VLLM_SOURCE" in str(excinfo.value)
