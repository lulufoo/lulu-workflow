#!/usr/bin/env python3
"""Write one human-delivery-gate.md."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def delivery_gate_file(doc_dir: Path) -> Path:
    return doc_dir / "human-delivery-gate.md"


def write_delivery_gate(path: Path, task_paths: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = ["---", "version: 1", "current_state: Delivered", f"updated_at: {now}", "---", ""]
    lines.extend(task_paths)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
