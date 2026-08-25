from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EngineResult:
    """Computation payload. Phase 3 wraps this as Evidence; fields must not be dropped."""

    operation: str
    source_columns: list[str]
    filters: dict[str, Any] = field(default_factory=dict)
    period: dict[str, Any] | None = None
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
