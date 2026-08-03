#!/usr/bin/env python3
"""Commit lulu-bet's decision-package and delivered reference."""

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
from dec_decision_package_schema import build_decision_package, save_decision_package
from dec_session_state_schema import write_session_state

DECISION_PACKAGE_FILENAME = "decision-package.json"
SOURCE_PACKAGE_FILENAME = "source-package.json"


def _restore_file(path: Path, previous: bytes | None) -> None:
    if previous is None:
        path.unlink(missing_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(previous)


def deliver(holder_root: Path, *, cycle_id: str, project_root: Path) -> Path:
    """Atomically commit Bet decision-package, delivered ref, and terminal state."""
    root = Path(holder_root).resolve()
    doc_path = root / "decision-doc.md"
    state_path = root / "session-state.md"
    if not doc_path.is_file():
        raise ValueError("lulu-bet delivery requires decision-doc.md")
    if not state_path.is_file():
        raise ValueError("lulu-bet delivery requires session-state.md")

    package_path = root / DECISION_PACKAGE_FILENAME
    residual_source = root / SOURCE_PACKAGE_FILENAME
    refs_path = delivered_refs_file_path(cycle_id, project_root)
    package_before = package_path.read_bytes() if package_path.is_file() else None
    refs_before = refs_path.read_bytes() if refs_path.is_file() else None
    state_before = state_path.read_bytes()
    package = build_decision_package(
        main={
            "decision_doc_path": "decision-doc.md",
        },
        slices=[],
        status="package_ready",
    )
    try:
        save_decision_package(root, package)
        record_delivered_ref(
            cycle_id,
            project_root,
            delivered_type="lulu-bet",
            path=str(package_path.resolve()),
            artifact="decision-package",
            revision=1,
            profile_id="lulu-bet",
            source_workflow_state=str(state_path),
        )
        write_session_state(state_path, "Completed")
        residual_source.unlink(missing_ok=True)
    except Exception:
        _restore_file(package_path, package_before)
        _restore_file(refs_path, refs_before)
        _restore_file(state_path, state_before)
        raise
    return package_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Commit lulu-bet decision-package delivery."
    )
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
