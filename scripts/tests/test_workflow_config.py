#!/usr/bin/env python3
"""Tests for workflow_config_schema.py and workflow_config.py CLI."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from workflow_config_schema import (  # noqa: E402
    apply_workflow_config_from_url,
    ensure_builtin_stage_configs,
    get_stage_config_bucket,
    get_stage_config_value,
    load_stage_config,
    lookup_subagent,
    nest_compose_stage_config,
    resolve_stage_config_path,
    resolve_workflow_config_path,
    split_monolith_payload,
    workflow_config_is_present,
    write_stage_configs,
)
from workflow_config_test_helpers import write_monolith_config, write_stage_config  # noqa: E402

_DEFAULT_URL = (
    "https://github.com/example/workflow-framework/blob/main/template/workflow-config.json"
)


class TestStageConfigLoader:
    def test_load_stage_from_stages_layout(self, tmp_path: Path) -> None:
        write_stage_config(tmp_path, "lulu-exec", {"test_command": "npm test"})
        assert load_stage_config(tmp_path, "lulu-exec") == {"test_command": "npm test"}

    def test_leftover_pointer_does_not_redirect(self, tmp_path: Path) -> None:
        monolith = tmp_path / "custom" / "workflow-config.json"
        monolith.parent.mkdir(parents=True)
        monolith.write_text(
            json.dumps({"lulu-exec": {"test_command": "pnpm test"}}),
            encoding="utf-8",
        )
        cfg_path = tmp_path / ".cursor/lulu-workflow/config.json"
        cfg_path.parent.mkdir(parents=True)
        cfg_path.write_text(
            json.dumps({"workflowConfig": "custom/workflow-config.json"}),
            encoding="utf-8",
        )
        assert load_stage_config(tmp_path, "lulu-exec", "cursor") != {
            "test_command": "pnpm test",
        }

    def test_legacy_monolith_in_config_dir_fallback(self, tmp_path: Path) -> None:
        write_monolith_config(
            tmp_path,
            {"lulu-plan": {"tpt_url": "https://example.com/t.md"}},
        )
        assert load_stage_config(tmp_path, "lulu-plan") == {
            "tpt_url": "https://example.com/t.md",
        }

    def test_missing_stage_returns_empty_dict(self, tmp_path: Path) -> None:
        write_stage_config(tmp_path, "lulu-exec", {"test_command": "npm test"})
        assert load_stage_config(tmp_path, "lulu-plan") == {}

    def test_leftover_pointer_ignored_when_stages_present(self, tmp_path: Path) -> None:
        write_stage_config(tmp_path, "lulu-exec", {"test_command": "npm test"})
        cfg_path = tmp_path / ".cursor/lulu-workflow/config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps(
                {"workflowConfig": "skill-config/lulu-workflow/workflow-config.json"}
            ),
            encoding="utf-8",
        )
        assert workflow_config_is_present(tmp_path, "cursor")
        assert load_stage_config(tmp_path, "lulu-exec", "cursor") == {
            "test_command": "npm test",
        }

    def test_skill_config_dir_is_not_read(self, tmp_path: Path) -> None:
        leftover = tmp_path / "skill-config/lulu-workflow/stages"
        leftover.mkdir(parents=True)
        (leftover / "lulu-exec.json").write_text(
            json.dumps({"test_command": "UNIQUE_SKILL_CONFIG"}),
            encoding="utf-8",
        )
        assert load_stage_config(tmp_path, "lulu-exec", "cursor") != {
            "test_command": "UNIQUE_SKILL_CONFIG",
        }
        assert not workflow_config_is_present(tmp_path, "cursor")


class TestSplitMonolithPayload:
    def test_splits_version_and_stages(self) -> None:
        manifest, stages = split_monolith_payload(
            {
                "version": 1,
                "lulu-exec": {"test_command": "npm test"},
                "decision": {"decision_doc_template_url": "https://example.com/d.md"},
            }
        )
        assert manifest == {"version": 1, "layout": "stages"}
        assert stages["lulu-exec"] == {"test_command": "npm test"}
        assert stages["decision"] == {"decision_doc_template_url": "https://example.com/d.md"}

    def test_nests_compose_stage_from_profile(self) -> None:
        manifest, stages = split_monolith_payload(
            {
                "version": 1,
                "lulu-design": {
                    "tdt_section_registry_url": "https://example.com/registry.json",
                    "tdt_design_quality_framework_url": "https://example.com/quality.md",
                    "tdt_design_doc_template_url": "https://example.com/dead.md",
                },
            }
        )
        assert manifest["layout"] == "stages"
        assert stages["lulu-design"]["compose"]["tdt_section_registry_url"].endswith(
            "registry.json"
        )
        assert stages["lulu-design"]["eval"]["tdt_design_quality_framework_url"].endswith(
            "quality.md"
        )
        assert "tdt_design_doc_template_url" not in stages["lulu-design"]["compose"]
        assert "tdt_design_doc_template_url" not in stages["lulu-design"].get("eval", {})


class TestNestedComposeEvalConfig:
    def test_get_stage_config_value_reads_compose_bucket(self, tmp_path: Path) -> None:
        write_stage_config(
            tmp_path,
            "lulu-design",
            {
                "compose": {"tdt_section_registry_url": "https://example.com/r.json"},
                "eval": {"tdt_design_quality_framework_url": "https://example.com/q.md"},
            },
        )
        assert get_stage_config_value(
            tmp_path, "lulu-design", "tdt_section_registry_url"
        ).endswith("r.json")
        assert get_stage_config_value(
            tmp_path, "lulu-design", "tdt_design_quality_framework_url"
        ).endswith("q.md")

    def test_get_stage_config_bucket_eval(self, tmp_path: Path) -> None:
        write_stage_config(
            tmp_path,
            "lulu-plan",
            {
                "compose": {"tpt_section_registry_url": "https://example.com/r.json"},
                "eval": {"tpt_tech_conformance_url": "https://example.com/tc.md"},
            },
        )
        eval_cfg = get_stage_config_bucket(tmp_path, "lulu-plan", "eval")
        assert eval_cfg["tpt_tech_conformance_url"].endswith("tc.md")

    def test_nest_compose_stage_config_uses_profile(self) -> None:
        nested = nest_compose_stage_config(
            "lulu-spec",
            {
                "pst_section_registry_url": "https://example.com/r.json",
                "pst_product_eval_framework_url": "https://example.com/e.md",
            },
        )
        assert nested["compose"]["pst_section_registry_url"].endswith("r.json")
        assert nested["eval"]["pst_product_eval_framework_url"].endswith("e.md")


class TestConfigureWorkflowConfig:
    def test_writes_stages_layout(self, tmp_path: Path) -> None:
        payload = {
            "version": 1,
            "lulu-plan": {"tpt_tech_conformance_url": "https://example.com/tc.md"},
        }

        def stub_fetch(owner: str, repo: str, ref: str, path: str) -> str:
            assert owner == "example"
            assert repo == "workflow-framework"
            assert ref == "main"
            assert path == "template/workflow-config.json"
            return json.dumps(payload)

        import fetch_template as ft

        original = ft.gh_api_fetch
        ft.gh_api_fetch = stub_fetch
        try:
            target = apply_workflow_config_from_url(
                tmp_path,
                _DEFAULT_URL,
                platform="cursor",
            )
        finally:
            ft.gh_api_fetch = original

        expected_root = resolve_workflow_config_path(tmp_path, "cursor")
        assert target == expected_root
        assert (target / "manifest.json").exists()
        stage_cfg = json.loads((target / "stages" / "lulu-plan.json").read_text())
        assert stage_cfg == {
            "eval": {"tpt_tech_conformance_url": "https://example.com/tc.md"},
        }
        assert workflow_config_is_present(tmp_path, "cursor")

    def test_cli_configure_prints_root(self, tmp_path: Path) -> None:
        source = tmp_path / "workflow-config.json"
        source.write_text(json.dumps({"version": 1}), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "workflow_config.py"),
                "configure",
                "--project-root",
                str(tmp_path),
                "--platform",
                "cursor",
                "--url",
                str(source),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout.strip().endswith(".cursor/lulu-workflow")

    def test_cli_resolve_path(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "workflow_config.py"),
                "resolve-path",
                "--project-root",
                str(tmp_path),
                "--platform",
                "cursor",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout.strip().endswith(".cursor/lulu-workflow")

    def test_cli_resolve_stage_path(self, tmp_path: Path) -> None:
        write_stage_config(tmp_path, "lulu-exec", {"test_command": "npm test"})
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "workflow_config.py"),
                "resolve-stage-path",
                "--project-root",
                str(tmp_path),
                "--stage",
                "lulu-exec",
                "--platform",
                "cursor",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout.strip().endswith(
            ".cursor/lulu-workflow/stages/lulu-exec.json"
        )
        assert resolve_stage_config_path(tmp_path, "lulu-exec", "cursor").exists()

    def test_invalid_json_raises(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "fetch_template.gh_api_fetch",
            lambda *_args: "not-json",
        )
        with pytest.raises(ValueError, match="not valid JSON"):
            apply_workflow_config_from_url(tmp_path, _DEFAULT_URL, platform="cursor")

    def test_write_stage_configs(self, tmp_path: Path) -> None:
        root = tmp_path / "cfg"
        write_stage_configs(
            root,
            {"version": 2, "layout": "stages"},
            {"lulu-exec": {"test_command": "make test"}},
        )
        assert json.loads((root / "manifest.json").read_text())["version"] == 2
        assert json.loads((root / "stages" / "lulu-exec.json").read_text())[
            "test_command"
        ] == "make test"


class TestEnsureBuiltinStageConfigs:
    def test_writes_missing_builtin_stages(self, tmp_path: Path) -> None:
        created = ensure_builtin_stage_configs(tmp_path, "cursor")
        root = tmp_path / ".cursor/lulu-workflow"
        names = {path.name for path in created}
        assert "lulu-exec.json" in names
        assert "lulu-tasks.json" not in names
        assert not (root / "stages/lulu-tasks.json").exists()
        assert json.loads((root / "manifest.json").read_text())["layout"] == "stages"
        assert load_stage_config(tmp_path, "lulu-exec", "cursor")["test_commands"] == {}
        assert load_stage_config(tmp_path, "lulu-exec", "cursor")["subagent"] == ""
        assert "eval" in load_stage_config(tmp_path, "lulu-tasks", "cursor")


class TestLookupSubagent:
    def test_string_is_stripped(self) -> None:
        assert lookup_subagent({"subagent": "  composer-2.5-fast  "}) == "composer-2.5-fast"

    def test_empty_or_missing_is_blank(self) -> None:
        assert lookup_subagent({}) == ""
        assert lookup_subagent({"subagent": ""}) == ""
        assert lookup_subagent({"subagent": "   "}) == ""

    def test_legacy_object_is_blank(self) -> None:
        assert lookup_subagent({"subagent": {"cursor": "composer-2.5-fast"}}) == ""
