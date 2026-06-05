"""Tests for invalidation_hook.py: _write_invalidated and invalidate_downstream."""

import json
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from invalidation_hook import _write_invalidated, invalidate_downstream


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(tmp_path: Path, container: str, stage: str, revision: str,
                current_state: str, extra_fields: Optional[Dict] = None) -> Path:
    rev_dir = tmp_path / container / stage / revision
    rev_dir.mkdir(parents=True, exist_ok=True)
    state_path = rev_dir / "workflow-state.md"
    fields = {
        "version": "1",
        "workflow": stage,
        "current_state": current_state,
        "updated_at": "2026-06-01T00:00:00Z",
    }
    if extra_fields:
        fields.update(extra_fields)
    lines = ["---"] + [f"{k}: {v}" for k, v in fields.items()] + ["---\n"]
    state_path.write_text("\n".join(lines), encoding="utf-8")
    return state_path


def _make_sm_config(config_dir: Path,
                    feature_stages: List[str],
                    topic_stages: List[str]) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    sm = {
        "version": 2,
        "cycle_types": {
            "feature": {"stages": feature_stages, "terminal": feature_stages[-1]},
            "topic": {"stages": topic_stages, "terminal": topic_stages[-1]},
        },
    }
    (config_dir / "state-machine.json").write_text(json.dumps(sm), encoding="utf-8")


FEATURE_STAGES = [
    "product-diagnostic", "product-plan",
    "tech-diagnostic", "tech-plan",
    "tech-work-order", "tech-code",
]
TOPIC_STAGES = [
    "product-diagnostic", "product-plan",
    "tech-diagnostic", "tech-plan",
]


# ---------------------------------------------------------------------------
# _write_invalidated
# ---------------------------------------------------------------------------

class TestWriteInvalidated:
    def test_changes_current_state_to_invalidated(self, tmp_path):
        sp = _make_state(tmp_path, "c", "product-plan", "r1", "Delivered")
        _write_invalidated(sp)
        from hook_guard import _parse_frontmatter
        assert _parse_frontmatter(sp.read_text())["current_state"] == "Invalidated"

    def test_preserves_other_frontmatter_fields(self, tmp_path):
        sp = _make_state(tmp_path, "c", "product-plan", "r1", "Drafting",
                         extra_fields={"evaluate_round": "2", "tech_ref": "/a/b.md",
                                       "updated_at": "2026-05-01T12:00:00Z"})
        _write_invalidated(sp)
        from hook_guard import _parse_frontmatter
        fm = _parse_frontmatter(sp.read_text())
        assert fm["current_state"] == "Invalidated"
        assert fm["version"] == "1"
        assert fm["workflow"] == "product-plan"
        assert fm["evaluate_round"] == "2"
        assert fm["tech_ref"] == "/a/b.md"
        assert fm["updated_at"] == "2026-05-01T12:00:00Z"

    def test_already_invalidated_stays_invalidated(self, tmp_path):
        sp = _make_state(tmp_path, "c", "tech-plan", "r1", "Invalidated")
        _write_invalidated(sp)
        from hook_guard import _parse_frontmatter
        assert _parse_frontmatter(sp.read_text())["current_state"] == "Invalidated"

    def test_written_file_has_valid_frontmatter_block(self, tmp_path):
        sp = _make_state(tmp_path, "c", "product-plan", "r1", "Evaluating")
        _write_invalidated(sp)
        content = sp.read_text()
        assert content.startswith("---\n")
        assert "---" in content[3:]


# ---------------------------------------------------------------------------
# invalidate_downstream
# ---------------------------------------------------------------------------

class TestInvalidateDownstream:
    @pytest.fixture(autouse=True)
    def patch_config(self, tmp_path, monkeypatch):
        import invalidation_hook
        config_dir = tmp_path / "config"
        _make_sm_config(config_dir, FEATURE_STAGES, TOPIC_STAGES)
        monkeypatch.setattr(invalidation_hook, "_CONFIG_DIR", config_dir)
        self.cache_dir = tmp_path

    def test_feature_reopen_product_plan_invalidates_downstream(self):
        from_sp = _make_state(self.cache_dir, "feat-1", "product-plan", "r1", "Drafting")
        for stage in ["tech-diagnostic", "tech-plan", "tech-work-order", "tech-code"]:
            _make_state(self.cache_dir, "feat-1", stage, "r1", "Delivered")

        invalidate_downstream("feat-1", "product-plan", "feature", self.cache_dir)

        from hook_guard import _parse_frontmatter
        assert _parse_frontmatter(from_sp.read_text())["current_state"] == "Drafting"
        for stage in ["tech-diagnostic", "tech-plan", "tech-work-order", "tech-code"]:
            sp = self.cache_dir / "feat-1" / stage / "r1" / "workflow-state.md"
            assert _parse_frontmatter(sp.read_text())["current_state"] == "Invalidated", stage

    def test_topic_reopen_product_diagnostic_invalidates_downstream(self):
        from_sp = _make_state(self.cache_dir, "topic-1", "product-diagnostic", "r1", "Drafting")
        for stage in ["product-plan", "tech-diagnostic", "tech-plan"]:
            _make_state(self.cache_dir, "topic-1", stage, "r1", "Delivered")

        invalidate_downstream("topic-1", "product-diagnostic", "topic", self.cache_dir)

        from hook_guard import _parse_frontmatter
        assert _parse_frontmatter(from_sp.read_text())["current_state"] == "Drafting"
        for stage in ["product-plan", "tech-diagnostic", "tech-plan"]:
            sp = self.cache_dir / "topic-1" / stage / "r1" / "workflow-state.md"
            assert _parse_frontmatter(sp.read_text())["current_state"] == "Invalidated", stage

    def test_only_writes_current_state_other_fields_preserved(self):
        _make_state(self.cache_dir, "feat-1", "tech-plan", "r1", "Delivered",
                    extra_fields={"evaluate_round": "3", "tech_ref": "/ref.md"})
        invalidate_downstream("feat-1", "product-plan", "feature", self.cache_dir)
        from hook_guard import _parse_frontmatter
        sp = self.cache_dir / "feat-1" / "tech-plan" / "r1" / "workflow-state.md"
        fm = _parse_frontmatter(sp.read_text())
        assert fm["current_state"] == "Invalidated"
        assert fm["evaluate_round"] == "3"
        assert fm["tech_ref"] == "/ref.md"

    def test_does_not_modify_from_stage(self):
        from_sp = _make_state(self.cache_dir, "feat-1", "tech-plan", "r1", "Drafting")
        _make_state(self.cache_dir, "feat-1", "tech-work-order", "r1", "Delivered")
        invalidate_downstream("feat-1", "tech-plan", "feature", self.cache_dir)
        from hook_guard import _parse_frontmatter
        assert _parse_frontmatter(from_sp.read_text())["current_state"] == "Drafting"

    def test_downstream_stage_no_sessions_no_error(self):
        invalidate_downstream("feat-1", "product-plan", "feature", self.cache_dir)

    def test_already_invalidated_stays_invalidated(self):
        sp = _make_state(self.cache_dir, "feat-1", "tech-plan", "r1", "Invalidated")
        invalidate_downstream("feat-1", "product-plan", "feature", self.cache_dir)
        from hook_guard import _parse_frontmatter
        assert _parse_frontmatter(sp.read_text())["current_state"] == "Invalidated"

    def test_idempotent_second_call(self):
        _make_state(self.cache_dir, "feat-1", "tech-plan", "r1", "Delivered")
        invalidate_downstream("feat-1", "product-plan", "feature", self.cache_dir)
        invalidate_downstream("feat-1", "product-plan", "feature", self.cache_dir)
        from hook_guard import _parse_frontmatter
        sp = self.cache_dir / "feat-1" / "tech-plan" / "r1" / "workflow-state.md"
        assert _parse_frontmatter(sp.read_text())["current_state"] == "Invalidated"

    def test_only_affects_given_cycle_id(self):
        _make_state(self.cache_dir, "feat-1", "tech-plan", "r1", "Delivered")
        sp2 = _make_state(self.cache_dir, "feat-2", "tech-plan", "r1", "Delivered")
        invalidate_downstream("feat-1", "product-plan", "feature", self.cache_dir)
        from hook_guard import _parse_frontmatter
        assert _parse_frontmatter(sp2.read_text())["current_state"] == "Delivered"

    def test_old_named_sessions_not_modified(self):
        """get_sessions skips unknown state names like InProgress."""
        rev_dir = self.cache_dir / "feat-1" / "tech-plan" / "r1"
        rev_dir.mkdir(parents=True, exist_ok=True)
        sp = rev_dir / "workflow-state.md"
        sp.write_text(
            "---\nversion: 1\nworkflow: tech-plan\ncurrent_state: InProgress\n"
            "updated_at: 2026-01-01T00:00:00Z\n---\n",
            encoding="utf-8",
        )
        invalidate_downstream("feat-1", "product-plan", "feature", self.cache_dir)
        content = sp.read_text()
        assert "InProgress" in content
        assert "Invalidated" not in content
