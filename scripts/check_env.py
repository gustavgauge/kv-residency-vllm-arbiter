#!/usr/bin/env python3
"""Print a small environment report for this prototype workspace."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def command_version(command: str) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        result = subprocess.run(
            [command, "--version"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=5,
        )
    except Exception as exc:  # pragma: no cover - defensive environment probe
        return f"{path} ({exc})"
    first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else path
    return first_line


def exists(path: Path) -> bool:
    return path.exists()


def main() -> int:
    report = {
        "repo": str(ROOT),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "commands": {
            "git": command_version("git"),
            "uv": command_version("uv"),
            "python": command_version("python"),
        },
        "configured_paths": {
            "VLLM_AUDIT_PYTHON": os.environ.get("VLLM_AUDIT_PYTHON"),
            "VLLM_KV_RESIDENCY_MODEL": os.environ.get("VLLM_KV_RESIDENCY_MODEL"),
            "VLLM_KV_RESIDENCY_VLLM_SOURCE": os.environ.get(
                "VLLM_KV_RESIDENCY_VLLM_SOURCE"
            ),
        },
        "configured_path_exists": {
            name: exists(Path(value).expanduser())
            for name, value in {
                "VLLM_AUDIT_PYTHON": os.environ.get("VLLM_AUDIT_PYTHON"),
                "VLLM_KV_RESIDENCY_VLLM_SOURCE": os.environ.get(
                    "VLLM_KV_RESIDENCY_VLLM_SOURCE"
                ),
            }.items()
            if value
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
