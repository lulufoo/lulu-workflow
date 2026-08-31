#!/usr/bin/env python3
"""Shared holder preflight helpers (called by stage holders, not compose Start).

Writes runtime profile + normalized scope-package under the stage cache
``preflight/`` directory, outside any revision.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

_START = Path(__file__).resolve().parent
_SCRIPTS = _START.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from workflow_common import CACHE_DIR  # noqa: E402


def preflight_dir(project_root: Path, cycle_id: str, cache_subdir: str) -> Path:
    return (
        Path(project_root).resolve()
        / CACHE_DIR
        / cycle_id.strip()
        / cache_subdir.strip()
        / "preflight"
    )


def write_profile_bytes(source: Path, dest_dir: Path, overlay: dict[str, Any] | None = None) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / "compose-profile.json"
    if overlay is None:
        shutil.copyfile(source, out)
        return out.resolve()
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    data.update(overlay)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out.resolve()


def run_scope_preflight(
    *,
    adapter: Any,
    cycle_id: str,
    project_root: Path,
    output_dir: Path,
) -> Path:
    """Validate holder inputs and write ``scope-package.json`` into output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    run_mode = adapter.infer_run_mode(cycle_id, project_root)
    errors = adapter.validate_for_start(
        cycle_id, project_root, run_mode=run_mode
    )
    if errors:
        raise ValueError("; ".join(errors))
    delivered = adapter.resolve_delivered_refs(
        cycle_id, project_root, run_mode=run_mode
    )
    scope_refs = adapter.resolve_scope_refs(
        delivered_refs=delivered,
        run_mode=run_mode,
        output_dir=output_dir,
    )
    if not scope_refs:
        raise ValueError("preflight produced no scope-package")
    path = Path(scope_refs[0].path).resolve()
    if not path.is_file():
        raise ValueError(f"scope-package missing after preflight: {path}")
    return path


def emit_ok(*, profile_path: Path, scope_package: Path) -> dict[str, Any]:
    return {
        "ok": True,
        "command": "preflight",
        "profile_path": str(Path(profile_path).resolve()),
        "scope_package": str(Path(scope_package).resolve()),
    }


def print_preflight(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1
