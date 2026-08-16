"""Tests for per-round MaterializedCorpusSnapshot."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from corpus_snapshot import (  # noqa: E402
    SNAPSHOT_REF,
    corpus_digest_from_manifest,
    load_materialized_corpus,
    materialize_corpus_snapshot,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _corpus(method: Path, sot: Path, template: Path) -> dict:
    return {
        "id": "snapshot-test",
        "schema_version": "6",
        "version": "2",
        "scope": "tests",
        "context": "offline",
        "dimension_dispatch": "parallel",
        "dimensions": [
            {
                "id": "quality",
                "label": "Quality",
                "eval_target": {"path": "/tmp/target.md"},
                "sots": [{"ref": str(sot)}],
                "method": {"ref": str(method), "focus": "quality"},
                "review": {
                    "seq": 1,
                    "output_path": "quality.md",
                    "template": str(template),
                },
            }
        ],
    }


def test_materialize_and_reload_file_assets(tmp_path: Path) -> None:
    method = tmp_path / "method.md"
    sot = tmp_path / "sot.md"
    template = tmp_path / "review.md"
    method.write_text("method-body", encoding="utf-8")
    sot.write_text("sot-body", encoding="utf-8")
    template.write_text("template-body", encoding="utf-8")
    dest = tmp_path / "corpus-snapshot"
    manifest = materialize_corpus_snapshot(
        dest,
        _corpus(method, sot, template),
        method_roots=[tmp_path],
        sot_roots=[tmp_path],
    )
    assert manifest["corpus_digest"] == corpus_digest_from_manifest(manifest)
    assert SNAPSHOT_REF.endswith("manifest.json")
    loaded = load_materialized_corpus(dest, expected_digest=manifest["corpus_digest"])
    assert Path(loaded["dimensions"][0]["method"]["ref"]).read_text(
        encoding="utf-8"
    ) == "method-body"
    method.write_text("changed", encoding="utf-8")
    reloaded = load_materialized_corpus(dest, expected_digest=manifest["corpus_digest"])
    assert Path(reloaded["dimensions"][0]["method"]["ref"]).read_text(
        encoding="utf-8"
    ) == "method-body"


def test_asset_drift_is_incompatible(tmp_path: Path) -> None:
    method = tmp_path / "method.md"
    sot = tmp_path / "sot.md"
    template = tmp_path / "review.md"
    method.write_text("method-body", encoding="utf-8")
    sot.write_text("sot-body", encoding="utf-8")
    template.write_text("template-body", encoding="utf-8")
    dest = tmp_path / "corpus-snapshot"
    manifest = materialize_corpus_snapshot(
        dest,
        _corpus(method, sot, template),
        method_roots=[tmp_path],
        sot_roots=[tmp_path],
    )
    asset = dest / manifest["assets"][0]["snapshot_path"]
    asset.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="incompatible_round"):
        load_materialized_corpus(dest, expected_digest=manifest["corpus_digest"])


def test_directory_sot_uses_git_worktree_view(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    tracked = repo / "src" / "a.py"
    tracked.parent.mkdir()
    tracked.write_text("tracked\n", encoding="utf-8")
    _git(repo, "add", "src/a.py")
    _git(repo, "commit", "-m", "init")
    untracked = repo / "src" / "b.py"
    untracked.write_text("untracked\n", encoding="utf-8")
    ignored = repo / "src" / "ignored.tmp"
    ignored.write_text("ignored\n", encoding="utf-8")
    (repo / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    method = repo / "method.md"
    template = repo / "review.md"
    method.write_text("m", encoding="utf-8")
    template.write_text("t", encoding="utf-8")
    dest = tmp_path / "snap"
    manifest = materialize_corpus_snapshot(
        dest,
        {
            "id": "dir-test",
            "schema_version": "6",
            "version": "2",
            "scope": "tests",
            "context": "offline",
            "dimension_dispatch": "parallel",
            "dimensions": [
                {
                    "id": "code",
                    "label": "Code",
                    "eval_target": {"path": "/tmp/t"},
                    "sots": [{"ref": "."}],
                    "method": {"ref": str(method), "focus": "code"},
                    "review": {
                        "seq": 1,
                        "output_path": "c.md",
                        "template": str(template),
                    },
                }
            ],
        },
        method_roots=[repo],
        sot_roots=[repo],
    )
    loaded = load_materialized_corpus(dest, expected_digest=manifest["corpus_digest"])
    view = Path(loaded["dimensions"][0]["sots"][0]["ref"])
    assert (view / "src" / "a.py").read_text(encoding="utf-8") == "tracked\n"
    assert (view / "src" / "b.py").read_text(encoding="utf-8") == "untracked\n"
    assert not (view / "src" / "ignored.tmp").exists()
    tracked.write_text("changed\n", encoding="utf-8")
    assert (view / "src" / "a.py").read_text(encoding="utf-8") == "tracked\n"


def test_absolute_source_outside_roots_is_rejected(tmp_path: Path) -> None:
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()
    method = inside / "method.md"
    template = inside / "review.md"
    sot = outside / "secret.md"
    method.write_text("m", encoding="utf-8")
    template.write_text("t", encoding="utf-8")
    sot.write_text("secret", encoding="utf-8")
    with pytest.raises(ValueError, match="outside allowed roots"):
        materialize_corpus_snapshot(
            tmp_path / "snap",
            _corpus(method, sot, template),
            method_roots=[inside],
            sot_roots=[inside],
        )


def test_directory_sot_records_deleted_tracked_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    tracked = repo / "src" / "a.py"
    tracked.parent.mkdir()
    tracked.write_text("tracked\n", encoding="utf-8")
    gone = repo / "src" / "gone.py"
    gone.write_text("gone\n", encoding="utf-8")
    _git(repo, "add", "src/a.py", "src/gone.py")
    _git(repo, "commit", "-m", "init")
    gone.unlink()
    method = repo / "method.md"
    template = repo / "review.md"
    method.write_text("m", encoding="utf-8")
    template.write_text("t", encoding="utf-8")
    dest = tmp_path / "snap"
    manifest = materialize_corpus_snapshot(
        dest,
        {
            "id": "dir-deleted",
            "schema_version": "6",
            "version": "2",
            "scope": "tests",
            "context": "offline",
            "dimension_dispatch": "parallel",
            "dimensions": [
                {
                    "id": "code",
                    "label": "Code",
                    "eval_target": {"path": "/tmp/t"},
                    "sots": [{"ref": "."}],
                    "method": {"ref": str(method), "focus": "code"},
                    "review": {
                        "seq": 1,
                        "output_path": "c.md",
                        "template": str(template),
                    },
                }
            ],
        },
        method_roots=[repo],
        sot_roots=[repo],
    )
    dir_manifest = json.loads(
        (dest / "assets" / "directories" / "d-000001" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    deleted = [item for item in dir_manifest["files"] if item.get("status") == "deleted"]
    assert deleted == [
        {"path": "src/gone.py", "mode": 0, "digest": "", "status": "deleted"}
    ]
    view = dest / "assets" / "directories" / "d-000001" / "view"
    assert not (view / "src" / "gone.py").exists()
    load_materialized_corpus(dest, expected_digest=manifest["corpus_digest"])
    extra = view / "src" / "sneaky.py"
    extra.write_text("nope\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected snapshot file"):
        load_materialized_corpus(dest, expected_digest=manifest["corpus_digest"])
    extra.unlink()
    (view / "src" / "gone.py").write_text("back\n", encoding="utf-8")
    with pytest.raises(ValueError, match="deleted snapshot path still present"):
        load_materialized_corpus(dest, expected_digest=manifest["corpus_digest"])


def test_directory_sot_rejects_gitlink_submodule(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    tracked = repo / "src" / "a.py"
    tracked.parent.mkdir()
    tracked.write_text("tracked\n", encoding="utf-8")
    _git(repo, "add", "src/a.py")
    _git(repo, "commit", "-m", "init")
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{sha},vendor/lib",
        ],
        check=True,
        capture_output=True,
    )
    method = repo / "method.md"
    template = repo / "review.md"
    method.write_text("m", encoding="utf-8")
    template.write_text("t", encoding="utf-8")
    with pytest.raises(ValueError, match="submodule"):
        materialize_corpus_snapshot(
            tmp_path / "snap",
            {
                "id": "dir-sub",
                "schema_version": "6",
                "version": "2",
                "scope": "tests",
                "context": "offline",
                "dimension_dispatch": "parallel",
                "dimensions": [
                    {
                        "id": "code",
                        "label": "Code",
                        "eval_target": {"path": "/tmp/t"},
                        "sots": [{"ref": "."}],
                        "method": {"ref": str(method), "focus": "code"},
                        "review": {
                            "seq": 1,
                            "output_path": "c.md",
                            "template": str(template),
                        },
                    }
                ],
            },
            method_roots=[repo],
            sot_roots=[repo],
        )


def _dir_corpus(method: Path, template: Path, sot_ref: str = ".") -> dict:
    return {
        "id": "dir-sot",
        "schema_version": "6",
        "version": "2",
        "scope": "tests",
        "context": "offline",
        "dimension_dispatch": "parallel",
        "dimensions": [
            {
                "id": "code",
                "label": "Code",
                "eval_target": {"path": "/tmp/t"},
                "sots": [{"ref": sot_ref}],
                "method": {"ref": str(method), "focus": "code"},
                "review": {
                    "seq": 1,
                    "output_path": "c.md",
                    "template": str(template),
                },
            }
        ],
    }


def test_directory_sot_rejects_escaping_symlink(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    tracked = repo / "src" / "a.py"
    tracked.parent.mkdir()
    tracked.write_text("tracked\n", encoding="utf-8")
    link = repo / "leak"
    link.symlink_to(outside)
    _git(repo, "add", "src/a.py", "leak")
    _git(repo, "commit", "-m", "init")
    method = repo / "method.md"
    template = repo / "review.md"
    method.write_text("m", encoding="utf-8")
    template.write_text("t", encoding="utf-8")
    with pytest.raises(ValueError, match="symlink"):
        materialize_corpus_snapshot(
            tmp_path / "snap",
            _dir_corpus(method, template),
            method_roots=[repo],
            sot_roots=[repo],
        )


def test_directory_sot_subdir_skips_sibling_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    keep = repo / "docs" / "keep.md"
    keep.parent.mkdir()
    keep.write_text("keep\n", encoding="utf-8")
    sibling = repo / "src" / "other.py"
    sibling.parent.mkdir()
    sibling.write_text("other\n", encoding="utf-8")
    _git(repo, "add", "docs/keep.md", "src/other.py")
    _git(repo, "commit", "-m", "init")
    method = repo / "method.md"
    template = repo / "review.md"
    method.write_text("m", encoding="utf-8")
    template.write_text("t", encoding="utf-8")
    dest = tmp_path / "snap"
    materialize_corpus_snapshot(
        dest,
        _dir_corpus(method, template, sot_ref="docs"),
        method_roots=[repo],
        sot_roots=[repo],
    )
    view = dest / "assets" / "directories" / "d-000001" / "view"
    assert (view / "keep.md").is_file()
    assert not (view / "src").exists()


def test_method_must_stay_under_workflow_root(tmp_path: Path) -> None:
    workflow = tmp_path / "lulu-dev-workflow"
    workflow.mkdir()
    leaked = tmp_path / "leaked.md"
    leaked.write_text("outside", encoding="utf-8")
    sot = workflow / "sot.md"
    template = workflow / "review.md"
    sot.write_text("sot", encoding="utf-8")
    template.write_text("tpl", encoding="utf-8")
    with pytest.raises(ValueError, match="outside workflow root"):
        materialize_corpus_snapshot(
            tmp_path / "snap",
            _corpus(leaked, sot, template),
            method_roots=[workflow, tmp_path],
            sot_roots=[tmp_path],
            method_must_stay_under=workflow,
        )


def test_repo_relative_method_stays_under_workflow_root(tmp_path: Path) -> None:
    workflow = tmp_path / "lulu-dev-workflow"
    method = workflow / "eval" / "methods" / "quality.md"
    method.parent.mkdir(parents=True)
    method.write_text("method-body", encoding="utf-8")
    sot = tmp_path / "sot.md"
    template = workflow / "eval" / "review.template.md"
    sot.write_text("sot", encoding="utf-8")
    template.write_text("tpl", encoding="utf-8")
    dest = tmp_path / "snap"
    corpus = _corpus(
        Path("lulu-dev-workflow/eval/methods/quality.md"),
        sot,
        Path("eval/review.template.md"),
    )
    manifest = materialize_corpus_snapshot(
        dest,
        corpus,
        method_roots=[workflow, tmp_path],
        sot_roots=[tmp_path],
        method_must_stay_under=workflow,
    )
    loaded = load_materialized_corpus(dest, expected_digest=manifest["corpus_digest"])
    assert Path(loaded["dimensions"][0]["method"]["ref"]).read_text(
        encoding="utf-8"
    ) == "method-body"
