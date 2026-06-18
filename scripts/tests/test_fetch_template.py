#!/usr/bin/env python3
"""Tests for fetch_template.py."""

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from fetch_template import FetchTemplateError, cache_path, fetch_template, main, parse_blob_url


class TestParseBlobUrl:
    def test_parses_github_blob_url(self):
        url = (
            "https://github.com/lulufoo/lulu-workflow-framework/blob/main/"
            "lulu-dev-workflow/template/tech-plan/20-tech-plan-spec-template.md"
        )
        parsed = parse_blob_url(url)
        assert parsed["owner"] == "lulufoo"
        assert parsed["repo"] == "lulu-workflow-framework"
        assert parsed["ref"] == "main"
        assert parsed["path"].endswith("20-tech-plan-spec-template.md")

    def test_parses_multi_segment_ref(self):
        url = (
            "https://github.com/lulufoo/lulu-workflow-framework/blob/release/2026.06/"
            "lulu-dev-workflow/template/tech-plan/20-tech-plan-spec-template.md"
        )
        parsed = parse_blob_url(url)
        assert parsed["ref"] == "release/2026.06"
        assert parsed["path"] == (
            "lulu-dev-workflow/template/tech-plan/20-tech-plan-spec-template.md"
        )

    def test_parses_multi_segment_ref_with_nested_path(self):
        url = (
            "https://github.com/lulufoo/lulu-workflow-framework/blob/release/candidate/v2/"
            "lulu-dev-workflow/template/diagnostic/decision-doc.template.md"
        )
        parsed = parse_blob_url(url)
        assert parsed["ref"] == "release/candidate/v2"
        assert parsed["path"] == (
            "lulu-dev-workflow/template/diagnostic/decision-doc.template.md"
        )

    def test_rejects_blob_url_with_ref_only(self):
        with pytest.raises(FetchTemplateError, match="missing path"):
            parse_blob_url("https://github.com/o/r/blob/main")

    def test_parses_repo_root_template_path(self):
        url = (
            "https://github.com/lulufoo/lulu-workflow-framework/blob/main/"
            "template/workflow-config.json"
        )
        parsed = parse_blob_url(url)
        assert parsed["ref"] == "main"
        assert parsed["path"] == "template/workflow-config.json"

    def test_rejects_non_github_url(self):
        with pytest.raises(FetchTemplateError, match="Not a GitHub blob URL"):
            parse_blob_url("https://example.com/doc.md")

    def test_parses_path_when_known_root_not_matched(self):
        parsed = parse_blob_url("https://github.com/o/r/blob/release/candidate/template.md")
        assert parsed["ref"] == "release"
        assert parsed["path"] == "candidate/template.md"


class TestFetchTemplate:
    def _write_config(self, tmp_path: Path, payload: dict) -> None:
        cfg_path = tmp_path / "skill-config/lulu-dev-workflow/workflow-config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_cache_hit_skips_gh(self, tmp_path):
        self._write_config(tmp_path, {
            "tech-plan": {"tpt_url": "https://github.com/o/r/blob/main/path.md"},
        })
        cache = cache_path(tmp_path, "cursor", "tech-plan", "tpt_url")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text("# cached\n", encoding="utf-8")

        def fail_fetch(*_args):
            raise AssertionError("gh should not be called on cache hit")

        content = fetch_template(
            "tech-plan",
            "tpt_url",
            tmp_path,
            platform="cursor",
            gh_fetcher=fail_fetch,
        )
        assert content == "# cached\n"

    def test_cache_miss_fetches_and_writes_cache(self, tmp_path):
        url = "https://github.com/o/r/blob/main/template.md"
        self._write_config(tmp_path, {"tech-plan": {"tpt_url": url}})

        def mock_fetch(owner, repo, ref, path):
            assert (owner, repo, ref, path) == ("o", "r", "main", "template.md")
            return "# fetched\n"

        content = fetch_template(
            "tech-plan",
            "tpt_url",
            tmp_path,
            platform="cursor",
            gh_fetcher=mock_fetch,
        )
        assert content == "# fetched\n"
        cache = cache_path(tmp_path, "cursor", "tech-plan", "tpt_url")
        assert cache.read_text(encoding="utf-8") == "# fetched\n"

    def test_force_bypasses_cache(self, tmp_path):
        url = "https://github.com/o/r/blob/main/template.md"
        self._write_config(tmp_path, {"tech-plan": {"tpt_url": url}})
        cache = cache_path(tmp_path, "cursor", "tech-plan", "tpt_url")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text("# stale\n", encoding="utf-8")

        content = fetch_template(
            "tech-plan",
            "tpt_url",
            tmp_path,
            platform="cursor",
            force=True,
            gh_fetcher=lambda *_: "# fresh\n",
        )
        assert content == "# fresh\n"
        assert cache.read_text(encoding="utf-8") == "# fresh\n"

    def test_empty_url_exits_without_cache_write(self, tmp_path):
        self._write_config(tmp_path, {"tech-plan": {"tpt_url": ""}})
        with pytest.raises(FetchTemplateError, match="Empty URL"):
            fetch_template("tech-plan", "tpt_url", tmp_path, platform="cursor")
        cache = cache_path(tmp_path, "cursor", "tech-plan", "tpt_url")
        assert not cache.exists()

    def test_missing_section_raises(self, tmp_path):
        self._write_config(tmp_path, {"tech-plan": {}})
        with pytest.raises(FetchTemplateError, match="Missing key"):
            fetch_template("tech-plan", "tpt_url", tmp_path, platform="cursor")

    def test_config_not_found_raises(self, tmp_path):
        with pytest.raises(FetchTemplateError, match="workflow-config not found"):
            fetch_template("tech-plan", "tpt_url", tmp_path, platform="cursor")

    def test_gh_failure_does_not_write_cache(self, tmp_path):
        url = "https://github.com/o/r/blob/main/template.md"
        self._write_config(tmp_path, {"tech-plan": {"tpt_url": url}})

        def fail_fetch(*_args):
            raise FetchTemplateError("gh api failed")

        with pytest.raises(FetchTemplateError, match="gh api failed"):
            fetch_template(
                "tech-plan",
                "tpt_url",
                tmp_path,
                platform="cursor",
                gh_fetcher=fail_fetch,
            )
        cache = cache_path(tmp_path, "cursor", "tech-plan", "tpt_url")
        assert not cache.exists()

    def test_empty_cache_file_refetches(self, tmp_path):
        url = "https://github.com/o/r/blob/main/template.md"
        self._write_config(tmp_path, {"tech-plan": {"tpt_url": url}})
        cache = cache_path(tmp_path, "cursor", "tech-plan", "tpt_url")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text("   \n", encoding="utf-8")

        content = fetch_template(
            "tech-plan",
            "tpt_url",
            tmp_path,
            platform="cursor",
            gh_fetcher=lambda *_: "# refetched\n",
        )
        assert content == "# refetched\n"

    def test_fetches_diagnostic_template(self, tmp_path):
        url = (
            "https://github.com/lulufoo/lulu-workflow-framework/blob/main/"
            "lulu-dev-workflow/template/diagnostic/decision-doc.template.md"
        )
        self._write_config(tmp_path, {"diagnostic": {"decision_doc_template_url": url}})

        def mock_fetch(owner, repo, ref, path):
            assert owner == "lulufoo"
            assert repo == "lulu-workflow-framework"
            assert ref == "main"
            assert path == "lulu-dev-workflow/template/diagnostic/decision-doc.template.md"
            return "# diagnostic template\n"

        content = fetch_template(
            "diagnostic",
            "decision_doc_template_url",
            tmp_path,
            platform="cursor",
            gh_fetcher=mock_fetch,
        )
        assert content == "# diagnostic template\n"


class TestMainCli:
    def test_cli_success_prints_stdout(self, tmp_path, capsys):
        cfg_path = tmp_path / "skill-config/lulu-dev-workflow/workflow-config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps({
            "tech-plan": {
                "tpt_url": "https://github.com/o/r/blob/main/template.md",
            },
        }), encoding="utf-8")

        import fetch_template as mod

        original = mod.fetch_template

        def stub(*_args, **_kwargs):
            return "# cli\n"

        mod.fetch_template = stub
        try:
            code = main([
                "--section", "tech-plan",
                "--key", "tpt_url",
                "--project-root", str(tmp_path),
                "--platform", "cursor",
            ])
        finally:
            mod.fetch_template = original

        assert code == 0
        assert capsys.readouterr().out == "# cli\n"

    def test_cli_failure_returns_exit_1(self, tmp_path, capsys):
        code = main([
            "--section", "tech-plan",
            "--key", "tpt_url",
            "--project-root", str(tmp_path),
            "--platform", "cursor",
        ])
        assert code == 1
        assert capsys.readouterr().err
