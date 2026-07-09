#!/usr/bin/env python3
"""Schema and I/O for cycles.json and cycle-state.json."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from workflow_config_schema import detect_platform  # noqa: E402


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


def format_cycles_list(cache_dir: Path) -> str:
    cycles = load_cycles(cache_dir)
    if not cycles:
        return "Cycles:\n(no cycles)"
    lines = ["Cycles:"]
    for index, cycle_id in enumerate(sorted(cycles.keys()), start=1):
        entry = cycles[cycle_id]
        name = entry.get("name", cycle_id) if isinstance(entry, dict) else str(entry)
        kind = cycle_type_from_id(cycle_id)
        lines.append(f"[{kind}]   {index}. {name}")
    return "\n".join(lines)


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


def prune_cycles(cache_dir: Path, keep: int, project_root: Path) -> None:
    cycles_json = cache_dir / "cycles.json"
    if not cycles_json.exists():
        print("cycles.json not found — nothing to prune.")
        return

    features = load_cycles(cache_dir)
    sorted_ids = sorted(features.keys())

    if len(sorted_ids) <= keep:
        print(
            f"Nothing to prune — total features: {len(sorted_ids)}, "
            f"keep: {keep}."
        )
        return

    keep_ids = set(sorted_ids[-keep:])
    delete_ids = [fid for fid in sorted_ids if fid not in keep_ids]

    deleted, skipped = [], []
    for fid in delete_ids:
        feature_dir = cache_dir / fid
        if feature_dir.exists():
            shutil.rmtree(feature_dir)
            deleted.append(fid)
            print(f"Deleted: {feature_dir.relative_to(project_root)}")
        else:
            skipped.append(fid)
            print(f"Directory not found (removed from index only): {fid}")

    pruned = {fid: features[fid] for fid in sorted_ids if fid in keep_ids}
    save_cycles(cache_dir, pruned)

    print(
        f"\nDone — deleted {len(deleted)} dir(s), "
        f"cleaned {len(skipped)} stale index entr(ies), "
        f"kept {len(keep_ids)} most recent feature(s)."
    )
