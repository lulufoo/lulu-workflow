"""eval_entry host root: omit uses cwd; mismatch exits 1."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eval_entry  # noqa: E402

_ENTRY = Path(__file__).resolve().parents[1] / "eval_entry.py"


def test_parse_entry_args_omit_uses_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    args = eval_entry.parse_entry_args(
        ["--cycle-id", "C1", "begin-eval-round"],
    )
    assert args.project_root == tmp_path.resolve()


def test_parse_entry_args_match_ok(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    args = eval_entry.parse_entry_args(
        [
            "--cycle-id",
            "C1",
            "--project-root",
            str(tmp_path),
            "begin-eval-round",
        ]
    )
    assert args.project_root == tmp_path.resolve()


def test_parse_entry_args_mismatch_exits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(SystemExit) as exc:
        eval_entry.parse_entry_args(
            [
                "--cycle-id",
                "C1",
                "--project-root",
                str(other),
                "begin-eval-round",
            ]
        )
    assert exc.value.code == 1
    assert "must equal process cwd" in capsys.readouterr().err


def test_subprocess_mismatch_with_explicit_cwd(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(_ENTRY),
            "--cycle-id",
            "C1",
            "--project-root",
            str(other),
            "begin-eval-round",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "must equal process cwd" in result.stderr
