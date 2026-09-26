#!/usr/bin/env python3
"""Static landing checks for compose-viewer Projection drift (archive-14.0 / sub_07)."""

from __future__ import annotations

from pathlib import Path

_HTML = (
    Path(__file__).resolve().parents[2]
    / "compose-viewer"
    / "assets"
    / "compose-viewer.html"
)


def _compute_projection_drift(arc_fact_ids: list[str], fact_ids: list[str]) -> dict:
    """Mirror of Viewer set-diff contract (fact ID strings)."""
    arc_set = set(arc_fact_ids)
    fact_set = set(fact_ids)
    missing = sorted(arc_set - fact_set)
    unplaced = sorted(fact_set - arc_set)
    return {
        "missingFacts": missing,
        "unplacedFacts": unplaced,
        "differenceCount": len(missing) + len(unplaced),
    }


def test_viewer_html_has_projection_drift_ui():
    html = _HTML.read_text(encoding="utf-8")
    assert "computeProjectionDrift" in html
    assert "renderProjectionDrift" in html
    assert "Projection drift" in html
    assert "Arc references missing facts" in html
    assert "Facts not placed in the arc" in html
    assert 'id="drift-trigger"' in html
    assert 'id="drift-popover"' in html
    assert "In sync" in html
    # Old one-way orphan parallel path must be gone
    assert "orphanIds" not in html
    assert "computeOrphans" not in html
    assert "orphan-box" not in html
    assert "STALE · unattached facts" not in html


def test_projection_drift_set_math_four_cases():
    sync = _compute_projection_drift(["F-1", "F-2"], ["F-1", "F-2"])
    assert sync["differenceCount"] == 0
    assert sync["missingFacts"] == []
    assert sync["unplacedFacts"] == []

    missing_only = _compute_projection_drift(["F-1", "F-2"], ["F-1"])
    assert missing_only["missingFacts"] == ["F-2"]
    assert missing_only["unplacedFacts"] == []
    assert missing_only["differenceCount"] == 1

    unplaced_only = _compute_projection_drift(["F-1"], ["F-1", "F-3"])
    assert unplaced_only["missingFacts"] == []
    assert unplaced_only["unplacedFacts"] == ["F-3"]
    assert unplaced_only["differenceCount"] == 1

    both = _compute_projection_drift(["F-1", "F-2"], ["F-1", "F-3"])
    assert both["missingFacts"] == ["F-2"]
    assert both["unplacedFacts"] == ["F-3"]
    assert both["differenceCount"] == 2
