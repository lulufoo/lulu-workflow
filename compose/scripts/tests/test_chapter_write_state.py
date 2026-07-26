#!/usr/bin/env python3
"""Tests for chapter write-state (archive-5.0 chapter serial Write gate)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SECTION = Path(__file__).resolve().parents[1] / "section"
_SCRIPTS = Path(__file__).resolve().parents[1]
for _p in (_SECTION, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from chapter_write_state_control import main as write_state_main  # noqa: E402
from chapter_write_state_schema import (  # noqa: E402
    CHAPTER_WRITE_STATE_BASENAME,
    is_complete,
    load_chapter_write_state,
    validate_chapter_write_state,
)
from narrative_arc_schema import chapter_write_units, save_narrative_arc  # noqa: E402


def _arc() -> dict:
    return {
        "version": "1",
        "kind": "narrative-arc",
        "status": "write_ready",
        "leaves": [
            {
                "id": "A01",
                "title": "Leaf one",
                "fact_ids": ["F-1", "F-2"],
                "chapters": [
                    {"lens": "I", "fact_ids": ["F-1"]},
                    {"lens": "IF", "fact_ids": ["F-2"]},
                ],
            }
        ],
    }


def _seed_arc(rev: Path) -> None:
    save_narrative_arc(rev / "_narrative-arc.json", _arc())


def _write_artifacts(rev: Path, cid: str, *, title: str = "Title", body: str = "body") -> None:
    (rev / f"_derive-{cid}.json").write_text(
        json.dumps({"display_title": title, "lens": cid.split("-")[-1]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (rev / f"_body-{cid}.txt").write_text(body + "\n", encoding="utf-8")


def test_chapter_write_units_order():
    units = chapter_write_units(_arc())
    assert [u["chapter_id"] for u in units] == ["A01-I", "A01-IF"]
    assert units[0]["leaf_id"] == "A01"
    assert units[0]["lens"] == "I"


def test_validate_rejects_bad_kind():
    errors = validate_chapter_write_state(
        {"version": "1", "kind": "x", "order": [], "by_id": {}},
    )
    assert any("kind" in e for e in errors)


def test_sync_creates_pending_order(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    rc = write_state_main(["sync", "--revision-dir", str(rev)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["order"] == ["A01-I", "A01-IF"]
    state = load_chapter_write_state(rev / CHAPTER_WRITE_STATE_BASENAME)
    assert state["by_id"]["A01-I"]["status"] == "pending"
    assert state["status"] == "pending"


def test_begin_rejects_when_previous_not_done(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    capsys.readouterr()
    rc = write_state_main(["begin", "--revision-dir", str(rev), "--chapter", "A01-IF"])
    assert rc != 0
    err = json.loads(capsys.readouterr().out)
    assert err["ok"] is False
    assert err["error"] == "gate_failed"


def test_begin_complete_happy_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    capsys.readouterr()
    assert write_state_main(["begin", "--revision-dir", str(rev), "--chapter", "A01-I"]) == 0
    _write_artifacts(rev, "A01-I")
    assert write_state_main(["complete", "--revision-dir", str(rev), "--chapter", "A01-I"]) == 0
    capsys.readouterr()
    assert write_state_main(["status", "--revision-dir", str(rev)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["next"] == "A01-IF"
    assert status["done_count"] == 1


def test_complete_rejects_missing_body(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    assert write_state_main(["begin", "--revision-dir", str(rev), "--chapter", "A01-I"]) == 0
    (rev / "_derive-A01-I.json").write_text(
        json.dumps({"display_title": "T"}), encoding="utf-8",
    )
    capsys.readouterr()
    rc = write_state_main(["complete", "--revision-dir", str(rev), "--chapter", "A01-I"])
    assert rc != 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "artifact_gate_failed"
    state = load_chapter_write_state(rev / CHAPTER_WRITE_STATE_BASENAME)
    assert state["by_id"]["A01-I"]["status"] == "in_progress"


def test_sync_discards_ghost_cid(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    assert write_state_main(["begin", "--revision-dir", str(rev), "--chapter", "A01-I"]) == 0
    _write_artifacts(rev, "A01-I")
    assert write_state_main(["complete", "--revision-dir", str(rev), "--chapter", "A01-I"]) == 0
    arc = _arc()
    arc["leaves"][0]["chapters"] = [{"lens": "I", "fact_ids": ["F-1"]}]
    arc["leaves"][0]["fact_ids"] = ["F-1"]
    save_narrative_arc(rev / "_narrative-arc.json", arc)
    capsys.readouterr()
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    captured = capsys.readouterr()
    assert "A01-IF" in captured.err
    state = load_chapter_write_state(rev / CHAPTER_WRITE_STATE_BASENAME)
    assert state["order"] == ["A01-I"]
    assert "A01-IF" not in state["by_id"]
    assert is_complete(state)


def test_full_complete_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    for cid in ("A01-I", "A01-IF"):
        assert write_state_main(["begin", "--revision-dir", str(rev), "--chapter", cid]) == 0
        _write_artifacts(rev, cid)
        assert write_state_main(["complete", "--revision-dir", str(rev), "--chapter", cid]) == 0
    capsys.readouterr()
    assert write_state_main(["status", "--revision-dir", str(rev)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "complete"
    assert status["next"] is None
    assert is_complete(load_chapter_write_state(rev / CHAPTER_WRITE_STATE_BASENAME))


def test_no_reset_subcommand():
    with pytest.raises(SystemExit):
        write_state_main(["reset", "--revision-dir", "/tmp", "--chapter", "x"])


def test_assemble_requires_write_state_complete(tmp_path: Path):
    from compose_doc_control import assemble_arc_to_path

    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    for cid in ("A01-I", "A01-IF"):
        _write_artifacts(rev, cid)
    doc = tmp_path / "doc.md"
    with pytest.raises(ValueError, match="write-state"):
        assemble_arc_to_path(doc, revision_dir=rev, preamble="# Doc\n")
    # sync only → still not complete
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    with pytest.raises(ValueError, match="complete"):
        assemble_arc_to_path(doc, revision_dir=rev, preamble="# Doc\n")
    for cid in ("A01-I", "A01-IF"):
        assert write_state_main(["begin", "--revision-dir", str(rev), "--chapter", cid]) == 0
        assert write_state_main(["complete", "--revision-dir", str(rev), "--chapter", cid]) == 0
    result = assemble_arc_to_path(doc, revision_dir=rev, preamble="# Doc\n")
    assert result["ok"] is True


def test_init_validate_requires_write_state(tmp_path: Path):
    from init_compose_validation import validate_init_artifacts

    repo = Path(__file__).resolve().parents[4]
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    (rev / "_facts.json").write_text(
        json.dumps(
            [
                {"id": "F-1", "text": "fact one", "lens_tags": ["I"]},
                {"id": "F-2", "text": "fact two", "lens_tags": ["IF"]},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for cid, title in (("A01-I", "Leaf one · I"), ("A01-IF", "Leaf one · IF")):
        _write_artifacts(rev, cid, title=title)
    doc = rev / "design-doc.md"
    bodies = []
    for cid in ("A01-I", "A01-IF"):
        bodies.append(f"<!-- chapter:{cid} -->\n{cid} body\n")
    doc.write_text("# Doc\n\n" + "\n".join(bodies), encoding="utf-8")
    err = validate_init_artifacts(rev, doc, repo, "lulu-design")
    assert err is not None
    assert "4.W:" in err and "write-state" in err
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    for cid in ("A01-I", "A01-IF"):
        assert write_state_main(["begin", "--revision-dir", str(rev), "--chapter", cid]) == 0
        assert write_state_main(["complete", "--revision-dir", str(rev), "--chapter", cid]) == 0
    err2 = validate_init_artifacts(rev, doc, repo, "lulu-design")
    assert err2 is None or ("write-state" not in err2 and "4.W:" not in err2)
