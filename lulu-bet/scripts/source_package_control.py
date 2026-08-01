#!/usr/bin/env python3
"""Commit lulu-bet's single-L1 source package and delivered reference."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_DECISION_SCRIPTS = Path(__file__).resolve().parents[2] / "decision" / "scripts"
for _path in (_SCRIPTS, _DECISION_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from cycle_delivered_refs import delivered_refs_file_path, record_delivered_ref
from dec_session_state_schema import write_session_state
from dec_source_package_schema import build_source_package, save_source_package


def _restore_file(path: Path, previous: bytes | None) -> None:
    if previous is None:
        path.unlink(missing_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(previous)


def deliver(holder_root: Path, *, cycle_id: str, project_root: Path) -> Path:
    """Atomically commit Bet's L1 source package, delivered ref, and terminal state."""
    root = Path(holder_root).resolve()
    fact_path = root / "decision-fact.json"
    state_path = root / "session-state.md"
    if not fact_path.is_file():
        raise ValueError("lulu-bet delivery requires prepared decision-fact.json")
    if not state_path.is_file():
        raise ValueError("lulu-bet delivery requires session-state.md")

    source_path = root / "source-package.json"
    refs_path = delivered_refs_file_path(cycle_id, project_root)
    source_before = source_path.read_bytes() if source_path.is_file() else None
    refs_before = refs_path.read_bytes() if refs_path.is_file() else None
    state_before = state_path.read_bytes()
    package = build_source_package(
        holder_stage="lulu-bet",
        slices=[
            {
                "id": "L1",
                "title": "main",
                "source_path": "decision-fact.json",
                "source_id": "main",
            }
        ],
        commit_status="prepared",
    )
    try:
        save_source_package(root, package)
        record_delivered_ref(
            cycle_id,
            project_root,
            delivered_type="lulu-bet",
            path=str(source_path),
            artifact="source-package",
            revision=1,
            profile_id="lulu-bet",
            source_workflow_state=str(state_path),
        )
        write_session_state(state_path, "Completed")
        package["commit_status"] = "committed"
        save_source_package(root, package)
    except Exception:
        _restore_file(source_path, source_before)
        _restore_file(refs_path, refs_before)
        _restore_file(state_path, state_before)
        raise
    return source_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Commit lulu-bet source-package delivery.")
    parser.add_argument("--holder-root", required=True)
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    try:
        path = deliver(
            Path(args.holder_root),
            cycle_id=args.cycle_id.strip(),
            project_root=Path(args.project_root).resolve(),
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
