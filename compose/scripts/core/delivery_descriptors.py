"""Delivery index descriptors for cycle delivered-refs backfill."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from workflow_paths import (
    ACTIVE_COMPOSE_STAGE_IDS,
    COMPOSE_ROOT,
    WORKFLOW_ROOT,
    load_profile,
)

_DELIVERY_SOURCES_PATH = COMPOSE_ROOT / "config" / "delivery-sources.json"
_DEFAULT_TERMINAL = "Delivered"


@dataclass(frozen=True)
class DeliveryDescriptor:
    stage_name: str
    layout: str  # "revision" | "flat"
    cache_subdir: str
    state_file: str
    terminal_state: str
    doc_filename: str


def _descriptor_from_delivery_index(
    stage_name: str,
    cache_subdir: str,
    delivery_index: dict,
    *,
    default_doc_filename: str | None = None,
) -> DeliveryDescriptor | None:
    layout = str(delivery_index.get("layout", "")).strip()
    if layout not in ("revision", "flat"):
        return None
    state_file = str(delivery_index.get("state_file", "")).strip()
    doc_filename = str(delivery_index.get("doc_filename", "")).strip() or (
        default_doc_filename or ""
    )
    if not state_file or not doc_filename:
        return None
    terminal_state = str(delivery_index.get("terminal_state", _DEFAULT_TERMINAL)).strip()
    return DeliveryDescriptor(
        stage_name=stage_name,
        layout=layout,
        cache_subdir=cache_subdir,
        state_file=state_file,
        terminal_state=terminal_state,
        doc_filename=doc_filename,
    )


def _compose_descriptor(profile_id: str) -> DeliveryDescriptor | None:
    profile = load_profile(profile_id)
    if profile.get("status") == "placeholder_phase2":
        return None
    stage_name = str(profile.get("stage_name", profile_id)).strip()
    cache_subdir = str(profile.get("cache_subdir", "")).strip()
    if not cache_subdir:
        return None
    doc_filename = str((profile.get("document") or {}).get("filename", "")).strip()
    delivery_index = profile.get("delivery_index")
    if isinstance(delivery_index, dict) and delivery_index:
        return _descriptor_from_delivery_index(
            stage_name,
            cache_subdir,
            delivery_index,
            default_doc_filename=doc_filename,
        )
    if not doc_filename:
        return None
    return DeliveryDescriptor(
        stage_name=stage_name,
        layout="revision",
        cache_subdir=cache_subdir,
        state_file="workflow-state.md",
        terminal_state=_DEFAULT_TERMINAL,
        doc_filename=doc_filename,
    )


def _diagnostic_descriptor(constraints_path: Path) -> DeliveryDescriptor | None:
    try:
        data = json.loads(constraints_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    stage_name = str(data.get("stage", "")).strip()
    cache_subdir = str(data.get("cache_subdir", "")).strip()
    if not stage_name or not cache_subdir:
        return None
    delivery_index = data.get("delivery_index")
    if isinstance(delivery_index, dict) and delivery_index:
        return _descriptor_from_delivery_index(stage_name, cache_subdir, delivery_index)
    return DeliveryDescriptor(
        stage_name=stage_name,
        layout="flat",
        cache_subdir=cache_subdir,
        state_file="session-state.md",
        terminal_state=_DEFAULT_TERMINAL,
        doc_filename="decision-doc.md",
    )


def _load_delivery_sources() -> dict:
    if not _DELIVERY_SOURCES_PATH.is_file():
        raise FileNotFoundError(f"delivery-sources not found: {_DELIVERY_SOURCES_PATH}")
    return json.loads(_DELIVERY_SOURCES_PATH.read_text(encoding="utf-8"))


def _decision_constraints_paths() -> list[Path]:
    data = _load_delivery_sources()
    raw = data.get("decision_constraints")
    if not isinstance(raw, list):
        raise ValueError("delivery-sources.decision_constraints must be a list")
    paths: list[Path] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            continue
        paths.append(WORKFLOW_ROOT / item.strip())
    return paths


def _compose_stage_ids(sources: dict) -> tuple[str, ...]:
    raw = sources.get("compose_stage_ids")
    if isinstance(raw, list) and raw:
        return tuple(str(item).strip() for item in raw if str(item).strip())
    return ACTIVE_COMPOSE_STAGE_IDS


def iter_delivery_descriptors() -> Iterator[DeliveryDescriptor]:
    seen: set[str] = set()
    sources = _load_delivery_sources()
    for stage_id in _compose_stage_ids(sources):
        desc = _compose_descriptor(stage_id)
        if desc is not None and desc.stage_name not in seen:
            seen.add(desc.stage_name)
            yield desc
    for constraints_path in _decision_constraints_paths():
        desc = _diagnostic_descriptor(constraints_path)
        if desc is not None and desc.stage_name not in seen:
            seen.add(desc.stage_name)
            yield desc
