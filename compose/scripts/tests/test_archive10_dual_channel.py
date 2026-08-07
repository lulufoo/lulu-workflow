#!/usr/bin/env python3
"""archive-10.0 dual-channel landing: topic-current, fact-settle, collab arc tool."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent.parent / "section"
_TOPIC_CTL = _SECTION / "topic_current_control.py"
_FACT_CTL = _SECTION / "fact_settle_control.py"
_ARC_TOOL = _SECTION / "narrative_arc_tool_control.py"
_VIEWER = _SECTION / "narrative_arc_viewer_control.py"

sys.path.insert(0, str(_SECTION))
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
    code, payload, err = _run(
        _TOPIC_CTL,
        "set",
        "--revision-dir",
        str(tmp_path),
        "--title",
        "Traction",
        "--scope",
        "D1+D2 boundary",
    )
    assert code == 0, err
    assert payload["topic"]["clarified"] is True

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


def test_fact_settle_requires_confirm_and_signals_stale(tmp_path: Path):
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


def test_narrative_arc_tool_regenerate_path_and_backup(tmp_path: Path):
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
    out.write_text('{"version":"1","kind":"narrative-arc-collab","status":"display","tree":{"id":"root","title":"old","children":[]},"leaves":[]}\n', encoding="utf-8")

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

    # Formal path hard-banned
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
    # Drop F-2 attachment artificially
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


def test_viewer_mount_cross_root_stops_old(tmp_path: Path):
    """T4: different root on same port → stop-old-then-start."""
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    port = 48641
    try:
        code_a, payload_a, err_a = _run(
            _VIEWER,
            "mount",
            "--revision-dir",
            str(root_a),
            "--port",
            str(port),
        )
        assert code_a == 0, err_a
        assert payload_a.get("ok") is True
        code_b, payload_b, err_b = _run(
            _VIEWER,
            "mount",
            "--revision-dir",
            str(root_b),
            "--port",
            str(port),
        )
        assert code_b == 0, err_b
        assert payload_b.get("ok") is True
        assert payload_b.get("reused") is False
        assert str(payload_b.get("root", "")).endswith("/b") or Path(
            payload_b["root"]
        ).resolve() == root_b.resolve()
    finally:
        _run(_VIEWER, "stop", "--revision-dir", str(root_a))
        _run(_VIEWER, "stop", "--revision-dir", str(root_b))
