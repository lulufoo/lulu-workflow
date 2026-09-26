#!/usr/bin/env python3
"""Tests for workflow_paths.load_profile session vs authoring resolution."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
for _p in (_SCRIPTS / "_kernel", _SCRIPTS / "schema" / "session"):
    sys.path.insert(0, str(_p))

from workflow_paths import (  # noqa: E402
    active_profile_path,
    compose_profile_path,
    load_profile,
    read_active_profile,
    resolve_revision_runtime_profile,
    seed_profile_pointer_for_tests,
    validate_compose_profile_path,
    write_active_profile,
)


def _bind_session(session_base: Path, profile_path: Path, *, active_doc: int = 2) -> None:
    digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    session_base.mkdir(parents=True, exist_ok=True)
    (session_base / "session-state.md").write_text(
        "---\n"
        "version: 2\n"
        f"active_doc: {active_doc}\n"
        f"profile_path: {profile_path.resolve()}\n"
        f"profile_digest: {digest}\n"
        "start_id: test\n"
        "holder_finalized: true\n"
        "updated_at: 2024-01-01T00:00:00+00:00\n"
        "---\n",
        encoding="utf-8",
    )


def _seed_revision_runtime_profile(
    project_root: Path,
    *,
    cycle_id: str = "revision-profile-cycle",
    profile_id: str = "lulu-design",
) -> tuple[Path, Path, Path]:
    profile_path = project_root / "runtime-profiles" / f"{profile_id}.json"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps({"profile_id": profile_id, "runtime": "session-bound"}),
        encoding="utf-8",
    )
    session_base = active_profile_path(project_root, cycle_id).parent / profile_id
    session_base.mkdir(parents=True, exist_ok=True)
    _bind_session(session_base, profile_path, active_doc=2)
    write_active_profile(project_root, cycle_id, profile_id)
    revision_root = session_base / "revision2"
    revision_root.mkdir()
    return session_base, revision_root, profile_path.resolve()


def test_load_profile_authoring_when_project_root_omitted() -> None:
    data = load_profile("lulu-plan")
    assert data["profile_id"] == "lulu-plan"
    assert compose_profile_path("lulu-plan").is_file()


def test_load_profile_authoring_when_cycle_unresolvable(tmp_path: Path) -> None:
    data = load_profile("lulu-plan", project_root=tmp_path)
    assert data["profile_id"] == "lulu-plan"


def test_load_profile_session_via_pointer(tmp_path: Path) -> None:
    seed_profile_pointer_for_tests(tmp_path, "feat-load-profile", "lulu-plan")
    data = load_profile("lulu-plan", project_root=tmp_path, cycle_id="feat-load-profile")
    assert data["profile_id"] == "lulu-plan"
    assert data["document"]["filename"] == "tech-doc.md"


def test_load_profile_raises_without_pointer_when_cycle_id_given(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="session-state.md not found"):
        load_profile("lulu-plan", project_root=tmp_path, cycle_id="missing-pointer-cycle")


def test_validate_compose_profile_path_accepts_non_authoring(tmp_path: Path) -> None:
    instance = tmp_path / "session" / "compose-profile.json"
    instance.parent.mkdir(parents=True)
    instance.write_text(
        compose_profile_path("lulu-plan").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    validate_compose_profile_path(instance)


def test_validate_compose_profile_path_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--profile-path not found"):
        validate_compose_profile_path(tmp_path / "missing.json")


def test_seed_writes_active_profile(tmp_path: Path) -> None:
    seed_profile_pointer_for_tests(tmp_path, "feat-active-profile", "lulu-design")
    assert read_active_profile(tmp_path, "feat-active-profile") == "lulu-design"
    data = load_profile(
        project_root=tmp_path,
        cycle_id="feat-active-profile",
    )
    assert data["profile_id"] == "lulu-design"


def test_resolve_revision_runtime_profile_from_revision_root(tmp_path: Path) -> None:
    session_base, revision_root, profile_path = _seed_revision_runtime_profile(tmp_path)

    context = resolve_revision_runtime_profile(revision_root, tmp_path)

    assert context.session_base == session_base.resolve()
    assert context.revision_root == revision_root.resolve()
    assert context.profile_path == profile_path
    assert context.profile_id == "lulu-design"
    assert context.profile_data["runtime"] == "session-bound"


def test_resolve_revision_runtime_profile_from_nested_execution(tmp_path: Path) -> None:
    session_base, revision_root, _ = _seed_revision_runtime_profile(tmp_path)
    slice_dir = revision_root / "execution"
    slice_dir.mkdir()

    context = resolve_revision_runtime_profile(slice_dir, tmp_path)

    assert context.session_base == session_base.resolve()
    assert context.revision_root == revision_root.resolve()
    assert context.profile_id == "lulu-design"


def test_resolve_revision_runtime_profile_rejects_active_mismatch(
    tmp_path: Path,
) -> None:
    _, revision_root, _ = _seed_revision_runtime_profile(
        tmp_path,
        cycle_id="mismatch-cycle",
    )
    write_active_profile(tmp_path, "mismatch-cycle", "lulu-plan")

    with pytest.raises(ValueError, match="active profile mismatch"):
        resolve_revision_runtime_profile(
            revision_root,
            tmp_path,
            cycle_id="mismatch-cycle",
        )


def test_resolve_revision_runtime_profile_rejects_missing_pointer(
    tmp_path: Path,
) -> None:
    revision_root = tmp_path / "cache" / "session" / "revision1"
    revision_root.mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="session-state.md not found"):
        resolve_revision_runtime_profile(revision_root, tmp_path)


@pytest.mark.parametrize("missing_target", [True, False])
def test_resolve_revision_runtime_profile_rejects_empty_or_missing_target(
    tmp_path: Path,
    missing_target: bool,
) -> None:
    session_base = tmp_path / "cache" / "session"
    revision_root = session_base / "revision1"
    revision_root.mkdir(parents=True)
    if missing_target:
        ghost = tmp_path / "runtime-profiles" / "missing.json"
        digest = "0" * 64
        (session_base / "session-state.md").write_text(
            "---\nversion: 2\nactive_doc: 1\n"
            f"profile_path: {ghost}\nprofile_digest: {digest}\n"
            "start_id: test\nholder_finalized: true\n"
            "updated_at: 2024-01-01T00:00:00+00:00\n---\n",
            encoding="utf-8",
        )
        with pytest.raises(FileNotFoundError):
            resolve_revision_runtime_profile(revision_root, tmp_path)
    else:
        (session_base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\n---\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            resolve_revision_runtime_profile(revision_root, tmp_path)


@pytest.mark.parametrize(
    ("profile_text", "message"),
    [
        ("{not-json", "Expecting property name"),
        (json.dumps({"profile_id": "  "}), "nonempty profile_id"),
    ],
)
def test_resolve_revision_runtime_profile_rejects_invalid_profile(
    tmp_path: Path,
    profile_text: str,
    message: str,
) -> None:
    profile_path = tmp_path / "runtime-profiles" / "invalid.json"
    profile_path.parent.mkdir()
    profile_path.write_text(profile_text, encoding="utf-8")
    session_base = tmp_path / "cache" / "session"
    revision_root = session_base / "revision1"
    revision_root.mkdir(parents=True)
    _bind_session(session_base, profile_path, active_doc=1)

    with pytest.raises((json.JSONDecodeError, ValueError), match=message):
        resolve_revision_runtime_profile(revision_root, tmp_path)


def test_resolve_revision_runtime_profile_rejects_malformed_revision_path(
    tmp_path: Path,
) -> None:
    session_base, _, _ = _seed_revision_runtime_profile(tmp_path)
    malformed = session_base / "draft1"
    malformed.mkdir()

    with pytest.raises(ValueError, match="malformed revision path"):
        resolve_revision_runtime_profile(malformed, tmp_path)


def test_resolve_revision_runtime_profile_outside_project_root(
    tmp_path: Path,
) -> None:
    session_base, revision_root, profile_path = _seed_revision_runtime_profile(tmp_path)
    _bind_session(session_base, profile_path, active_doc=2)
    other_root = tmp_path / "other-project"
    other_root.mkdir()

    context = resolve_revision_runtime_profile(revision_root, other_root)

    assert context.profile_path == profile_path
    assert context.profile_id == "lulu-design"
