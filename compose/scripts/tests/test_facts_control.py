#!/usr/bin/env python3
"""Tests for facts_schema / facts_control (fact-first display layer, M1)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent.parent / "section"
sys.path.insert(0, str(_SECTION))

from facts_schema import (  # noqa: E402
    filter_by_lens,
    lenses_present,
    load_facts,
    normalize_fact,
    save_facts,
    unlensed_fact_ids,
    validate_facts,
)

_CTL = _SECTION / "facts_control.py"


def test_validate_accepts_n_to_m_tags():
    facts = [
        {"id": "F-1", "text": "one", "lens_tags": ["CTX", "GO"]},
        {"id": "F-2", "text": "two", "lens_tags": ["I"]},
    ]
    assert validate_facts(facts, allowed_lenses=["CTX", "GO", "I"]) == []


def test_validate_accepts_empty_lens_tags_as_legal():
    """Empty lens_tags is schema-legal (Q1 quarantine candidate, not blocked here)."""
    facts = [{"id": "F-1", "text": "orphan", "lens_tags": []}]
    assert validate_facts(facts) == []


def test_validate_rejects_bad_id_and_extra_fields():
    facts = [
        {
            "id": "A-1",
            "text": "x",
            "lens_tags": ["CTX"],
            "display_home": "chap-1",
        },
    ]
    errors = validate_facts(facts, allowed_lenses=["CTX"])
    assert any("F-<n>" in e for e in errors)
    assert any("unexpected fields" in e for e in errors)


def test_validate_rejects_duplicate_and_unknown_tags():
    facts = [{"id": "F-1", "text": "x", "lens_tags": ["CTX", "CTX", "ZZ"]}]
    errors = validate_facts(facts, allowed_lenses=["CTX"])
    assert any("duplicate" in e for e in errors)
    assert any("not in section_order" in e for e in errors)


def test_validate_rejects_non_contiguous_ids():
    facts = [
        {"id": "F-1", "text": "a", "lens_tags": ["CTX"]},
        {"id": "F-3", "text": "b", "lens_tags": ["CTX"]},
    ]
    errors = validate_facts(facts, allowed_lenses=["CTX"])
    assert any("must be F-2" in e for e in errors)


def test_validate_rejects_duplicate_fact_id():
    facts = [
        {"id": "F-1", "text": "a", "lens_tags": ["CTX"]},
        {"id": "F-1", "text": "b", "lens_tags": ["CTX"]},
    ]
    errors = validate_facts(facts, allowed_lenses=["CTX"])
    # duplicate id also breaks contiguity; both signals should surface
    assert any("duplicate" in e for e in errors)


def test_validate_rejects_empty_and_non_array_root():
    assert validate_facts([]) == ["facts array must not be empty"]
    assert validate_facts({"id": "F-1"}) == ["facts root must be a JSON array"]


def test_filter_by_lens_stays_addressable(tmp_path: Path):
    """N:M: a fact tagged to two lenses is returned intact (not dissolved into prose)."""
    facts = [
        {"id": "F-1", "text": "alpha", "lens_tags": ["CTX", "AR"]},
        {"id": "F-2", "text": "beta", "lens_tags": ["I"]},
        {"id": "F-3", "text": "gamma", "lens_tags": ["AR"]},
    ]
    path = tmp_path / "_facts.json"
    save_facts(path, facts, allowed_lenses=["CTX", "AR", "I"])
    matched = filter_by_lens(
        json.loads(path.read_text(encoding="utf-8")),
        "AR",
    )
    assert matched == [
        {"id": "F-1", "text": "alpha"},
        {"id": "F-3", "text": "gamma"},
    ]


def test_lenses_present_and_unlensed_ids():
    facts = [
        {"id": "F-1", "text": "a", "lens_tags": ["CTX", "AR"]},
        {"id": "F-2", "text": "b", "lens_tags": ["AR"]},
        {"id": "F-3", "text": "c", "lens_tags": []},
    ]
    assert lenses_present(facts) == {"CTX": 1, "AR": 2}
    assert unlensed_fact_ids(facts) == ["F-3"]


def test_control_write_validate_filter(tmp_path: Path):
    facts = [
        {"id": "F-1", "text": "fact one", "lens_tags": ["GO", "AR"]},
        {"id": "F-2", "text": "fact two", "lens_tags": ["AR"]},
    ]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(facts), encoding="utf-8")
    rev = tmp_path / "revision1"
    rev.mkdir()

    write = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "write",
            "--revision-dir",
            str(rev),
            "--facts-file",
            str(facts_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0, write.stderr
    assert (rev / "_facts.json").is_file()
    payload = json.loads(write.stdout)
    assert payload["facts_total"] == 2
    assert payload["by_lens"] == {"GO": 1, "AR": 2}
    assert payload["unlensed_total"] == 0

    validate = subprocess.run(
        [sys.executable, str(_CTL), "validate", "--revision-dir", str(rev)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert validate.returncode == 0, validate.stderr

    filt = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "filter",
            "--revision-dir",
            str(rev),
            "--lens",
            "AR",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert filt.returncode == 0, filt.stderr
    matched = json.loads(filt.stdout)
    assert matched == [
        {"id": "F-1", "text": "fact one"},
        {"id": "F-2", "text": "fact two"},
    ]

    status = subprocess.run(
        [sys.executable, str(_CTL), "status", "--revision-dir", str(rev)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert status.returncode == 0, status.stderr
    status_payload = json.loads(status.stdout)
    assert status_payload["exists"] is True
    assert status_payload["facts_total"] == 2


def test_control_status_missing_file(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir()
    status = subprocess.run(
        [sys.executable, str(_CTL), "status", "--revision-dir", str(rev)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert status.returncode == 0, status.stderr
    payload = json.loads(status.stdout)
    assert payload["exists"] is False


def test_control_write_rejects_invalid_facts(tmp_path: Path):
    bad = [{"id": "F-1", "text": "", "lens_tags": ["CTX"]}]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(bad), encoding="utf-8")
    rev = tmp_path / "revision1"
    rev.mkdir()

    write = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "write",
            "--revision-dir",
            str(rev),
            "--facts-file",
            str(facts_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 1
    assert "text must be a non-empty string" in write.stderr


# --- K1 optional ``source`` field (compose-fact-first-k1-pd-design.md §3) ---


def test_validate_accepts_optional_source():
    facts = [
        {"id": "F-1", "text": "atom", "lens_tags": ["SK"]},
        {
            "id": "F-2",
            "text": "derived task",
            "lens_tags": ["T"],
            "source": ["F-1", "对应 SK P1"],
        },
    ]
    assert validate_facts(facts, allowed_lenses=["SK", "T"]) == []


def test_validate_still_rejects_unknown_extra_fields():
    facts = [
        {
            "id": "F-1",
            "text": "x",
            "lens_tags": ["CTX"],
            "display_home": "chap-1",
        },
    ]
    errors = validate_facts(facts, allowed_lenses=["CTX"])
    assert any("unexpected fields" in e for e in errors)


def test_validate_rejects_empty_or_bad_source():
    assert any(
        "non-empty array" in e
        for e in validate_facts(
            [{"id": "F-1", "text": "x", "lens_tags": ["T"], "source": []}],
            allowed_lenses=["T"],
        )
    )
    assert any(
        "must be an array" in e
        for e in validate_facts(
            [{"id": "F-1", "text": "x", "lens_tags": ["T"], "source": "F-1"}],
            allowed_lenses=["T"],
        )
    )
    assert any(
        "non-empty string" in e
        for e in validate_facts(
            [{"id": "F-1", "text": "x", "lens_tags": ["T"], "source": ["  "]}],
            allowed_lenses=["T"],
        )
    )


def test_validate_rejects_source_null():
    """Explicit null must fail (not treated as omit)."""
    errors = validate_facts(
        [{"id": "F-1", "text": "x", "lens_tags": ["T"], "source": None}],
        allowed_lenses=["T"],
    )
    assert any("source" in e and "null" in e.lower() for e in errors)


def test_normalize_and_save_round_trip_preserves_source(tmp_path: Path):
    """Grok K1 review: normalize/save must not silently strip ``source``."""
    facts = [
        {"id": "F-1", "text": "upstream", "lens_tags": ["SK"]},
        {
            "id": "F-2",
            "text": "derived",
            "lens_tags": ["T"],
            "source": ["F-1", "按 AR 契约"],
        },
    ]
    path = tmp_path / "_facts.json"
    save_facts(path, facts, allowed_lenses=["SK", "T"])
    loaded = load_facts(path)
    assert "source" not in loaded[0]
    assert loaded[1]["source"] == ["F-1", "按 AR 契约"]
    assert normalize_fact(facts[1])["source"] == ["F-1", "按 AR 契约"]


def test_control_write_round_trips_source(tmp_path: Path):
    facts = [
        {
            "id": "F-1",
            "text": "derived task",
            "lens_tags": ["T"],
            "source": ["F-3"],
        },
    ]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(facts), encoding="utf-8")
    rev = tmp_path / "revision1"
    rev.mkdir()

    write = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "write",
            "--revision-dir",
            str(rev),
            "--facts-file",
            str(facts_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0, write.stderr
    on_disk = json.loads((rev / "_facts.json").read_text(encoding="utf-8"))
    assert on_disk[0]["source"] == ["F-3"]


def test_validate_rejects_origin_null():
    errors = validate_facts(
        [{"id": "F-1", "text": "x", "lens_tags": ["T"], "origin": None}],
        allowed_lenses=["T"],
    )
    assert any("origin" in e and "null" in e.lower() for e in errors)


def test_validate_rejects_origin_bad_type():
    errors = validate_facts(
        [
            {
                "id": "F-1",
                "text": "x",
                "lens_tags": ["T"],
                "origin": {"type": "unknown", "ref": ["O-1"]},
            }
        ],
        allowed_lenses=["T"],
    )
    assert any("origin.type" in e for e in errors)


def test_validate_rejects_origin_empty_ref():
    errors = validate_facts(
        [
            {
                "id": "F-1",
                "text": "x",
                "lens_tags": ["T"],
                "origin": {"type": "discovered", "ref": []},
            }
        ],
        allowed_lenses=["T"],
    )
    assert any("origin.ref" in e for e in errors)


def test_normalize_and_save_round_trip_preserves_origin(tmp_path: Path):
    """K4 Phase 1a: normalize/save must not silently strip ``origin``."""
    facts = [
        {"id": "F-1", "text": "upstream", "lens_tags": ["SK"]},
        {
            "id": "F-2",
            "text": "discovered",
            "lens_tags": ["T"],
            "origin": {"type": "discovered", "ref": ["O-1"]},
        },
        {
            "id": "F-3",
            "text": "seeded",
            "lens_tags": ["FL"],
            "origin": {
                "type": "seed",
                "ref": ["scope:decision-doc.md", "主路径：进入计划任务页"],
            },
        },
    ]
    path = tmp_path / "_facts.json"
    save_facts(path, facts, allowed_lenses=["SK", "T", "FL"])
    loaded = load_facts(path)
    assert "origin" not in loaded[0]
    assert loaded[1]["origin"] == {"type": "discovered", "ref": ["O-1"]}
    assert loaded[2]["origin"]["type"] == "seed"
    assert loaded[2]["origin"]["ref"][0] == "scope:decision-doc.md"
    assert normalize_fact(facts[1])["origin"]["ref"] == ["O-1"]


def test_facts_without_origin_still_valid():
    """Backward compatible: existing facts without origin remain legal."""
    assert (
        validate_facts(
            [{"id": "F-1", "text": "x", "lens_tags": ["T"]}],
            allowed_lenses=["T"],
        )
        == []
    )


def test_validate_accepts_carried_and_quarantined_derivation():
    assert (
        validate_facts(
            [
                {
                    "id": "F-1",
                    "text": "kept",
                    "lens_tags": ["T"],
                    "derivation": {
                        "disposition": "carried",
                        "upstream_ref": ["F-12"],
                    },
                },
                {
                    "id": "F-2",
                    "text": "isolated",
                    "lens_tags": [],
                    "derivation": {
                        "disposition": "quarantined",
                        "upstream_ref": ["F-13"],
                    },
                },
            ],
            allowed_lenses=["T"],
        )
        == []
    )


def test_validate_rejects_derivation_null():
    errors = validate_facts(
        [{"id": "F-1", "text": "x", "lens_tags": ["T"], "derivation": None}],
        allowed_lenses=["T"],
    )
    assert any("derivation" in e and "null" in e.lower() for e in errors)


def test_validate_rejects_derivation_empty_upstream_ref():
    errors = validate_facts(
        [
            {
                "id": "F-1",
                "text": "x",
                "lens_tags": ["T"],
                "derivation": {"disposition": "carried", "upstream_ref": []},
            }
        ],
        allowed_lenses=["T"],
    )
    assert any("upstream_ref" in e for e in errors)


def test_validate_rejects_derivation_bad_disposition():
    errors = validate_facts(
        [
            {
                "id": "F-1",
                "text": "x",
                "lens_tags": ["T"],
                "derivation": {
                    "disposition": "rewritten",
                    "upstream_ref": ["F-1"],
                },
            }
        ],
        allowed_lenses=["T"],
    )
    assert any("disposition" in e for e in errors)


def test_validate_rejects_derivation_unknown_field():
    errors = validate_facts(
        [
            {
                "id": "F-1",
                "text": "x",
                "lens_tags": ["T"],
                "derivation": {
                    "disposition": "carried",
                    "upstream_ref": ["F-1"],
                    "extra": 1,
                },
            }
        ],
        allowed_lenses=["T"],
    )
    assert any("unexpected fields" in e for e in errors)


def test_validate_rejects_carried_with_empty_lens_tags():
    errors = validate_facts(
        [
            {
                "id": "F-1",
                "text": "x",
                "lens_tags": [],
                "derivation": {
                    "disposition": "carried",
                    "upstream_ref": ["F-9"],
                },
            }
        ],
        allowed_lenses=["T"],
    )
    assert any("carried" in e and "lens_tags" in e for e in errors)


def test_validate_rejects_quarantined_with_nonempty_lens_tags():
    errors = validate_facts(
        [
            {
                "id": "F-1",
                "text": "x",
                "lens_tags": ["T"],
                "derivation": {
                    "disposition": "quarantined",
                    "upstream_ref": ["F-9"],
                },
            }
        ],
        allowed_lenses=["T"],
    )
    assert any("quarantined" in e and "lens_tags" in e for e in errors)


def test_normalize_and_save_round_trip_preserves_derivation(tmp_path: Path):
    facts = [
        {"id": "F-1", "text": "plain", "lens_tags": ["T"]},
        {
            "id": "F-2",
            "text": "imported",
            "lens_tags": ["T"],
            "derivation": {"disposition": "carried", "upstream_ref": ["F-99"]},
        },
    ]
    path = tmp_path / "_facts.json"
    save_facts(path, facts, allowed_lenses=["T"])
    loaded = load_facts(path)
    assert "derivation" not in loaded[0]
    assert loaded[1]["derivation"] == {
        "disposition": "carried",
        "upstream_ref": ["F-99"],
    }
    assert normalize_fact(facts[1])["derivation"]["upstream_ref"] == ["F-99"]


def test_save_facts_rejects_incomplete_origin_with_value_error(tmp_path: Path):
    """Malformed origin must raise ValueError, not KeyError/TypeError."""
    path = tmp_path / "_facts.json"
    try:
        save_facts(
            path,
            [
                {
                    "id": "F-1",
                    "text": "x",
                    "lens_tags": ["T"],
                    "origin": {"type": "seed"},
                }
            ],
            allowed_lenses=["T"],
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "origin.ref" in str(exc)

    try:
        save_facts(
            path,
            [
                {
                    "id": "F-1",
                    "text": "x",
                    "lens_tags": ["T"],
                    "origin": {"type": "discovered", "ref": None},
                }
            ],
            allowed_lenses=["T"],
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "origin.ref" in str(exc)


def test_write_target_l_buckets_and_demotes(tmp_path: Path) -> None:
    """v1.1: --target-l writes into Lx and demotes production=done targets."""
    import argparse

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "schema" / "session"))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
    from dependency_tree_schema import build_tree, save_dependency_tree
    from discussion_pointer_schema import build_pointer_from_tree, load_discussion_pointer, save_discussion_pointer
    from facts_control import cmd_write

    rev = tmp_path / "revision1"
    rev.mkdir()
    tree = build_tree(
        nodes=[
            {"id": "L1", "title": "Base", "summary": "a"},
            {"id": "L2", "title": "Dep", "summary": "b"},
        ],
        edges=[{"from": "L2", "to": "L1"}],
        order=["L1", "L2"],
        status="locked",
    )
    save_dependency_tree(rev, tree)
    ptr = build_pointer_from_tree(tree)
    ptr["by_id"]["L1"]["inductive"] = "done"
    ptr["by_id"]["L1"]["production"] = "done"
    save_discussion_pointer(rev, ptr, tree=tree)
    (rev / "L1").mkdir(exist_ok=True)
    (rev / "L1" / "design-doc.md").write_text("# L1\n\n## Boundary\n\n", encoding="utf-8")

    facts_file = tmp_path / "facts.json"
    facts_file.write_text(
        json.dumps(
            [
                {
                    "id": "F-1",
                    "text": "bucketed",
                    "lens_tags": ["CTX"],
                    "home_l": "L1",
                    "home_rationale": "belongs to L1",
                }
            ]
        ),
        encoding="utf-8",
    )
    args = argparse.Namespace(
        revision_dir=rev,
        facts_file=facts_file,
        target_l="L1",
        package_confirm=False,
        profile="",
        project_root=tmp_path,
    )
    assert cmd_write(args) == 0
    assert (rev / "L1" / "_facts.json").is_file()
    loaded = load_discussion_pointer(rev)
    assert loaded["by_id"]["L1"]["production"] == "pending"
