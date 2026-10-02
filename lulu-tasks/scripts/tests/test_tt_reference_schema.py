#!/usr/bin/env python3
"""Reference document resolution from the cycle's delivered refs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from tt_reference_schema import resolve_reference  # noqa: E402
from cycle_delivered_refs import delivered_refs_file_path  # noqa: E402

_CYCLE = "20260601000000-aaaabbbb"


def _write_entry(project_root: Path, entry_type: str, package_path: Path) -> None:
    refs = delivered_refs_file_path(_CYCLE, project_root)
    data = json.loads(refs.read_text(encoding="utf-8")) if refs.is_file() else {"version": 1, "entries": {}}
    data["entries"][entry_type] = {"delivered_type": entry_type, "path": str(package_path.resolve())}
    refs.parent.mkdir(parents=True, exist_ok=True)
    refs.write_text(json.dumps(data), encoding="utf-8")


def _deliver_plan(project_root: Path, *, doc_path: str = "execution/tech-doc.md", write_doc: bool = True) -> Path:
    revision = project_root / "plan-revision"
    package = revision / "tech-package.json"
    revision.mkdir(parents=True, exist_ok=True)
    package.write_text(
        json.dumps({"version": 2, "profile_id": "lulu-plan", "doc_path": doc_path}),
        encoding="utf-8",
    )
    doc = revision / doc_path
    if write_doc:
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# Plan\n", encoding="utf-8")
    _write_entry(project_root, "lulu-plan", package)
    return doc


def _deliver_approach(project_root: Path, *, decision_doc_path: str = "decision-doc.md") -> Path:
    holder = project_root / "approach-holder"
    holder.mkdir(parents=True, exist_ok=True)
    package = holder / "decision-package.json"
    package.write_text(
        json.dumps({"version": 2, "status": "package_ready", "main": {"decision_doc_path": decision_doc_path}}),
        encoding="utf-8",
    )
    doc = holder / "decision-doc.md"
    doc.write_text("# Decision\n", encoding="utf-8")
    _write_entry(project_root, "lulu-approach", package)
    return doc


def test_plan_only_resolves_plan_doc(tmp_path: Path) -> None:
    doc = _deliver_plan(tmp_path)
    assert resolve_reference(_CYCLE, tmp_path) == {"source": "lulu-plan", "tech_ref": str(doc.resolve())}


def test_approach_only_resolves_decision_doc(tmp_path: Path) -> None:
    doc = _deliver_approach(tmp_path)
    assert resolve_reference(_CYCLE, tmp_path) == {"source": "lulu-approach", "tech_ref": str(doc.resolve())}


def test_plan_wins_when_both_delivered(tmp_path: Path) -> None:
    plan_doc = _deliver_plan(tmp_path)
    _deliver_approach(tmp_path)
    resolved = resolve_reference(_CYCLE, tmp_path)
    assert resolved["source"] == "lulu-plan"
    assert resolved["tech_ref"] == str(plan_doc.resolve())


def test_no_delivery_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="lulu-plan or lulu-approach"):
        resolve_reference(_CYCLE, tmp_path)


def test_invalid_plan_package_does_not_fall_back_to_approach(tmp_path: Path) -> None:
    _deliver_approach(tmp_path)
    package = tmp_path / "plan-revision" / "tech-package.json"
    package.parent.mkdir(parents=True)
    package.write_text(json.dumps({"version": 1}), encoding="utf-8")
    _write_entry(tmp_path, "lulu-plan", package)
    with pytest.raises(ValueError, match="invalid lulu-plan delivery"):
        resolve_reference(_CYCLE, tmp_path)


def test_missing_plan_doc_is_rejected(tmp_path: Path) -> None:
    _deliver_plan(tmp_path, write_doc=False)
    with pytest.raises(ValueError, match="lulu-plan reference doc not found"):
        resolve_reference(_CYCLE, tmp_path)


@pytest.mark.parametrize("bad_path", ["/etc/passwd", "../outside.md", ""])
def test_approach_doc_path_must_stay_under_package_dir(tmp_path: Path, bad_path: str) -> None:
    _deliver_approach(tmp_path, decision_doc_path=bad_path)
    with pytest.raises(ValueError, match="invalid lulu-approach delivery"):
        resolve_reference(_CYCLE, tmp_path)


def test_missing_approach_package_is_rejected(tmp_path: Path) -> None:
    doc = _deliver_approach(tmp_path)
    (doc.parent / "decision-package.json").unlink()
    with pytest.raises(ValueError, match="invalid lulu-approach delivery"):
        resolve_reference(_CYCLE, tmp_path)
