#!/usr/bin/env python3
"""Tests for chapter write-state (claim-current serial Write gate)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SECTION = Path(__file__).resolve().parents[1] / "section"
_SCRIPTS = Path(__file__).resolve().parents[1]
_NARRATIVE = Path(__file__).resolve().parents[2] / "narrative-arc-runner" / "scripts"
for _p in (_SECTION, _SCRIPTS, _NARRATIVE):
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

_REPO = Path(__file__).resolve().parents[4]
_PROFILE = "lulu-design"


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


def _seed_facts(rev: Path, *, with_anchors: bool = True) -> None:
    facts = [
        {
            "id": "F-1",
            "text": "fact one",
            "lens_tags": ["I"],
        },
        {
            "id": "F-2",
            "text": "fact two",
            "lens_tags": ["IF"],
        },
    ]
    if with_anchors:
        facts[0]["anchors"] = [{"kind": "path", "value": "src/a.py"}]
    (rev / "_facts.json").write_text(
        json.dumps(facts, ensure_ascii=False),
        encoding="utf-8",
    )


def _seed_arc(rev: Path) -> None:
    save_narrative_arc(rev / "_narrative-arc.json", _arc())
    _seed_facts(rev)


def _write_artifacts(rev: Path, cid: str, *, body: str = "body") -> None:
    (rev / f"_body-{cid}.txt").write_text(body + "\n", encoding="utf-8")


def _begin(rev: Path) -> int:
    return write_state_main(
        [
            "begin",
            "--revision-dir",
            str(rev),
            "--project-root",
            str(_REPO),
            "--profile",
            _PROFILE,
        ]
    )


def _complete(rev: Path, chapter: str | None = None) -> int:
    argv = ["complete", "--revision-dir", str(rev)]
    if chapter is not None:
        argv.extend(["--chapter", chapter])
    return write_state_main(argv)


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


def test_begin_returns_work_ticket(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    capsys.readouterr()
    assert _begin(rev) == 0
    ticket = json.loads(capsys.readouterr().out)
    assert ticket["ok"] is True
    assert ticket["chapter_id"] == "A01-I"
    assert ticket["leaf_id"] == "A01"
    assert ticket["leaf_title"] == "Leaf one"
    assert ticket["lens"] == "I"
    assert ticket["fact_ids"] == ["F-1"]
    assert ticket["facts"] == [
        {
            "id": "F-1",
            "text": "fact one",
            "anchors": [{"kind": "path", "value": "src/a.py"}],
        },
    ]
    assert ticket["status"] == "in_progress"
    cognition = ticket["writing_cognition"]
    assert set(cognition) == {"reading_axis", "presentation", "expression"}
    assert "proposition" in cognition["reading_axis"]
    intent = ticket["lens_intent"]
    assert set(intent) == {"intent", "intent_boundary"}
    assert intent["intent"]


def test_begin_writing_cognition_is_current_lens_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    capsys.readouterr()
    assert _begin(rev) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["lens"] == "I"
    axis_i = first["writing_cognition"]["reading_axis"]
    _write_artifacts(rev, "A01-I")
    assert _complete(rev) == 0
    capsys.readouterr()
    assert _begin(rev) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["lens"] == "IF"
    axis_if = second["writing_cognition"]["reading_axis"]
    assert axis_i != axis_if
    assert axis_i == first["writing_cognition"]["reading_axis"]


def test_begin_facts_emit_empty_anchors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    _seed_facts(rev, with_anchors=False)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    capsys.readouterr()
    assert _begin(rev) == 0
    ticket = json.loads(capsys.readouterr().out)
    assert ticket["facts"] == [
        {"id": "F-1", "text": "fact one", "anchors": []},
    ]


def test_begin_facts_order_follows_fact_ids(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    rev = tmp_path / "rev"
    rev.mkdir()
    arc = {
        "version": "1",
        "kind": "narrative-arc",
        "status": "write_ready",
        "leaves": [
            {
                "id": "A01",
                "title": "Leaf one",
                "fact_ids": ["F-2", "F-1"],
                "chapters": [
                    {"lens": "I", "fact_ids": ["F-2", "F-1"]},
                ],
            }
        ],
    }
    save_narrative_arc(rev / "_narrative-arc.json", arc)
    _seed_facts(rev, with_anchors=False)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    capsys.readouterr()
    assert _begin(rev) == 0
    ticket = json.loads(capsys.readouterr().out)
    assert ticket["fact_ids"] == ["F-2", "F-1"]
    assert [row["id"] for row in ticket["facts"]] == ["F-2", "F-1"]


def test_begin_missing_fact_id_fails_without_in_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    rev = tmp_path / "rev"
    rev.mkdir()
    # Contiguous F-1..F-2 in store; chapter asks for absent F-3.
    arc = {
        "version": "1",
        "kind": "narrative-arc",
        "status": "write_ready",
        "leaves": [
            {
                "id": "A01",
                "title": "Leaf one",
                "fact_ids": ["F-3"],
                "chapters": [{"lens": "I", "fact_ids": ["F-3"]}],
            }
        ],
    }
    save_narrative_arc(rev / "_narrative-arc.json", arc)
    _seed_facts(rev, with_anchors=False)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    capsys.readouterr()
    rc = _begin(rev)
    assert rc != 0
    err = json.loads(capsys.readouterr().out)
    assert err["error"] == "missing_fact_ids"
    assert err["missing_fact_ids"] == ["F-3"]
    assert "facts" not in err
    state = load_chapter_write_state(rev / CHAPTER_WRITE_STATE_BASENAME)
    # sync may already point current at the next cid while pending; claim must not start.
    assert state["by_id"]["A01-I"]["status"] == "pending"
    assert state["by_id"]["A01-I"].get("started_at") is None


def test_begin_rejects_chapter_arg(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    capsys.readouterr()
    rc = write_state_main(
        [
            "begin",
            "--revision-dir",
            str(rev),
            "--project-root",
            str(_REPO),
            "--profile",
            _PROFILE,
            "--chapter",
            "A01-I",
        ],
    )
    assert rc != 0
    err = json.loads(capsys.readouterr().out)
    assert err["error"] == "chapter_arg_forbidden"


def test_begin_rejects_already_running(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    assert _begin(rev) == 0
    capsys.readouterr()
    rc = _begin(rev)
    assert rc != 0
    err = json.loads(capsys.readouterr().out)
    assert err["error"] == "already_running"
    assert err["chapter_id"] == "A01-I"
    assert "facts" not in err


def test_begin_complete_happy_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    capsys.readouterr()
    assert _begin(rev) == 0
    ticket = json.loads(capsys.readouterr().out)
    assert ticket["chapter_id"] == "A01-I"
    _write_artifacts(rev, "A01-I")
    assert _complete(rev) == 0
    done = json.loads(capsys.readouterr().out)
    assert done["chapter_id"] == "A01-I"
    assert done["next"] == "A01-IF"
    assert "message" not in done
    assert write_state_main(["status", "--revision-dir", str(rev)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["next"] == "A01-IF"
    assert status["done_count"] == 1


def test_complete_biz_includes_body_path_and_mtime(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
):
    from datetime import datetime, timezone

    monkeypatch.setenv("LULU_PLATFORM", "cursor")
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "skill-config/lulu-dev-workflow/workflow-guard-config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        json.dumps(
            {
                "version": 2,
                "logs": {"enabled": True},
                "internalPathGuard": {
                    "enable": True,
                    "defaults": {
                        "readDirs": ["."],
                        "writeDirs": [".cache/{platform}/lulu-dev-workflow"],
                    },
                },
                "externalPathGuard": {
                    "enabled": False,
                    "writeAllowExternalPaths": [],
                    "readAllowExternalPaths": [],
                    "sessionAllow": False,
                },
            }
        ),
        encoding="utf-8",
    )
    plat = tmp_path / ".cursor/lulu-dev-workflow/config.json"
    plat.parent.mkdir(parents=True, exist_ok=True)
    plat.write_text(
        json.dumps(
            {
                "version": 1,
                "workflowConfig": "skill-config/lulu-dev-workflow/",
                "hookConfig": "skill-config/lulu-dev-workflow/workflow-guard-config.json",
            }
        ),
        encoding="utf-8",
    )

    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    assert _begin(rev) == 0
    _write_artifacts(rev, "A01-I")
    body = rev / "_body-A01-I.txt"
    expected_mtime = datetime.fromtimestamp(
        body.stat().st_mtime, tz=timezone.utc
    ).isoformat()
    capsys.readouterr()
    assert _complete(rev) == 0

    biz_log = tmp_path / ".cache/cursor/lulu-dev-workflow/.logs/biz.log"
    rows = [
        json.loads(line)
        for line in biz_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    complete_rows = [
        row
        for row in rows
        if row.get("component") == "chapter-write" and row.get("event") == "complete"
    ]
    assert len(complete_rows) == 1
    detail = complete_rows[0]["detail"]
    assert detail["chapter_id"] == "A01-I"
    assert detail["body_path"] == str(body)
    assert detail["body_mtime"] == expected_mtime


def test_complete_rejects_chapter_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    assert _begin(rev) == 0
    _write_artifacts(rev, "A01-I")
    capsys.readouterr()
    rc = _complete(rev, "A01-IF")
    assert rc != 0
    err = json.loads(capsys.readouterr().out)
    assert err["error"] == "chapter_mismatch"
    assert err["current"] == "A01-I"


def test_complete_accepts_matching_chapter_arg(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    assert _begin(rev) == 0
    _write_artifacts(rev, "A01-I")
    capsys.readouterr()
    assert _complete(rev, "A01-I") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["next"] == "A01-IF"


def test_complete_rejects_missing_body(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    assert _begin(rev) == 0
    capsys.readouterr()
    rc = _complete(rev)
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
    assert _begin(rev) == 0
    _write_artifacts(rev, "A01-I")
    assert _complete(rev) == 0
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
    capsys.readouterr()
    last_complete: dict | None = None
    for _ in range(2):
        assert _begin(rev) == 0
        ticket = json.loads(capsys.readouterr().out)
        cid = ticket["chapter_id"]
        _write_artifacts(rev, cid)
        assert _complete(rev) == 0
        last_complete = json.loads(capsys.readouterr().out)
    assert last_complete is not None
    assert last_complete["next"] is None
    assert last_complete["status"] == "complete"
    assert last_complete["message"] == "all chapters done"
    assert write_state_main(["status", "--revision-dir", str(rev)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "complete"
    assert status["next"] is None
    assert is_complete(load_chapter_write_state(rev / CHAPTER_WRITE_STATE_BASENAME))


def test_begin_when_all_done(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_arc(rev)
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    capsys.readouterr()
    for _ in range(2):
        assert _begin(rev) == 0
        cid = json.loads(capsys.readouterr().out)["chapter_id"]
        _write_artifacts(rev, cid)
        assert _complete(rev) == 0
        capsys.readouterr()
    assert _begin(rev) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["chapter_id"] is None
    assert out["status"] == "complete"


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
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    with pytest.raises(ValueError, match="complete"):
        assemble_arc_to_path(doc, revision_dir=rev, preamble="# Doc\n")
    for _ in range(2):
        assert _begin(rev) == 0
        assert _complete(rev) == 0
    result = assemble_arc_to_path(doc, revision_dir=rev, preamble="# Doc\n")
    assert result["ok"] is True


def test_init_validate_requires_write_state(tmp_path: Path):
    from writing_compose_validation import validate_writing_artifacts

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
    for cid in ("A01-I", "A01-IF"):
        _write_artifacts(rev, cid)
    doc = rev / "design-doc.md"
    bodies = []
    for cid in ("A01-I", "A01-IF"):
        bodies.append(f"<!-- chapter:{cid} -->\n{cid} body\n")
    doc.write_text("# Doc\n\n" + "\n".join(bodies), encoding="utf-8")
    err = validate_writing_artifacts(rev, doc, repo, "lulu-design")
    assert err is not None
    assert "4.W:" in err and "write-state" in err
    assert write_state_main(["sync", "--revision-dir", str(rev)]) == 0
    for _ in range(2):
        assert _begin(rev) == 0
        assert _complete(rev) == 0
    err2 = validate_writing_artifacts(rev, doc, repo, "lulu-design")
    assert err2 is None or ("write-state" not in err2 and "4.W:" not in err2)
