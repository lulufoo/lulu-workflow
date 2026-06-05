#!/usr/bin/env python3
"""Per-cycle current-stage tracking via cycle-state.json."""

import json
from datetime import datetime, timezone
from pathlib import Path


def read_cycle_state(cycle_id: str, cache_dir: Path) -> "str | None":
    """Return current_stage from cycle-state.json, or None if not found / unreadable."""
    p = cache_dir / cycle_id / "cycle-state.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("current_stage") or None
    except Exception:
        return None


def write_cycle_state(cycle_id: str, stage: str, cache_dir: Path) -> None:
    """Write current_stage to cycle-state.json."""
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
