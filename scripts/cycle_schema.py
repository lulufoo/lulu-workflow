#!/usr/bin/env python3
"""Schema and I/O for cycles.json and cycle-state.json."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from transition_table import topic_doc_stage_for  # noqa: E402
from workflow_config_schema import detect_platform  # noqa: E402

_EXCERPT_MAX_CHARS = 400


def resolve_cache_dir(project_root: Path, platform: Optional[str] = None) -> Path:
    plat = detect_platform(platform)
    return project_root / ".cache" / plat / "lulu-dev-workflow"


def generate_cycle_id(cycle_type: str) -> str:
    """Return a cycle ID: {cycle_type}-YYYYMMDDHHMMSS-{8hexchars}."""
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    hex_part = uuid4().hex[:8]
    return f"{cycle_type}-{ts}-{hex_part}"


def load_cycles(cache_dir: Path) -> dict:
    cj = cache_dir / "cycles.json"
    if not cj.exists():
        return {}
    return json.loads(cj.read_text(encoding="utf-8"))


def save_cycles(cache_dir: Path, data: dict) -> None:
    cj = cache_dir / "cycles.json"
    cj.parent.mkdir(parents=True, exist_ok=True)
    cj.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_cycle(
    cache_dir: Path,
    cycle_id: str,
    name: str,
    topic_id: Optional[str] = None,
) -> None:
    data = load_cycles(cache_dir)
    entry = {"name": name}
    if topic_id is not None:
        entry["topic_id"] = topic_id
    data[cycle_id] = entry
    save_cycles(cache_dir, data)


def cycle_exists(cache_dir: Path, cycle_id: str) -> bool:
    return cycle_id in load_cycles(cache_dir)


def cycle_type_from_id(cycle_id: str) -> str:
    return cycle_id.split("-", 1)[0]


def load_cycle_entry(cache_dir: Path, cycle_id: str) -> Optional[dict]:
    return load_cycles(cache_dir).get(cycle_id)


def validate_cycle(cache_dir: Path, cycle_id: str) -> tuple[bool, str]:
    if not cycle_exists(cache_dir, cycle_id):
        return False, f"cycle-id {cycle_id!r} not found in cycles.json"
    if not (cache_dir / cycle_id).is_dir():
        return False, f"cycle directory not found: {cache_dir / cycle_id}"
    return True, ""


_MENU_PER_TYPE_LIMIT = 5
_MENU_TYPE_ORDER = ("topic", "feature")
_MENU_TOKEN_PREFIX = {"topic": "T", "feature": "F"}
_MENU_PREFIX_TO_TYPE = {v: k for k, v in _MENU_TOKEN_PREFIX.items()}
_MENU_CREATE_LINES = (
    "N. New topic — type a description to create",
    "M. New feature — type a description to create",
)
_MENU_TOKEN_RE = re.compile(r"^([TtFf])(\d+)$")


def _menu_ids_by_type(cache_dir: Path) -> dict[str, list[str]]:
    """Ordered cycle ids per menu type (newest first, truncated)."""
    cycles = load_cycles(cache_dir)
    by_kind: dict[str, list[str]] = {}
    for cycle_id in cycles:
        kind = cycle_type_from_id(cycle_id)
        if kind not in _MENU_TOKEN_PREFIX:
            continue
        by_kind.setdefault(kind, []).append(cycle_id)
    return {
        kind: sorted(by_kind.get(kind, []), reverse=True)[:_MENU_PER_TYPE_LIMIT]
        for kind in _MENU_TYPE_ORDER
    }


def format_cycles_menu(cache_dir: Path) -> str:
    """Format Feature Resolution menu (typed tokens + create actions)."""
    cycles = load_cycles(cache_dir)
    lines = ["Cycles:"]
    ids_by_type = _menu_ids_by_type(cache_dir)
    if not any(ids_by_type.values()):
        lines.append("(no cycles)")
    else:
        for kind in _MENU_TYPE_ORDER:
            prefix = _MENU_TOKEN_PREFIX[kind]
            for index, cycle_id in enumerate(ids_by_type[kind], start=1):
                entry = cycles[cycle_id]
                name = (
                    entry.get("name", cycle_id)
                    if isinstance(entry, dict)
                    else str(entry)
                )
                lines.append(f"[{kind}]   {prefix}{index}. {name}")

    lines.extend(_MENU_CREATE_LINES)
    return "  \n".join(lines)


def resolve_menu_token(cache_dir: Path, token: str) -> Optional[str]:
    """Resolve a menu token (``T#`` / ``F#``) to ``cycle_id``, or None."""
    match = _MENU_TOKEN_RE.match(token.strip())
    if match is None:
        return None
    kind = _MENU_PREFIX_TO_TYPE[match.group(1).upper()]
    index = int(match.group(2))
    ids = _menu_ids_by_type(cache_dir).get(kind, [])
    if index < 1 or index > len(ids):
        return None
    return ids[index - 1]


def build_cycle_info(cache_dir: Path, cycle_id: str) -> Optional[dict]:
    entry = load_cycle_entry(cache_dir, cycle_id)
    if entry is None:
        return None
    if not isinstance(entry, dict):
        entry = {"name": str(entry)}
    info = {
        "cycle_id": cycle_id,
        "cycle_type": cycle_type_from_id(cycle_id),
        "name": entry.get("name"),
        "current_stage": read_stage(cycle_id, cache_dir),
    }
    if "topic_id" in entry:
        info["topic_id"] = entry["topic_id"]
    return info


def ensure_container_dir(cache_dir: Path, cycle_id: str) -> Path:
    target = cache_dir / cycle_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def read_stage(cycle_id: str, cache_dir: Path) -> Optional[str]:
    p = cache_dir / cycle_id / "cycle-state.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("current_stage") or None
    except Exception:
        return None


def write_stage(cycle_id: str, stage: str, cache_dir: Path) -> None:
    p = cache_dir / cycle_id / "cycle-state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "current_stage": stage,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _excerpt_from_doc(path: Path, max_chars: int = _EXCERPT_MAX_CHARS) -> str:
    text = path.read_text(encoding="utf-8")
    # Collapse leading whitespace; keep content readable for relevance matching.
    collapsed = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[:max_chars].rstrip()


def _topic_delivered_doc_path(cache_dir: Path, topic_id: str, ref_stage: str) -> Optional[Path]:
    refs_path = cache_dir / topic_id / "delivered-refs.json"
    if not refs_path.is_file():
        return None
    try:
        data = json.loads(refs_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    entry = (data.get("entries") or {}).get(ref_stage)
    if not isinstance(entry, dict):
        return None
    raw_path = str(entry.get("path", "")).strip()
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_file():
        return None
    return path


def build_topic_digest(cache_dir: Path, stage: str) -> dict[str, Any]:
    """Build topic association candidates for a feature-line stage.

    Looks up ``topic_doc_stage[stage]``; when unmapped returns
    ``applicable: false``. Otherwise lists topics that have delivered the
    mapped ref-stage document, each with a short excerpt.
    """
    ref_stage = topic_doc_stage_for(stage)
    if ref_stage is None:
        return {
            "applicable": False,
            "stage": stage,
            "ref_stage": None,
            "topics": [],
        }

    topics: list[dict[str, Any]] = []
    for cycle_id, entry in sorted(load_cycles(cache_dir).items()):
        if cycle_type_from_id(cycle_id) != "topic":
            continue
        name = entry.get("name", cycle_id) if isinstance(entry, dict) else str(entry)
        doc_path = _topic_delivered_doc_path(cache_dir, cycle_id, ref_stage)
        if doc_path is None:
            continue
        topics.append(
            {
                "topic_id": cycle_id,
                "name": name,
                "ref_stage": ref_stage,
                "doc_path": str(doc_path.resolve()),
                "excerpt": _excerpt_from_doc(doc_path),
            }
        )

    return {
        "applicable": True,
        "stage": stage,
        "ref_stage": ref_stage,
        "topics": topics,
    }
