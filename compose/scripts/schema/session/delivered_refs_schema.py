#!/usr/bin/env python3
"""Cycle delivered-refs.json and workflow-state delivered_refs helpers."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[2]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

_WORKFLOW_SCRIPTS = Path(__file__).resolve().parents[4] / "scripts"
if str(_WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_WORKFLOW_SCRIPTS))

from cycle_delivered_refs import (  # noqa: E402
    delivered_refs_file_path,
    load_delivered_refs_file,
    record_delivered_ref,
    save_delivered_refs_file,
)


@dataclass(frozen=True)
class DeliveredRef:
    """Upstream delivered stage reference (doc path + optional decision-fact).

    ``artifact`` marks delivery shape (archive-1.0 P0.7): e.g.
    ``decision-package`` when ``path`` points at ``decision-package.json``.
    ``kind`` is required on norm-channel refs (archive-1.0 P3 D2): e.g.
    ``parent_decision`` / ``split_artifact`` / ``topic_arch`` / ``other``.
    """

    type: str
    path: str
    decision_fact_path: str = ""
    artifact: str = ""
    kind: str = ""

    def to_dict(self) -> dict[str, str]:
        out: dict[str, str] = {"type": self.type, "path": self.path}
        if self.decision_fact_path:
            out["decision_fact_path"] = self.decision_fact_path
        if self.artifact:
            out["artifact"] = self.artifact
        if self.kind:
            out["kind"] = self.kind
        return out


def entry_path_ok(data: dict[str, Any], delivered_type: str) -> bool:
    entry = (data.get("entries") or {}).get(delivered_type)
    if not isinstance(entry, dict):
        return False
    raw = str(entry.get("path", "")).strip()
    return bool(raw) and Path(raw).is_file()


def ref_from_file_entry(delivered_type: str, data: dict[str, Any]) -> DeliveredRef | None:
    entry = (data.get("entries") or {}).get(delivered_type)
    if not isinstance(entry, dict):
        return None
    raw_path = str(entry.get("path", "")).strip()
    if not raw_path:
        return None
    decision_fact = str(entry.get("decision_fact_path", "")).strip()
    artifact = str(entry.get("artifact", "")).strip()
    kind = str(entry.get("kind", "")).strip()
    return DeliveredRef(
        type=delivered_type,
        path=raw_path,
        decision_fact_path=decision_fact,
        artifact=artifact,
        kind=kind,
    )


def serialize_delivered_refs(refs: list[DeliveredRef]) -> str:
    return json.dumps([r.to_dict() for r in refs], ensure_ascii=False)


def parse_delivered_refs(state: dict[str, Any]) -> list[DeliveredRef]:
    raw = state.get("delivered_refs", "[]")
    if isinstance(raw, list):
        items = raw
    else:
        text = str(raw).strip() or "[]"
        items = json.loads(text)
    if not isinstance(items, list):
        raise ValueError("delivered_refs must be a JSON array")
    refs: list[DeliveredRef] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("delivered_refs items must be objects")
        dtype = str(item.get("type", "")).strip()
        path = str(item.get("path", "")).strip()
        if not dtype or not path:
            raise ValueError("delivered_refs item requires non-empty type and path")
        decision_fact_path = str(item.get("decision_fact_path", "")).strip()
        artifact = str(item.get("artifact", "")).strip()
        kind = str(item.get("kind", "")).strip()
        refs.append(
            DeliveredRef(
                type=dtype,
                path=path,
                decision_fact_path=decision_fact_path,
                artifact=artifact,
                kind=kind,
            )
        )
    return refs


def delivered_path(state: dict[str, Any], delivered_type: str) -> str:
    for ref in parse_delivered_refs(state):
        if ref.type == delivered_type:
            return ref.path
    return ""
