"""JSONL telemetry helpers for active/resident KV experiments."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ArbiterEvent:
    """One claim-level or block-level telemetry event."""

    event: str
    run_id: str
    request_id: str
    policy: str
    usable_blocks: int
    timestamp_ns: int = 0
    schema_version: int = 1
    claim_id: str | None = None
    prefix_id: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        fields = record.pop("fields")
        record.update(fields)
        return record

    def to_json(self) -> str:
        return json.dumps(self.to_record(), sort_keys=True, separators=(",", ":"))
