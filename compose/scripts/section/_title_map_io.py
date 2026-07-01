#!/usr/bin/env python3
"""Shared load/save/get/set/validate for flat string JSON title maps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _atomic_write_json(path: Path, data: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(path)


def validate_flat_string_map(data: Any, *, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"{label} root must be an object"]
    for raw_key, value in data.items():
        key = str(raw_key).strip().upper()
        if not key:
            errors.append(f"{label}: empty map key")
            continue
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label}[{key!r}] must be a non-empty string")
    return errors


def load_map(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path.name}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name} root must be an object")
    normalized: dict[str, str] = {}
    for raw_key, value in raw.items():
        key = str(raw_key).strip().upper()
        if not key:
            raise ValueError(f"{path.name}: empty map key")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path.name}[{key!r}] must be a non-empty string")
        normalized[key] = value.strip()
    return normalized


def save_map(path: Path, data: dict[str, str]) -> None:
    normalized: dict[str, str] = {}
    for raw_key, value in data.items():
        key = str(raw_key).strip().upper()
        if not key:
            continue
        normalized[key] = str(value).strip()
    errors = validate_flat_string_map(normalized, label=path.name)
    if errors:
        raise ValueError("; ".join(errors))
    _atomic_write_json(path, normalized)


def get_title(data: dict[str, str], key: str) -> str:
    return data.get(key.strip().upper(), "").strip()


def set_title(data: dict[str, str], key: str, title: str) -> dict[str, str]:
    updated = dict(data)
    normalized_key = key.strip().upper()
    text = title.strip()
    if not normalized_key:
        raise ValueError("title map key is empty")
    if not text:
        raise ValueError("title is empty")
    updated[normalized_key] = text
    return updated
