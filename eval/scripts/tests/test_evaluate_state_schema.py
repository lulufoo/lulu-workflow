#!/usr/bin/env python3
"""Tests for the evaluate-state v7 data contract."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import evaluate_state_ops  # noqa: E402
from evaluate_state_schema import (  # noqa: E402
    all_dims_at_least,
    build_initial_evaluate_state,
    get_schema,
    is_v7_state,
    load_evaluate_state,
    parse_dimension_status,
    parse_handling_policy,
    save_evaluate_state,
    validate_evaluate_state,
)
from evaluate_state_ops import (  # noqa: E402
    build_initial_evaluate_state_for_corpus,
    init_evaluate_state_for_corpus,
    locked_patch_evaluate_state,
)


def _state(
    *,
    capability: str = "full-remediation",
    policies: dict[str, str] | None = None,
) -> dict[str, str]:
    return build_initial_evaluate_state(
        dimension_ids=["a", "b"],
        corpus_ref="synthetic@2",
        corpus_fingerprint="abc123",
        eval_capability=capability,
        handling_policy=policies or {"a": "class-default", "b": "human-first"},
    )


def _corpus() -> dict:
    return {
        "id": "synthetic",
        "schema_version": "6",
        "version": "2",
        "scope": "tests",
        "context": "offline",
        "dimension_dispatch": "parallel",
        "dimensions": [
            {
                "id": "a",
                "label": "A",
                "eval_target": {"path": "/tmp/a"},
                "sots": [],
                "method": {"ref": "method.md", "focus": "a"},
                "review": {"seq": 1, "output_path": "a.md", "template": "review.md"},
            },
            {
                "id": "b",
                "label": "B",
                "handling_policy": "human-first",
                "eval_target": {"path": "/tmp/b"},
                "sots": [],
                "method": {"ref": "method.md", "focus": "b"},
                "review": {"seq": 2, "output_path": "b.md", "template": "review.md"},
            },
        ],
    }


def _set_counts(
    state: dict[str, str],
    *,
    a: tuple[int, int],
    b: tuple[int, int],
) -> None:
    state["issue_counts"] = (
        f'{{"a":{{"total":{a[0]},"resolved":{a[1]}}},'
        f'"b":{{"total":{b[0]},"resolved":{b[1]}}}}}'
    )
    state["total_issues"] = str(a[0] + b[0])
    state["resolved_issues"] = str(a[1] + b[1])


class TestSchemaAndBuild:
    def test_schema_is_v7_without_removed_routing_fields(self):
        fields = {item["field"] for item in get_schema()}
        assert {
            "eval_phase",
            "eval_capability",
            "handling_policy",
            "dimension_status",
        } <= fields
        assert {
            "fix_phase",
            "force_human_resolution",
            "dimension_tokens",
        }.isdisjoint(fields)

    @pytest.mark.parametrize("capability", ["full-remediation", "probe-only"])
    def test_initial_state_requires_explicit_capability(self, capability: str):
        state = _state(capability=capability)
        assert state["version"] == "7"
        assert state["eval_phase"] == "probe"
        assert state["eval_capability"] == capability
        assert parse_dimension_status(state["dimension_status"]) == {
            "a": "pending",
            "b": "pending",
        }
        assert parse_handling_policy(state["handling_policy"]) == {
            "a": "class-default",
            "b": "human-first",
        }
        assert is_v7_state(state)

    def test_capability_and_policy_are_required(self):
        with pytest.raises(TypeError, match="eval_capability"):
            build_initial_evaluate_state(
                dimension_ids=["a"],
                handling_policy={"a": "class-default"},
            )
        with pytest.raises(TypeError, match="handling_policy"):
            build_initial_evaluate_state(
                dimension_ids=["a"],
                eval_capability="probe-only",
            )

    def test_corpus_initializer_pins_normalized_policy_and_capability(self):
        state = build_initial_evaluate_state_for_corpus(
            _corpus(),
            eval_capability="probe-only",
        )
        assert state["eval_capability"] == "probe-only"
        assert parse_handling_policy(state["handling_policy"]) == {
            "a": "class-default",
            "b": "human-first",
        }


class TestValidation:
    @pytest.mark.parametrize(
        ("eval_phase", "eval_status", "dimension_status"),
        [
            ("probe", "active", '{"a":"probing","b":"probed"}'),
            ("remediation", "active", '{"a":"remediating","b":"complete"}'),
            ("done", "done", '{"a":"complete","b":"complete"}'),
        ],
    )
    def test_valid_full_remediation_cross_field_combinations(
        self,
        eval_phase: str,
        eval_status: str,
        dimension_status: str,
    ):
        state = _state()
        state["eval_phase"] = eval_phase
        state["eval_status"] = eval_status
        state["dimension_status"] = dimension_status
        assert validate_evaluate_state(state) == []

    @pytest.mark.parametrize(
        ("capability", "eval_phase", "eval_status", "dimension_status"),
        [
            ("probe-only", "remediation", "active", '{"a":"probed","b":"complete"}'),
            ("probe-only", "done", "abandoned", '{"a":"complete","b":"complete"}'),
            ("full-remediation", "done", "active", '{"a":"complete","b":"complete"}'),
            ("full-remediation", "probe", "done", '{"a":"complete","b":"complete"}'),
            ("full-remediation", "probe", "active", '{"a":"remediating","b":"probed"}'),
            ("full-remediation", "remediation", "active", '{"a":"pending","b":"complete"}'),
            ("full-remediation", "done", "done", '{"a":"probed","b":"complete"}'),
        ],
    )
    def test_invalid_capability_phase_status_dimension_combinations(
        self,
        capability: str,
        eval_phase: str,
        eval_status: str,
        dimension_status: str,
    ):
        state = _state(capability=capability)
        state.update({
            "eval_phase": eval_phase,
            "eval_status": eval_status,
            "dimension_status": dimension_status,
        })
        assert any(
            "inconsistent" in error for error in validate_evaluate_state(state)
        )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("fix_phase", "human-resolution"),
            ("force_human_resolution", '{"a":false,"b":true}'),
            ("dimension_tokens", '{"a":"token"}'),
        ],
    )
    def test_removed_fields_are_rejected(self, field: str, value: str):
        state = _state()
        state[field] = value
        assert any(f"unsupported field: {field!r}" in error for error in validate_evaluate_state(state))

    @pytest.mark.parametrize("version", ["5", "6", "8", None])
    def test_old_or_unknown_versions_are_stably_rejected(self, version: str | None):
        state = _state()
        if version is None:
            del state["version"]
        else:
            state["version"] = version
        assert any("incompatible_round" in error for error in validate_evaluate_state(state))

    def test_old_version_is_rejected_before_business_fields_are_read(self):
        assert validate_evaluate_state({
            "version": "6",
            "dimension_status": "not-json",
        }) == [
            "incompatible_round: evaluate-state version '6' is not supported "
            "(expected '7')",
        ]

    def test_policy_keys_and_values_match_dimensions(self):
        state = _state()
        state["handling_policy"] = '{"a":"class-default"}'
        assert any("keys must match" in error for error in validate_evaluate_state(state))
        state["handling_policy"] = '{"a":"automatic","b":"human-first"}'
        assert any("invalid handling_policy" in error for error in validate_evaluate_state(state))

    @pytest.mark.parametrize("field", ["handling_policy", "issue_counts"])
    def test_all_dimension_maps_have_exact_same_keys(self, field: str):
        state = _state()
        state[field] = (
            '{"a":"class-default"}'
            if field == "handling_policy"
            else '{"a":{"total":0,"resolved":0}}'
        )
        assert any("keys must match" in error for error in validate_evaluate_state(state))

    @pytest.mark.parametrize(
        "issue_counts",
        [
            '{"a":{"total":-1,"resolved":0},"b":{"total":0,"resolved":0}}',
            '{"a":{"total":1,"resolved":2},"b":{"total":0,"resolved":0}}',
            '{"a":{"total":"one","resolved":0},"b":{"total":0,"resolved":0}}',
            '{"a":{"total":1,"resolved":0,"extra":1},"b":{"total":0,"resolved":0}}',
        ],
    )
    def test_issue_counts_are_exact_nonnegative_bounded_integers(
        self,
        issue_counts: str,
    ):
        state = _state()
        state["issue_counts"] = issue_counts
        assert validate_evaluate_state(state)

    def test_aggregate_counts_equal_dimension_sums(self):
        state = _state()
        _set_counts(state, a=(2, 1), b=(3, 2))
        assert validate_evaluate_state(state) == []
        state["total_issues"] = "4"
        state["resolved_issues"] = "4"
        errors = validate_evaluate_state(state)
        assert any("total_issues must equal" in error for error in errors)
        assert any("resolved_issues must equal" in error for error in errors)

    def test_full_remediation_done_requires_every_issue_resolved(self):
        state = _state()
        state.update({
            "eval_phase": "done",
            "eval_status": "done",
            "dimension_status": '{"a":"complete","b":"complete"}',
        })
        _set_counts(state, a=(2, 1), b=(0, 0))
        assert any(
            "full-remediation done requires all issues resolved" in error
            for error in validate_evaluate_state(state)
        )

    def test_probe_only_done_allows_pending_findings(self):
        state = _state(capability="probe-only")
        state.update({
            "eval_phase": "done",
            "eval_status": "done",
            "dimension_status": '{"a":"complete","b":"complete"}',
        })
        _set_counts(state, a=(2, 0), b=(1, 0))
        assert validate_evaluate_state(state) == []

    def test_abandoned_round_is_done_phase_with_unresolved_issues(self):
        state = _state()
        state.update({
            "eval_phase": "done",
            "eval_status": "abandoned",
            "dimension_status": '{"a":"remediating","b":"complete"}',
        })
        _set_counts(state, a=(2, 1), b=(1, 1))
        assert validate_evaluate_state(state) == []


class TestIoAndOrdering:
    def test_save_and_load_v7(self, tmp_path: Path):
        path = tmp_path / "evaluate-state.md"
        save_evaluate_state(path, _state(), merge=False)
        loaded = load_evaluate_state(path)
        assert loaded["version"] == "7"
        assert is_v7_state(loaded)

    @pytest.mark.parametrize("merge", [True, False])
    @pytest.mark.parametrize(
        "existing",
        [
            "---\nversion: 5\neval_status: done\n---\n",
            "---\nversion: 6\neval_status: abandoned\n---\n",
            "---\nversion: 8\n---\n",
            "legacy state without frontmatter\n",
        ],
    )
    def test_save_never_merges_or_overwrites_existing_non_v7_state(
        self,
        tmp_path: Path,
        merge: bool,
        existing: str,
    ):
        path = tmp_path / "evaluate-state.md"
        path.write_text(existing, encoding="utf-8")
        with pytest.raises(ValueError, match="incompatible_round"):
            save_evaluate_state(path, _state(), merge=merge)
        assert path.read_text(encoding="utf-8") == existing

    @pytest.mark.parametrize("legacy_version", ["5", "6"])
    def test_load_rejects_legacy_state_regardless_of_status(
        self,
        tmp_path: Path,
        legacy_version: str,
    ):
        path = tmp_path / "evaluate-state.md"
        path.write_text(
            f"---\nversion: {legacy_version}\neval_status: done\n---\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="incompatible_round"):
            load_evaluate_state(path)

    def test_status_order_supports_probe_and_remediation_progress(self):
        state = _state()
        state["dimension_status"] = '{"a":"probed","b":"complete"}'
        assert all_dims_at_least(state, ["a", "b"], "probed")
        assert not all_dims_at_least(state, ["a", "b"], "remediating")


class TestInitializeStorage:
    def test_initializes_only_empty_storage(self, tmp_path: Path):
        state_path = tmp_path / "eval" / "evaluate-state.md"
        init_evaluate_state_for_corpus(
            state_path,
            _corpus(),
            eval_capability="probe-only",
        )
        assert load_evaluate_state(state_path)["version"] == "7"

    def test_existing_v7_state_is_never_overwritten(self, tmp_path: Path):
        state_path = tmp_path / "eval" / "evaluate-state.md"
        state_path.parent.mkdir()
        original = "---\nversion: 7\nsentinel: keep\n---\n"
        state_path.write_text(original, encoding="utf-8")
        with pytest.raises(ValueError, match="incompatible_storage"):
            init_evaluate_state_for_corpus(
                state_path,
                _corpus(),
                eval_capability="probe-only",
            )
        assert state_path.read_text(encoding="utf-8") == original

    @pytest.mark.parametrize("legacy_version", ["5", "6"])
    def test_existing_legacy_state_is_incompatible_round(
        self,
        tmp_path: Path,
        legacy_version: str,
    ):
        state_path = tmp_path / "eval" / "evaluate-state.md"
        state_path.parent.mkdir()
        original = f"---\nversion: {legacy_version}\neval_status: done\n---\n"
        state_path.write_text(original, encoding="utf-8")
        with pytest.raises(ValueError, match="incompatible_round"):
            init_evaluate_state_for_corpus(
                state_path,
                _corpus(),
                eval_capability="probe-only",
            )
        assert state_path.read_text(encoding="utf-8") == original

    @pytest.mark.parametrize(
        "residue",
        [
            "tech-review-e11.md",
            "operation-records.json",
            "_human-resolution-txn.json",
            "staging/orphan.tmp",
        ],
    )
    def test_orphan_eval_residue_is_incompatible_storage(
        self,
        tmp_path: Path,
        residue: str,
    ):
        storage = tmp_path / "eval"
        residue_path = storage / residue
        residue_path.parent.mkdir(parents=True)
        residue_path.write_text("orphan", encoding="utf-8")
        with pytest.raises(ValueError, match="incompatible_storage"):
            init_evaluate_state_for_corpus(
                storage / "evaluate-state.md",
                _corpus(),
                eval_capability="probe-only",
            )
        assert residue_path.read_text(encoding="utf-8") == "orphan"


class TestLockedPatch:
    def test_v6_is_rejected_before_callback_or_business_field_parse(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        path = tmp_path / "evaluate-state.md"
        original = (
            "---\n"
            "version: 6\n"
            "force_human_resolution: {\"secret\":true}\n"
            "fix_phase: human-resolution\n"
            "---\n"
        )
        path.write_text(original, encoding="utf-8")
        callback_called = False

        def patch_fn(_data):
            nonlocal callback_called
            callback_called = True
            raise AssertionError("legacy business fields reached callback")

        def reject_full_parse(_content):
            raise AssertionError("legacy business fields were parsed")

        monkeypatch.setattr(
            evaluate_state_ops,
            "parse_frontmatter_fields",
            reject_full_parse,
        )
        with pytest.raises(ValueError, match="incompatible_round"):
            locked_patch_evaluate_state(path, patch_fn)
        assert not callback_called
        assert path.read_text(encoding="utf-8") == original

    def test_v7_is_parsed_then_patched(self, tmp_path: Path):
        path = tmp_path / "evaluate-state.md"
        save_evaluate_state(path, _state(), merge=False)
        callback_called = False

        def patch_fn(data):
            nonlocal callback_called
            callback_called = True
            updated = dict(data)
            updated["fix_severity_reason"] = "patched"
            return updated

        updated = locked_patch_evaluate_state(path, patch_fn)
        assert callback_called
        assert updated["fix_severity_reason"] == "patched"
        assert load_evaluate_state(path)["fix_severity_reason"] == "patched"
