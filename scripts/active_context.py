#!/usr/bin/env python3
"""Conversation-indexed active-context read/write helpers."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TypedDict

KNOWN_STAGES = frozenset({
    "diagnostic",
    "product-diagnostic",
    "tech-diagnostic",
    "product-plan",
    "tech-plan",
    "tech-work-order",
    "tech-code",
})


class Entry(TypedDict):
    feature_id: str
    stage: str
    container_type: str


def _normalize_platform(platform: str) -> str:
    if platform in ("cursor", "copilot"):
        return platform
    return "cursor"


def context_path(project_root: Path, platform: str) -> Path:
    plat = _normalize_platform(platform)
    return project_root / f".cache/{plat}/lulu-dev-workflow/active-context.json"


def is_legacy_flat(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    if "feature_id" not in data or "stage" not in data:
        return False
    return not isinstance(data.get("feature_id"), dict) and not isinstance(
        data.get("stage"), dict
    )


def _valid_entry(raw: object) -> Entry | None:
    if not isinstance(raw, dict):
        return None
    feature_id = raw.get("feature_id")
    stage = raw.get("stage")
    if not isinstance(feature_id, str) or not feature_id.strip():
        return None
    if not isinstance(stage, str) or stage not in KNOWN_STAGES:
        return None
    container_type = raw.get("container_type", "feature")
    if container_type not in ("feature", "topic"):
        container_type = "feature"
    return {"feature_id": feature_id, "stage": stage, "container_type": container_type}


def read_all(project_root: Path, platform: str) -> dict[str, Entry]:
    path = context_path(project_root, platform)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if is_legacy_flat(data):
        return {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, Entry] = {}
    for conv_id, entry_raw in data.items():
        if not isinstance(conv_id, str) or not conv_id:
            continue
        entry = _valid_entry(entry_raw)
        if entry is not None:
            result[conv_id] = entry
    return result


def get_entry(
    project_root: Path,
    platform: str,
    conversation_id: str,
) -> Entry | None:
    if not conversation_id:
        return None
    return read_all(project_root, platform).get(conversation_id)


def write_entry(
    project_root: Path,
    platform: str,
    conversation_id: str,
    feature_id: str,
    stage: str,
    container_type: str = "feature",
) -> None:
    if not conversation_id:
        print(
            "警告：未提供 conversation_id，active-context 未更新，hook 不会保护本对话写入。",
            file=sys.stderr,
        )
        return
    if stage not in KNOWN_STAGES:
        raise ValueError(f"Unknown stage: {stage!r}")
    data = read_all(project_root, platform)
    data[conversation_id] = {
        "feature_id": feature_id,
        "stage": stage,
        "container_type": container_type,
    }
    path = context_path(project_root, platform)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=True)
        handle.write("\n")


def resolve_conversation_id(cli_value: str | None) -> str | None:
    if cli_value is not None:
        stripped = cli_value.strip()
        if stripped:
            return stripped
    env_val = os.environ.get("LULU_CONVERSATION_ID", "").strip()
    return env_val or None
