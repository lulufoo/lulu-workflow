#!/usr/bin/env python3
"""CLI-level tests for dec_start.py's --domain-constraints-file argument.

decision never accepts pre-resolved context as a raw JSON string on the
command line — only a path to a file the holder's own resolver script
(resolve_context.py) already wrote to disk. These tests exercise that
contract at the actual subprocess/CLI boundary (main() -> parse_args() ->
_load_domain_override_file()), not just the underlying cmd_init_session()
Python function (already covered by test_dec_stage_e2e.py).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_domain_constraints_schema import load_domain_constraints  # noqa: E402
from dec_workflow_common import domain_constraints_path  # noqa: E402

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_START_PY = _DIAG_SCRIPTS / "dec_start.py"
# Inherit the ambient platform rather than forcing one: domain_constraints_path()
# below is computed in *this* process, so it must agree with whatever platform
# the subprocess resolved its cache dir under.
_SUBPROCESS_ENV = {**os.environ}


def _seed_decision_config(tmp_path: Path) -> None:
    cfg_dir = tmp_path / "skill-config" / "lulu-dev-workflow"
    cfg_dir.mkdir(parents=True)
    local_template = tmp_path / "decision-doc.template.md"
    local_template.write_text(
        "# Decision: {title}\n\n"
        "## 1. User Prior\n\n- placeholder\n\n"
        "## 2. Problem Definition\n\nTBD\n\n"
        "## 3. Direction Comparison\n\nTBD\n\n"
        "## 4. Decision Rationale\n\nTBD\n\n"
        "## 5. Scope\n\nTBD\n\n"
        "## 6. Assumptions & Risks\n\nTBD\n\n"
        "## 7. Execution Analysis\n\n### 7.1 Acceptance Criteria\n\nTBD\n",
        encoding="utf-8",
    )
    (cfg_dir / "workflow-config.json").write_text(
        json.dumps({"decision": {"decision_doc_template_url": local_template.as_uri()}}),
        encoding="utf-8",
    )


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    _seed_decision_config(tmp_path)
    return tmp_path


def _run_dec_start(project_root: Path, cycle_id: str, *extra_args: str) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable, str(_START_PY),
        "--project-root", str(project_root),
        "--cycle-id", cycle_id,
        "--stage", "lulu-bet",
        "--constraints", str(_WORKFLOW_ROOT / "lulu-bet" / "constraints-feature.json"),
        *extra_args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, env=_SUBPROCESS_ENV)


def test_domain_constraints_file_merged_into_session(project_root: Path) -> None:
    cycle_id = "dcf-ok-001"
    resolved = project_root / "resolved-context.json"
    resolved.write_text(
        json.dumps({
            "context": {
                "docs": {
                    "product_blueprint": "/cache/topic-line/lulu-blueprint/revision1/lulu-blueprint-doc.md",
                },
            },
        }),
        encoding="utf-8",
    )

    result = _run_dec_start(project_root, cycle_id, "--domain-constraints-file", str(resolved))
    assert result.returncode == 0, result.stderr
    start_payload = json.loads(result.stdout)
    assert start_payload["ok"] is True
    assert "product_blueprint" in start_payload["context_docs"]

    dc_path = project_root / domain_constraints_path(
        cycle_id, "lulu-bet",
        project_root=project_root,
        constraints_path=_WORKFLOW_ROOT / "lulu-bet" / "constraints-feature.json",
    )
    constraints = load_domain_constraints(dc_path)
    assert constraints["context"]["docs"]["product_blueprint"].endswith("lulu-blueprint-doc.md")


def test_domain_constraints_file_missing_path_errors(project_root: Path) -> None:
    cycle_id = "dcf-missing-001"
    missing = project_root / "does-not-exist.json"

    result = _run_dec_start(project_root, cycle_id, "--domain-constraints-file", str(missing))
    assert result.returncode != 0
    assert "--domain-constraints-file" in result.stderr


def test_domain_constraints_file_invalid_json_errors(project_root: Path) -> None:
    cycle_id = "dcf-badjson-001"
    bad = project_root / "resolved-context.json"
    bad.write_text("{not valid json", encoding="utf-8")

    result = _run_dec_start(project_root, cycle_id, "--domain-constraints-file", str(bad))
    assert result.returncode != 0
    assert "--domain-constraints-file" in result.stderr


def test_domain_constraints_file_non_object_errors(project_root: Path) -> None:
    cycle_id = "dcf-nonobj-001"
    non_object = project_root / "resolved-context.json"
    non_object.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    result = _run_dec_start(project_root, cycle_id, "--domain-constraints-file", str(non_object))
    assert result.returncode != 0
    assert "JSON object" in result.stderr
