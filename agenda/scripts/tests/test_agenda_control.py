#!/usr/bin/env python3
"""Tests for agenda_schema / agenda_control."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS))

from agenda_schema import (  # noqa: E402
    agenda_path,
    blocking_items,
    load_agenda,
)
from agenda_control import main as agenda_main  # noqa: E402

_CTL = _SCRIPTS / "agenda_control.py"


def _run_cli(args: list[str]) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(_CTL), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, payload


def test_add_blocker_and_blocking_list(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    code, out = _run_cli(
        [
            "add",
            "--revision-dir",
            str(rev),
            "--class",
            "blocker",
            "--text",
            "两类翻译清单须确认",
        ]
    )
    assert code == 0
    assert out["ok"] is True
    assert out["item"]["id"] == "A-1"
    assert out["item"]["async"] is False

    code, listed = _run_cli(
        ["list", "--revision-dir", str(rev), "--blocking-only"]
    )
    assert code == 0
    assert len(listed["items"]) == 1
    assert listed["items"][0]["id"] == "A-1"


def test_async_blocker_not_in_blocking_list(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    _run_cli(
        [
            "add",
            "--revision-dir",
            str(rev),
            "--class",
            "blocker",
            "--text",
            "async work",
            "--async",
        ]
    )
    code, listed = _run_cli(
        ["list", "--revision-dir", str(rev), "--blocking-only"]
    )
    assert code == 0
    assert listed["items"] == []


def test_note_never_blocking(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    code, out = _run_cli(
        [
            "add",
            "--revision-dir",
            str(rev),
            "--class",
            "note",
            "--text",
            "remember later",
        ]
    )
    assert code == 0
    assert "async" not in out["item"]
    code, listed = _run_cli(
        ["list", "--revision-dir", str(rev), "--blocking-only"]
    )
    assert listed["items"] == []


def test_note_rejects_async(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    code, out = _run_cli(
        [
            "add",
            "--revision-dir",
            str(rev),
            "--class",
            "note",
            "--text",
            "x",
            "--async",
        ]
    )
    assert code != 0
    assert out["ok"] is False


def test_waive_requires_reason(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    _run_cli(
        [
            "add",
            "--revision-dir",
            str(rev),
            "--class",
            "blocker",
            "--text",
            "must do",
        ]
    )
    code, out = _run_cli(
        [
            "update",
            "--revision-dir",
            str(rev),
            "--id",
            "A-1",
            "--status",
            "waived",
        ]
    )
    assert code != 0
    assert "reason" in out.get("error", "")

    code, out = _run_cli(
        [
            "update",
            "--revision-dir",
            str(rev),
            "--id",
            "A-1",
            "--status",
            "waived",
            "--reason",
            "out of scope this stage",
        ]
    )
    assert code == 0
    code, listed = _run_cli(
        ["list", "--revision-dir", str(rev), "--blocking-only"]
    )
    assert listed["items"] == []


def test_release_clears_blocking(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    _run_cli(
        [
            "add",
            "--revision-dir",
            str(rev),
            "--class",
            "blocker",
            "--text",
            "must do",
        ]
    )
    _run_cli(
        [
            "update",
            "--revision-dir",
            str(rev),
            "--id",
            "A-1",
            "--status",
            "released",
        ]
    )
    data = load_agenda(agenda_path(rev))
    assert blocking_items(data) == []


def test_missing_file_empty_blocking(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    data = load_agenda(agenda_path(rev))
    assert data["items"] == []
    assert blocking_items(data) == []
    code, listed = _run_cli(
        ["list", "--revision-dir", str(rev), "--blocking-only"]
    )
    assert code == 0
    assert listed["exists"] is False
    assert listed["items"] == []


def test_menu_lists_commands() -> None:
    code, out = _run_cli(["menu"])
    assert code == 0
    assert out["ok"] is True
    keys = {c["key"] for c in out["commands"]}
    assert keys == {"add", "update", "list", "menu"}
    labels = {o["label"] for o in out["l1_options"]}
    assert "agenda 查看命令" in labels
    assert "agenda 新增 blocker" in labels
    assert "agenda 新增 note" in labels
    assert "agenda 查看 blocker list" in labels
    assert all(str(o["label"]).startswith("agenda ") for o in out["l1_options"])


def test_main_add_via_argv(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    # exercise in-process main for coverage without subprocess edge cases
    rc = agenda_main(
        [
            "add",
            "--revision-dir",
            str(rev),
            "--class",
            "blocker",
            "--text",
            "in-process",
        ]
    )
    assert rc == 0
    assert agenda_path(rev).is_file()


def test_resolve_from_session_active_doc(tmp_path: Path) -> None:
    from agenda_session import CACHE_DIR, resolve_revision_dir

    cycle = "feat-agenda"
    profile = "lulu-spec"
    session_base = tmp_path / CACHE_DIR / cycle / profile
    rev = session_base / "revision2"
    rev.mkdir(parents=True)
    (session_base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 2\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    profile_json = tmp_path / "compose-profile.json"
    profile_json.write_text(
        json.dumps({"profile_id": profile}),
        encoding="utf-8",
    )
    (session_base / ".compose-profile-path").write_text(
        "compose-profile.json\n",
        encoding="utf-8",
    )

    resolved = resolve_revision_dir(
        tmp_path, cycle_id=cycle, profile_id=profile
    )
    assert resolved == rev.resolve()

    code, out = _run_cli(
        [
            "add",
            "--project-root",
            str(tmp_path),
            "--cycle-id",
            cycle,
            "--profile",
            profile,
            "--class",
            "blocker",
            "--text",
            "from session",
        ]
    )
    assert code == 0
    assert out["ok"] is True
    assert Path(out["revision_dir"]) == rev.resolve()
    assert (rev / "agenda.json").is_file()
