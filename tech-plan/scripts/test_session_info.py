#!/usr/bin/env python3
"""Tests for tech-plan session_info.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_info import delivery_preview, get_session_info, session_snapshot  # noqa: E402
from workflow_state_schema import save_workflow_state  # noqa: E402

_SCRIPT = Path(__file__).resolve().parent / "session_info.py"


def _setup_cycle(tmp_path: Path) -> tuple[Path, str]:
    cycle_id = "feat-session-info"
    base = tmp_path / ".cache" / "cursor" / "lulu-dev-workflow" / cycle_id / "tech" / "plan"
    revision = base / "revision1"
    revision.mkdir(parents=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\n---\n",
        encoding="utf-8",
    )
    (revision / "tech-doc.md").write_text(
        "---\n\n"
        "# Feature X\n\n"
        "## North Star\n\n"
        "Deliver a unified session info facade.\n\n"
        "## Key Decisions\n\n"
        "KD.\n",
        encoding="utf-8",
    )
    from workflow_state_schema import init_drafting  # noqa: WPS433

    ws_path = revision / "workflow-state.md"
    init_drafting(ws_path, mode="product", product_ref="/p.md")
    save_workflow_state(ws_path, {"current_state": "ReadyForDelivery"})
    return tmp_path, cycle_id


class TestDeliveryPreview:
    def test_returns_delivery_fields(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        payload = delivery_preview(cycle_id, project_root)
        assert payload["view"] == "delivery-preview"
        assert payload["active_doc"] == 1
        assert payload["current_state"] == "ReadyForDelivery"
        assert payload["tech_doc"]["title"] == "Feature X"
        assert "session info facade" in payload["tech_doc"]["summary"]
        assert payload["tech_doc"]["path"].endswith("revision1/tech-doc.md")


class TestSessionSnapshot:
    def test_returns_workflow_and_tech_doc(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        payload = session_snapshot(cycle_id, project_root)
        assert payload["view"] == "session"
        assert payload["workflow_state"]["mode"] == "product"
        assert payload["tech_doc"]["revision"] == 1


class TestGetSessionInfo:
    def test_unknown_view_raises(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        with pytest.raises(ValueError, match="unknown view"):
            get_session_info(cycle_id, project_root, view="invalid")


class TestCli:
    def test_delivery_preview_view(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                cycle_id,
                "--project-root",
                str(project_root),
                "--view",
                "delivery-preview",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["view"] == "delivery-preview"
        assert payload["tech_doc"]["title"] == "Feature X"
