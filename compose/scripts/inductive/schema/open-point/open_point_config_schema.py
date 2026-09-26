#!/usr/bin/env python3
"""Schema and I/O for compose ``config/compose-config.json``.

``detect_skip_clean`` defaults false when the file or key is absent.
``LULU_COMPOSE_CONFIG`` overrides the path (tests).

Design rationale:
docs/archive/lulu-dev-workflow/compose/archive-68.0/compose-g3-detect-clean-skip-design.md
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_KERNEL = Path(__file__).resolve().parents[3] / "_kernel"
if str(_KERNEL) not in sys.path:
    sys.path.insert(0, str(_KERNEL))

from workflow_paths import COMPOSE_ROOT  # noqa: E402

COMPOSE_CONFIG_BASENAME = "compose-config.json"
_CONFIG_KEYS = frozenset({"detect_skip_clean"})
_ENV_PATH = "LULU_COMPOSE_CONFIG"


def open_point_config_path() -> Path:
    override = os.environ.get(_ENV_PATH, "").strip()
    if override:
        return Path(override)
    return COMPOSE_ROOT / "config" / COMPOSE_CONFIG_BASENAME


def validate_open_point_config(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["open-point config root must be an object"]
    errors: list[str] = []
    extra = set(data) - _CONFIG_KEYS
    if extra:
        errors.append(f"open-point config unexpected fields {sorted(extra)}")
    if "detect_skip_clean" in data and not isinstance(data["detect_skip_clean"], bool):
        errors.append("detect_skip_clean must be a boolean")
    return errors


def load_open_point_config() -> dict[str, Any]:
    path = open_point_config_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid open-point config JSON: {exc}") from exc
    errors = validate_open_point_config(data)
    if errors:
        raise ValueError("; ".join(errors))
    out: dict[str, Any] = {}
    if "detect_skip_clean" in data:
        out["detect_skip_clean"] = bool(data["detect_skip_clean"])
    return out


def detect_skip_clean_enabled() -> bool:
    return load_open_point_config().get("detect_skip_clean") is True
