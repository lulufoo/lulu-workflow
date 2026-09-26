"""Tests for routing-free issue taxonomy metadata."""

import json
from pathlib import Path


def test_taxonomy_keeps_semantics_and_issue_class_without_fix_routing():
    path = Path(__file__).resolve().parents[2] / "issue-taxonomy.json"
    taxonomy = json.loads(path.read_text(encoding="utf-8"))
    assert taxonomy["version"] == "2"
    assert set(taxonomy["labels"]) == {
        "SOT-DEFECT",
        "WO-MISS",
        "WO-ERROR",
        "UNRESOLVABLE",
        "DECISION-REQUIRED",
    }
    for label, metadata in taxonomy["labels"].items():
        assert set(metadata) == {"desc", "issue_class"}, label
        assert metadata["issue_class"] in {"Artifact-class", "Human-class"}
    assert taxonomy["labels"]["WO-MISS"]["issue_class"] == "Artifact-class"
    assert taxonomy["labels"]["SOT-DEFECT"]["issue_class"] == "Human-class"
