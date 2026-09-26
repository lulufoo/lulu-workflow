#!/usr/bin/env python3
"""Tests for lulu-arch StartAdapter."""

from __future__ import annotations

import json
from pathlib import Path

import bootstrap  # noqa: F401
from delivered_refs_schema import record_delivered_ref  # noqa: E402
from tech_arch_start_adapter import TechArchStartAdapter  # noqa: E402


def _seed_tech_diagnostic(tmp_path: Path, cycle_id: str) -> Path:
    diag_dir = tmp_path / ".cache/cursor/lulu-workflow" / cycle_id / "lulu-approach"
    diag_dir.mkdir(parents=True)
    (diag_dir / "decision-doc.md").write_text("# Decision\n", encoding="utf-8")
    package = diag_dir / "decision-package.json"
    package.write_text(
        json.dumps(
            {
                "version": 1,
                "status": "package_ready",
                "main": {

                    "decision_doc_path": "decision-doc.md",
                },
                "slices": [],
            }
        ),
        encoding="utf-8",
    )
    (diag_dir / "session-state.md").write_text(
        "---\ncurrent_state: Delivered\n---\n",
        encoding="utf-8",
    )
    record_delivered_ref(
        cycle_id,
        tmp_path,
        delivered_type="lulu-approach",
        path=str(package.resolve()),
        artifact="decision-package",
        revision=1,
        profile_id="lulu-approach",
        source_workflow_state=str((diag_dir / "session-state.md").resolve()),
    )
    return package


def test_infer_run_mode_is_tech(tmp_path: Path) -> None:
    adapter = TechArchStartAdapter()
    assert adapter.infer_run_mode("topic-demo", tmp_path) == "tech"


def test_validate_rejects_feature_cycle(tmp_path: Path) -> None:
    adapter = TechArchStartAdapter()
    errors = adapter.validate_for_start(
        "feat-a",
        tmp_path,
        run_mode="tech",
    )
    assert errors == ["lulu-arch is topic-only; feature cycles are not supported"]


def test_validate_rejects_non_tech_run_mode(tmp_path: Path) -> None:
    adapter = TechArchStartAdapter()
    errors = adapter.validate_for_start(
        "topic-demo",
        tmp_path,
        run_mode="product",
    )
    assert errors == ["invalid run_mode: 'product' (lulu-arch is tech-only)"]


def test_validate_requires_lulu_approach(tmp_path: Path) -> None:
    adapter = TechArchStartAdapter()
    errors = adapter.validate_for_start(
        "topic-demo",
        tmp_path,
        run_mode="tech",
    )
    assert errors == ["missing delivered-refs entry: lulu-approach"]


def test_resolve_delivered_refs_lulu_approach(tmp_path: Path) -> None:
    cycle_id = "topic-arch-start"
    decision = _seed_tech_diagnostic(tmp_path, cycle_id)
    adapter = TechArchStartAdapter()
    assert adapter.validate_for_start(cycle_id, tmp_path, run_mode="tech") == []
    refs = adapter.resolve_delivered_refs(cycle_id, tmp_path, run_mode="tech")
    assert len(refs) == 1
    assert refs[0].type == "lulu-approach"
    assert refs[0].path == str(decision.resolve())
