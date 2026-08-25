from __future__ import annotations

from analysis.evidence.models import Evidence
from analysis.evidence.scorer import score_operation
from analysis.result import EngineResult


class EvidenceLog:
    """Append-only. Existing rows cannot be updated or removed."""

    def __init__(self) -> None:
        self._items: list[Evidence] = []
        self._seq = 0

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def ids(self) -> set[str]:
        return {e.evidence_id for e in self._items}

    def get(self, evidence_id: str) -> Evidence | None:
        for item in self._items:
            if item.evidence_id == evidence_id:
                return item
        return None

    def snapshot(self) -> tuple[Evidence, ...]:
        return tuple(self._items)

    def append_result(self, result: EngineResult | dict, evidence_id: str | None = None) -> Evidence:
        payload = result.to_dict() if isinstance(result, EngineResult) else dict(result)
        self._seq += 1
        eid = evidence_id or f"ev-{payload.get('operation', 'op')}-{self._seq:03d}"
        if eid in self.ids():
            raise ValueError(f"append-only log already has {eid}")
        evidence = Evidence(
            evidence_id=eid,
            operation=str(payload["operation"]),
            source_columns=list(payload.get("source_columns") or []),
            filters=dict(payload.get("filters") or {}),
            period=payload.get("period"),
            value=payload.get("value"),
            strength=score_operation(str(payload["operation"]), payload.get("value")),
        )
        self._items.append(evidence)
        return evidence

    def replace(self, evidence_id: str, **_kwargs) -> None:
        raise TypeError("evidence log is append-only")

    def update(self, *_args, **_kwargs) -> None:
        raise TypeError("evidence log is append-only")
