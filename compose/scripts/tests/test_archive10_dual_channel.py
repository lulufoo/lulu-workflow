#!/usr/bin/env python3
"""archive-10.0 dual-channel behavior (paths updated for archive-11.0 extract)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_COMPOSE = Path(__file__).resolve().parents[2]
_FACT_CTL = _COMPOSE / "fact-production-runner" / "scripts" / "fact_production_control.py"
_ARC_TOOL = _COMPOSE / "narrative-arc-runner" / "scripts" / "narrative_arc_collab_control.py"
_VIEWER = _COMPOSE / "compose-viewer" / "scripts" / "compose_viewer_control.py"
_TOPIC_CTL = _COMPOSE / "scripts" / "section" / "topic_current_control.py"
_NARRATIVE_SCRIPTS = _COMPOSE / "narrative-arc-runner" / "scripts"

sys.path.insert(0, str(_NARRATIVE_SCRIPTS))
from narrative_arc_collab_schema import (  # noqa: E402
    FORMAL_BASENAME,
    build_collab_from_facts,
    orphan_fact_ids,
    validate_narrative_arc_collab,
)


def _run(script: Path, *args: str) -> tuple[int, dict, str]:
    res = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(res.stdout) if res.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"raw": res.stdout}
    return res.returncode, payload, res.stderr


def test_topic_current_set_and_confirm(tmp_path: Path):
    code, _, err = _run(
        _TOPIC_CTL,
        "set",
        "--revision-dir",
        str(tmp_path),
        "--title",
        "Traction",
        "--scope",
        "D1+D2 boundary",
    )
    assert code != 0
    assert "human-adopted" in err.lower()

    code, payload, err = _run(
        _TOPIC_CTL,
        "set",
        "--revision-dir",
        str(tmp_path),
        "--title",
        "Traction",
        "--scope",
        "D1+D2 boundary",
        "--human-adopted",
    )
    assert code == 0, err
    assert payload["topic"]["clarified"] is True
    assert payload["topic"]["human_adopted"] is True

    code, _, err = _run(
        _TOPIC_CTL,
        "set-conclusion",
        "--revision-dir",
        str(tmp_path),
        "--text",
        "Keep production off display arc",
    )
    assert code == 0, err
    code, payload, err = _run(
        _TOPIC_CTL,
        "confirm-conclusion",
        "--revision-dir",
        str(tmp_path),
    )
    assert code == 0, err
    assert payload["topic"]["conclusion_confirmed"] is True


def test_fact_production_requires_confirm_and_signals_stale(tmp_path: Path):
    facts = json.dumps([{"text": "A settled fact", "lens_tags": ["I"]}])
    code, _, err = _run(
        _FACT_CTL,
        "commit",
        "--revision-dir",
        str(tmp_path),
        "--facts-json",
        facts,
    )
    assert code != 0
    assert "confirm" in err.lower()

    code, payload, err = _run(
        _FACT_CTL,
        "commit",
        "--revision-dir",
        str(tmp_path),
        "--confirm",
        "--facts-json",
        facts,
    )
    assert code == 0, err
    assert payload.get("stale_signal") is True
    assert payload.get("suggest_check") is True
    assert (tmp_path / "_facts.json").is_file()

    code, payload, err = _run(_FACT_CTL, "cancel", "--revision-dir", str(tmp_path))
    assert code == 0, err
    assert payload.get("written") is False


def test_fact_production_delete_keeps_ids_stable_and_signals_stale(tmp_path: Path):
    (tmp_path / "_facts.json").write_text(
        json.dumps(
            [
                {"id": "F-1", "text": "one", "lens_tags": ["I"]},
                {"id": "F-2", "text": "remove", "lens_tags": ["I"]},
                {"id": "F-3", "text": "three", "lens_tags": ["ST"]},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    code, _, err = _run(
        _FACT_CTL,
        "delete",
        "--revision-dir",
        str(tmp_path),
        "--id",
        "F-2",
    )
    assert code != 0
    assert "confirm" in err.lower()

    code, payload, err = _run(
        _FACT_CTL,
        "delete",
        "--revision-dir",
        str(tmp_path),
        "--id",
        "F-2",
        "--confirm",
    )
    assert code == 0, err
    assert payload["deleted"] == "F-2"
    assert payload["stale_signal"] is True
    assert payload["suggest_check"] is True
    facts = json.loads((tmp_path / "_facts.json").read_text(encoding="utf-8"))
    assert [fact["id"] for fact in facts] == ["F-1", "F-3"]
    assert facts[1]["text"] == "three"

    code, payload, err = _run(
        _FACT_CTL,
        "commit",
        "--revision-dir",
        str(tmp_path),
        "--confirm",
        "--facts-json",
        json.dumps([{"text": "four", "lens_tags": ["I"]}]),
    )
    assert code == 0, err
    assert payload["fact_ids"] == ["F-4"]


def test_fact_production_delete_only_fact_removes_store(tmp_path: Path):
    (tmp_path / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "one", "lens_tags": ["I"]}]),
        encoding="utf-8",
    )
    code, payload, err = _run(
        _FACT_CTL,
        "delete",
        "--revision-dir",
        str(tmp_path),
        "--id",
        "F-1",
        "--confirm",
    )
    assert code == 0, err
    assert payload["facts_total"] == 0
    assert not (tmp_path / "_facts.json").exists()


def test_narrative_arc_collab_regenerate_path_and_backup(tmp_path: Path):
    (tmp_path / "_facts.json").write_text(
        json.dumps(
            [
                {"id": "F-1", "text": "one", "lens_tags": ["I"]},
                {"id": "F-2", "text": "two", "lens_tags": ["ST"]},
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "_narrative-arc.collab.json"
    out.write_text(
        '{"version":"1","kind":"narrative-arc-collab","status":"display",'
        '"tree":{"id":"root","title":"old","children":[]},"leaves":[]}\n',
        encoding="utf-8",
    )

    code, _, err = _run(
        _ARC_TOOL,
        "regenerate",
        "--revision-dir",
        str(tmp_path),
        "--output-path",
        str(out),
    )
    assert code != 0
    assert "confirm" in err.lower()

    code, payload, err = _run(
        _ARC_TOOL,
        "regenerate",
        "--revision-dir",
        str(tmp_path),
        "--output-path",
        str(out),
        "--confirm",
    )
    assert code == 0, err
    assert payload.get("backup")
    assert Path(payload["backup"]).is_file()
    assert len(payload.get("fact_node_summary") or []) == 2

    code, _, err = _run(
        _ARC_TOOL,
        "regenerate",
        "--revision-dir",
        str(tmp_path),
        "--output-path",
        FORMAL_BASENAME,
        "--confirm",
    )
    assert code != 0
    assert "Formal" in err or "formal" in err.lower()


def test_collab_orphan_detection():
    facts = [
        {"id": "F-1", "text": "a", "lens_tags": ["I"]},
        {"id": "F-2", "text": "b", "lens_tags": ["I"]},
    ]
    arc = build_collab_from_facts(facts)
    assert validate_narrative_arc_collab(arc) == []
    arc["leaves"][0]["fact_ids"] = ["F-1"]
    assert orphan_fact_ids(arc, facts) == ["F-2"]


def test_viewer_rejects_formal_arc_file(tmp_path: Path):
    code, _, err = _run(
        _VIEWER,
        "mount",
        "--revision-dir",
        str(tmp_path),
        "--arc-file",
        "_narrative-arc.json",
    )
    assert code != 0
    assert "Formal" in err or "hard-banned" in err.lower()


def test_viewer_html_bans_bare_formal_arc_source():
    """HTML must reject bare Formal basename, not only ./_narrative-arc.json."""
    html = (
        _COMPOSE / "compose-viewer" / "assets" / "compose-viewer.html"
    ).read_text(encoding="utf-8")
    assert "function isFormalArcSource" in html
    assert "base === FORMAL_BASENAME" in html
    assert 'arc === FORMAL_BANNED' not in html
    assert "./_compose-viewer.json" in html


def test_fact_production_settle_rolls_back_facts_when_opens_save_fails(
    tmp_path: Path, monkeypatch
):
    """Atomic settle: opens save failure must roll back newly written facts."""
    sys.path.insert(0, str(_COMPOSE / "scripts"))
    sys.path.insert(0, str(_COMPOSE / "scripts" / "inductive"))
    sys.path.insert(0, str(_COMPOSE / "fact-production-runner" / "scripts"))
    import fact_production_control as fpc  # noqa: E402

    # Seed open via in-process G3 helpers (facts empty)
    g3 = _COMPOSE / "scripts" / "inductive" / "inductive_g3_section_control.py"
    for args in (
        ["init-pointer", "--sections", "ST,I", "--mandatory", ""],
        ["activate-section", "--section", "ST"],
        [
            "add-open",
            "--kw",
            "2",
            "--trigger",
            "ai",
            "--means",
            "ai_probe",
            "--problem",
            "q",
            "--blocking",
            "true",
        ],
    ):
        res = subprocess.run(
            [sys.executable, str(g3), "--out-dir", str(tmp_path), *args],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, res.stderr or res.stdout

    ff = tmp_path / "settle.json"
    ff.write_text(
        json.dumps([{"text": "orphan candidate", "lens_tags": ["ST"]}], ensure_ascii=False),
        encoding="utf-8",
    )

    def _boom(path, opens):  # noqa: ANN001
        raise OSError("permission denied")

    monkeypatch.setattr(fpc, "save_opens", _boom)

    code = fpc.main(
        [
            "settle-open",
            "--revision-dir",
            str(tmp_path),
            "--open-id",
            "O-1",
            "--facts-file",
            str(ff),
            "--confirm",
        ]
    )
    assert code != 0
    assert not (tmp_path / "_facts.json").exists()
    opens = json.loads((tmp_path / "inductive-opens.json").read_text(encoding="utf-8"))
    assert opens[0]["status"] == "open"


def test_viewer_mount_cross_root_stops_old(tmp_path: Path):
    """T4: different root on same port → stop-old-then-start; mount prints URL only."""
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    port = 48641

    def _mount_url(root: Path) -> str:
        res = subprocess.run(
            [
                sys.executable,
                str(_VIEWER),
                "mount",
                "--revision-dir",
                str(root),
                "--port",
                str(port),
            ],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, res.stderr
        url = res.stdout.strip()
        assert url.startswith("http://127.0.0.1:")
        assert "\n" not in url
        assert not url.startswith("{")
        return url

    try:
        url_a = _mount_url(root_a)
        url_b = _mount_url(root_b)
        assert "48641" in url_a and "48641" in url_b
        assert (root_b / "_compose-viewer.server.json").is_file()
    finally:
        _run(_VIEWER, "stop", "--revision-dir", str(root_a))
        _run(_VIEWER, "stop", "--revision-dir", str(root_b))
