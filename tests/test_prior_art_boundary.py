import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_prior_art_boundary", ROOT / "scripts" / "generate_prior_art_boundary.py"
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
ROWS = MODULE.ROWS


def test_prior_art_rows_have_evidence() -> None:
    assert {row["runtime"] for row in ROWS} == {
        "vLLM",
        "SGLang",
        "TensorRT-LLM",
        "Dynamo",
        "Continuum",
        "KVFlow",
        "Pie",
        "Marconi",
        "vLLM + Mooncake",
    }
    assert all(row["evidence"] for row in ROWS)


def test_tensorrt_llm_is_treated_as_strongest_prior_art() -> None:
    tensorrt = next(row for row in ROWS if row["runtime"] == "TensorRT-LLM")

    assert "Strongest prior art" in tensorrt["boundary_verdict"]
    assert "refutes any claim that runtimes lack primitives" in tensorrt[
        "boundary_verdict"
    ]
