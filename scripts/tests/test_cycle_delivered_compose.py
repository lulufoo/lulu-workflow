#!/usr/bin/env python3
"""Compose delivered-refs equality: package_digest, retry, extra fields."""

from __future__ import annotations

from pathlib import Path

import pytest

from cycle_delivered_refs import (
    DeliveryInconsistent,
    compose_equality_projection,
    file_digest,
    load_delivered_refs_file,
    record_delivered_ref,
    remove_delivered_ref,
)


def _pkg(tmp_path: Path, body: bytes = b'{"version":1}\n') -> Path:
    path = tmp_path / "design-package.json"
    path.write_bytes(body)
    return path


def test_compose_record_requires_digest(tmp_path: Path) -> None:
    pkg = _pkg(tmp_path)
    with pytest.raises(ValueError, match="package_digest"):
        record_delivered_ref(
            "feat-d",
            tmp_path,
            delivered_type="lulu-design",
            path=str(pkg),
            revision=1,
            profile_id="lulu-design",
            source_workflow_state="/ws.md",
            artifact="compose-package",
        )


def test_compose_exact_retry_is_noop(tmp_path: Path) -> None:
    pkg = _pkg(tmp_path)
    digest = file_digest(pkg)
    kwargs = dict(
        delivered_type="lulu-design",
        path=str(pkg),
        revision=1,
        profile_id="lulu-design",
        source_workflow_state="/ws.md",
        artifact="compose-package",
        package_digest=digest,
    )
    first = record_delivered_ref("feat-d", tmp_path, **kwargs)
    assert first["ok"] is True
    assert first["reused"] is False
    second = record_delivered_ref("feat-d", tmp_path, **kwargs)
    assert second["reused"] is True
    data = load_delivered_refs_file("feat-d", tmp_path)
    assert data["entries"]["lulu-design"]["package_digest"] == digest


def test_compose_mismatch_raises_inconsistent(tmp_path: Path) -> None:
    pkg = _pkg(tmp_path)
    record_delivered_ref(
        "feat-d",
        tmp_path,
        delivered_type="lulu-design",
        path=str(pkg),
        revision=1,
        profile_id="lulu-design",
        source_workflow_state="/ws.md",
        artifact="compose-package",
        package_digest=file_digest(pkg),
    )
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other = _pkg(other_dir)
    with pytest.raises(DeliveryInconsistent) as exc:
        record_delivered_ref(
            "feat-d",
            tmp_path,
            delivered_type="lulu-design",
            path=str(other),
            revision=1,
            profile_id="lulu-design",
            source_workflow_state="/ws.md",
            artifact="compose-package",
            package_digest=file_digest(other),
        )
    assert exc.value.code == "delivery_inconsistent"


def test_compose_extra_fields_rejected() -> None:
    with pytest.raises(ValueError, match="extra fields"):
        compose_equality_projection(
            {
                "delivered_type": "lulu-design",
                "profile_id": "lulu-design",
                "revision": 1,
                "path": "/p.json",
                "artifact": "compose-package",
                "package_digest": "a" * 64,
                "source_workflow_state": "/ws.md",
                "note": "nope",
            }
        )


def test_remove_delivered_ref_idempotent(tmp_path: Path) -> None:
    pkg = _pkg(tmp_path)
    record_delivered_ref(
        "feat-d",
        tmp_path,
        delivered_type="lulu-design",
        path=str(pkg),
        revision=1,
        profile_id="lulu-design",
        source_workflow_state="/ws.md",
        artifact="compose-package",
        package_digest=file_digest(pkg),
    )
    assert remove_delivered_ref("feat-d", tmp_path, "lulu-design") is True
    assert remove_delivered_ref("feat-d", tmp_path, "lulu-design") is False
