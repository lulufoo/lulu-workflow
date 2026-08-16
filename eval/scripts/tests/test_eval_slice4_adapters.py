#!/usr/bin/env python3
"""Slice 4: Dimension defs, adapter capability, and EvalTarget protocol."""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

_EVAL_SCRIPTS = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _EVAL_SCRIPTS.parents[1]
sys.path.insert(0, str(_EVAL_SCRIPTS))

import eval_adapter_config as eac
import eval_entry
from corpus_compose import compose_corpus, load_dimension_def
from corpus_schema import normalize_corpus, validate_corpus


_DIMENSION_DEFS = sorted(_WORKFLOW_ROOT.glob("**/dimension-defs/*.json"))
_HUMAN_FIRST_DEF = (
    _WORKFLOW_ROOT / "lulu-design" / "dimension-defs" / "intent-alignment.json"
)
_FULL_REMEDIATION_PROFILES = (
    _WORKFLOW_ROOT / "lulu-plan" / "compose-profile.json",
    _WORKFLOW_ROOT / "lulu-design" / "compose-profile.json",
    _WORKFLOW_ROOT / "lulu-arch" / "compose-profile.json",
    _WORKFLOW_ROOT / "lulu-blueprint" / "compose-profile.json",
    _WORKFLOW_ROOT / "lulu-spec" / "compose-profile.json",
    (
        _WORKFLOW_ROOT
        / "compose"
        / "fact-intake-runner"
        / "fact-intake-eval"
        / "eval-profile.json"
    ),
)
_DECISION_PROFILE = _WORKFLOW_ROOT / "decision" / "eval" / "eval-profile.json"
_REMOVED_FIELDS = ("force_human_resolution", "remediation_target")
_READ = "read_eval_target_digest"
_COMMIT = "commit_eval_target"
_RESTORE = "restore_eval_target"
_OLD_PRIMITIVES = ("commit_remediation_target", "restore_remediation_target")


def _eval_block(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("eval", payload)


def _valid_config(**overrides) -> dict:
    payload = {
        "workflow_id": "non-compose",
        "adapter_module": "unused.py",
        "adapter_class": "Unused",
        "eval_capability": "full-remediation",
    }
    payload.update(overrides)
    return payload


class TestDimensionDefinitions:
    def test_finds_exactly_twelve_dimension_definitions(self) -> None:
        assert len(_DIMENSION_DEFS) == 12

    def test_all_definitions_pass_corpus_schema_v6(self) -> None:
        for path in _DIMENSION_DEFS:
            composed = compose_corpus(
                corpus_id="slice4-one-def",
                corpus_version="2",
                scope="slice4",
                dimensions=[load_dimension_def(path)],
            )
            assert validate_corpus(composed) == [], path
            normalized = normalize_corpus(composed)
            assert normalized["dimensions"][0]["handling_policy"] in {
                "class-default",
                "human-first",
            }

    def test_only_intent_alignment_declares_human_first(self) -> None:
        human_first = []
        for path in _DIMENSION_DEFS:
            definition = load_dimension_def(path)
            if definition.get("handling_policy") == "human-first":
                human_first.append(path)
        assert human_first == [_HUMAN_FIRST_DEF]

    @pytest.mark.parametrize("field", _REMOVED_FIELDS)
    def test_definitions_do_not_declare_removed_fields(self, field: str) -> None:
        leftovers = [
            path.as_posix()
            for path in _DIMENSION_DEFS
            if field in load_dimension_def(path)
        ]
        assert leftovers == []


class TestAdapterProfiles:
    def test_seven_families_declare_eval_capability(self) -> None:
        profiles = [*_FULL_REMEDIATION_PROFILES, _DECISION_PROFILE]
        assert len(profiles) == 7
        for path in profiles:
            assert _eval_block(path)["eval_capability"] in {
                "full-remediation",
                "probe-only",
            }

    def test_compose_and_fact_intake_are_full_remediation(self) -> None:
        for path in _FULL_REMEDIATION_PROFILES:
            assert _eval_block(path)["eval_capability"] == "full-remediation"

    def test_decision_is_probe_only(self) -> None:
        assert _eval_block(_DECISION_PROFILE)["eval_capability"] == "probe-only"


class TestAdapterConfigCapability:
    def test_requires_eval_capability(self) -> None:
        payload = _valid_config()
        del payload["eval_capability"]
        with pytest.raises(ValueError, match="eval_capability"):
            eac.validate_adapter_config(payload)

    def test_rejects_unknown_eval_capability(self) -> None:
        with pytest.raises(ValueError, match="eval_capability"):
            eac.validate_adapter_config(_valid_config(eval_capability="guess"))

    def test_stores_validated_eval_capability(self) -> None:
        config = eac.validate_adapter_config(
            _valid_config(eval_capability="probe-only"),
        )
        assert config.eval_capability == "probe-only"


class TestEntryProtocol:
    def test_full_remediation_requires_read_commit_restore(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        class ReadOnlyAdapter:
            def request_eval_handoff(self, **kwargs):
                del kwargs
                return {
                    "version": 2,
                    "context": {
                        "policy_context": {"eval_capability": "full-remediation"},
                    },
                }

            def read_eval_target_digest(self, *args, **kwargs):
                return "digest"

        captured: dict[str, object] = {}
        monkeypatch.setattr(
            eval_entry,
            "load_adapter_config_file",
            lambda path: eac.validate_adapter_config(_valid_config()),
        )
        monkeypatch.setattr(
            eval_entry,
            "load_eval_adapter_from_config",
            lambda config: ReadOnlyAdapter(),
        )
        monkeypatch.setattr(
            eval_entry,
            "run_eval",
            lambda *args, **kwargs: captured.setdefault("ran", True) or 0,
        )
        code = eval_entry.main(
            [
                "--adapter-config-file",
                str(tmp_path / "cfg.json"),
                "--cycle-id",
                "C1",
                "--project-root",
                str(tmp_path),
                "begin-eval-round",
            ]
        )
        assert code == 1
        assert "ran" not in captured

    def test_probe_only_does_not_require_commit_or_restore(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        class ProbeOnlyAdapter:
            def request_eval_handoff(self, **kwargs):
                del kwargs
                return {
                    "version": 2,
                    "context": {
                        "policy_context": {"eval_capability": "probe-only"},
                    },
                }

            def read_eval_target_digest(self, *args, **kwargs):
                return "digest"

        captured: dict[str, object] = {}

        def fake_run_eval(parsed_args, adapter, *, handoff):
            captured["adapter"] = adapter
            captured["handoff"] = handoff
            return 0

        monkeypatch.setattr(
            eval_entry,
            "load_adapter_config_file",
            lambda path: eac.validate_adapter_config(
                _valid_config(eval_capability="probe-only"),
            ),
        )
        monkeypatch.setattr(
            eval_entry,
            "load_eval_adapter_from_config",
            lambda config: ProbeOnlyAdapter(),
        )
        monkeypatch.setattr(eval_entry, "run_eval", fake_run_eval)
        code = eval_entry.main(
            [
                "--adapter-config-file",
                str(tmp_path / "cfg.json"),
                "--cycle-id",
                "C1",
                "--project-root",
                str(tmp_path),
                "begin-eval-round",
            ]
        )
        assert code == 0
        assert captured["adapter"].__class__.__name__ == "ProbeOnlyAdapter"

    def test_capability_mismatch_between_config_and_handoff_is_rejected(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        class ProbeOnlyAdapter:
            def request_eval_handoff(self, **kwargs):
                del kwargs
                return {
                    "version": 2,
                    "context": {
                        "policy_context": {"eval_capability": "probe-only"},
                    },
                }

            def read_eval_target_digest(self, *args, **kwargs):
                return "digest"

            def commit_eval_target(self, *args, **kwargs):
                return {"ok": True}

            def restore_eval_target(self, *args, **kwargs):
                return {"ok": True}

        captured: dict[str, object] = {}
        monkeypatch.setattr(
            eval_entry,
            "load_adapter_config_file",
            lambda path: eac.validate_adapter_config(_valid_config()),
        )
        monkeypatch.setattr(
            eval_entry,
            "load_eval_adapter_from_config",
            lambda config: ProbeOnlyAdapter(),
        )
        monkeypatch.setattr(
            eval_entry,
            "run_eval",
            lambda *args, **kwargs: captured.setdefault("ran", True) or 0,
        )
        code = eval_entry.main(
            [
                "--adapter-config-file",
                str(tmp_path / "cfg.json"),
                "--cycle-id",
                "C1",
                "--project-root",
                str(tmp_path),
                "begin-eval-round",
            ]
        )
        assert code == 1
        assert "ran" not in captured

    def test_capability_mismatch_with_evaluate_state_is_rejected(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        state_path = tmp_path / "evaluate-state.md"
        state_path.write_text(
            "---\nversion: 7\neval_capability: probe-only\n---\n",
            encoding="utf-8",
        )

        class FullAdapter:
            def request_eval_handoff(self, **kwargs):
                del kwargs
                return {
                    "version": 2,
                    "context": {
                        "evaluate_state_path": str(state_path),
                        "policy_context": {"eval_capability": "full-remediation"},
                    },
                }

            def read_eval_target_digest(self, *args, **kwargs):
                return "digest"

            def commit_eval_target(self, *args, **kwargs):
                return {"ok": True}

            def restore_eval_target(self, *args, **kwargs):
                return {"ok": True}

        captured: dict[str, object] = {}
        monkeypatch.setattr(
            eval_entry,
            "load_adapter_config_file",
            lambda path: eac.validate_adapter_config(_valid_config()),
        )
        monkeypatch.setattr(
            eval_entry,
            "load_eval_adapter_from_config",
            lambda config: FullAdapter(),
        )
        monkeypatch.setattr(
            eval_entry,
            "run_eval",
            lambda *args, **kwargs: captured.setdefault("ran", True) or 0,
        )
        code = eval_entry.main(
            [
                "--adapter-config-file",
                str(tmp_path / "cfg.json"),
                "--cycle-id",
                "C1",
                "--project-root",
                str(tmp_path),
                "begin-eval-round",
            ]
        )
        assert code == 1
        assert "ran" not in captured

    def test_existing_evaluate_state_without_capability_is_rejected(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        state_path = tmp_path / "evaluate-state.md"
        state_path.write_text("---\nversion: 7\n---\n", encoding="utf-8")

        class FullAdapter:
            def request_eval_handoff(self, **kwargs):
                del kwargs
                return {
                    "version": 2,
                    "context": {
                        "evaluate_state_path": str(state_path),
                        "policy_context": {"eval_capability": "full-remediation"},
                    },
                }

            def read_eval_target_digest(self, *args, **kwargs):
                return "digest"

            def commit_eval_target(self, *args, **kwargs):
                return {"ok": True}

            def restore_eval_target(self, *args, **kwargs):
                return {"ok": True}

        captured: dict[str, object] = {}
        monkeypatch.setattr(
            eval_entry,
            "load_adapter_config_file",
            lambda path: eac.validate_adapter_config(_valid_config()),
        )
        monkeypatch.setattr(
            eval_entry,
            "load_eval_adapter_from_config",
            lambda config: FullAdapter(),
        )
        monkeypatch.setattr(
            eval_entry,
            "run_eval",
            lambda *args, **kwargs: captured.setdefault("ran", True) or 0,
        )
        code = eval_entry.main(
            [
                "--adapter-config-file",
                str(tmp_path / "cfg.json"),
                "--cycle-id",
                "C1",
                "--project-root",
                str(tmp_path),
                "begin-eval-round",
            ]
        )
        assert code == 1
        assert "ran" not in captured

    def test_existing_evaluate_state_with_invalid_capability_is_rejected(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        state_path = tmp_path / "evaluate-state.md"
        state_path.write_text(
            "---\nversion: 7\neval_capability: unchecked\n---\n",
            encoding="utf-8",
        )

        class FullAdapter:
            def request_eval_handoff(self, **kwargs):
                del kwargs
                return {
                    "version": 2,
                    "context": {
                        "evaluate_state_path": str(state_path),
                        "policy_context": {"eval_capability": "full-remediation"},
                    },
                }

            def read_eval_target_digest(self, *args, **kwargs):
                return "digest"

            def commit_eval_target(self, *args, **kwargs):
                return {"ok": True}

            def restore_eval_target(self, *args, **kwargs):
                return {"ok": True}

        captured: dict[str, object] = {}
        monkeypatch.setattr(
            eval_entry,
            "load_adapter_config_file",
            lambda path: eac.validate_adapter_config(_valid_config()),
        )
        monkeypatch.setattr(
            eval_entry,
            "load_eval_adapter_from_config",
            lambda config: FullAdapter(),
        )
        monkeypatch.setattr(
            eval_entry,
            "run_eval",
            lambda *args, **kwargs: captured.setdefault("ran", True) or 0,
        )
        code = eval_entry.main(
            [
                "--adapter-config-file",
                str(tmp_path / "cfg.json"),
                "--cycle-id",
                "C1",
                "--project-root",
                str(tmp_path),
                "begin-eval-round",
            ]
        )
        assert code == 1
        assert "ran" not in captured

    def test_absent_evaluate_state_file_skips_state_capability_check(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        class FullAdapter:
            def request_eval_handoff(self, **kwargs):
                del kwargs
                return {
                    "version": 2,
                    "context": {
                        "evaluate_state_path": str(tmp_path / "missing-state.md"),
                        "policy_context": {"eval_capability": "full-remediation"},
                    },
                }

            def read_eval_target_digest(self, *args, **kwargs):
                return "digest"

            def commit_eval_target(self, *args, **kwargs):
                return {"ok": True}

            def restore_eval_target(self, *args, **kwargs):
                return {"ok": True}

        captured: dict[str, object] = {}

        def fake_run_eval(*args, **kwargs):
            captured["ran"] = True
            return 0

        monkeypatch.setattr(
            eval_entry,
            "load_adapter_config_file",
            lambda path: eac.validate_adapter_config(_valid_config()),
        )
        monkeypatch.setattr(
            eval_entry,
            "load_eval_adapter_from_config",
            lambda config: FullAdapter(),
        )
        monkeypatch.setattr(eval_entry, "run_eval", fake_run_eval)
        code = eval_entry.main(
            [
                "--adapter-config-file",
                str(tmp_path / "cfg.json"),
                "--cycle-id",
                "C1",
                "--project-root",
                str(tmp_path),
                "begin-eval-round",
            ]
        )
        assert code == 0
        assert captured.get("ran") is True


class TestEvaluateStateCapabilityFailClosed:
    def _full_adapter(self):
        class FullAdapter:
            def read_eval_target_digest(self, *args, **kwargs):
                return "digest"

            def commit_eval_target(self, *args, **kwargs):
                return {"ok": True}

            def restore_eval_target(self, *args, **kwargs):
                return {"ok": True}

        return FullAdapter()

    def _handoff(self, state_path: Path) -> dict:
        return {
            "version": 2,
            "context": {
                "evaluate_state_path": str(state_path),
                "policy_context": {"eval_capability": "full-remediation"},
            },
        }

    def test_validate_rejects_present_state_missing_capability(
        self,
        tmp_path: Path,
    ) -> None:
        state_path = tmp_path / "evaluate-state.md"
        state_path.write_text("---\nversion: 7\n---\n", encoding="utf-8")
        with pytest.raises(ValueError, match="eval_capability"):
            eac.validate_adapter_protocol(
                self._full_adapter(),
                eval_capability="full-remediation",
                handoff=self._handoff(state_path),
            )

    def test_validate_rejects_present_state_invalid_capability(
        self,
        tmp_path: Path,
    ) -> None:
        state_path = tmp_path / "evaluate-state.md"
        state_path.write_text(
            "---\nversion: 7\neval_capability: unchecked\n---\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="eval_capability"):
            eac.validate_adapter_protocol(
                self._full_adapter(),
                eval_capability="full-remediation",
                handoff=self._handoff(state_path),
            )

    def test_validate_allows_absent_state_file(self, tmp_path: Path) -> None:
        eac.validate_adapter_protocol(
            self._full_adapter(),
            eval_capability="full-remediation",
            handoff=self._handoff(tmp_path / "missing-state.md"),
        )


class TestSharedInitializerAndPrimitives:
    def test_decision_and_fact_intake_do_not_keep_local_init(self) -> None:
        decision = (
            _WORKFLOW_ROOT / "decision" / "scripts" / "eval" / "decision_eval_adapter.py"
        ).read_text(encoding="utf-8")
        fact_intake = (
            _WORKFLOW_ROOT
            / "compose"
            / "fact-intake-runner"
            / "fact-intake-eval"
            / "scripts"
            / "fact_intake_eval_adapter.py"
        ).read_text(encoding="utf-8")
        assert "def _init_evaluate_state(" not in decision
        assert "def _init_evaluate_state(" not in fact_intake
        assert "init_evaluate_state_for_corpus" in decision
        assert "init_evaluate_state_for_corpus" in fact_intake

    def test_decision_does_not_write_evaluate_state_in_finalize(self) -> None:
        source = (
            _WORKFLOW_ROOT / "decision" / "scripts" / "eval" / "decision_eval_adapter.py"
        ).read_text(encoding="utf-8")
        finalize = source.split("def finalize_eval_outcome", 1)[1]
        assert "save_evaluate_state" not in finalize
        assert "load_evaluate_state" not in finalize

    def test_compose_support_exposes_renamed_target_primitives(self) -> None:
        sys.path.insert(0, str(_WORKFLOW_ROOT / "compose" / "scripts" / "core"))
        from compose_eval_adapter_support import ComposeEvalAdapterSupport

        for name in (_READ, _COMMIT, _RESTORE):
            assert hasattr(ComposeEvalAdapterSupport, name)
        for name in _OLD_PRIMITIVES:
            assert not hasattr(ComposeEvalAdapterSupport, name)

    def test_decision_is_read_only_and_does_not_fake_mutation(self) -> None:
        sys.path.insert(0, str(_WORKFLOW_ROOT / "decision" / "scripts" / "eval"))
        from decision_eval_adapter import DecisionEvalAdapter

        assert hasattr(DecisionEvalAdapter, _READ)
        assert not hasattr(DecisionEvalAdapter, _COMMIT)
        assert not hasattr(DecisionEvalAdapter, _RESTORE)

    def test_fact_intake_exposes_renamed_target_primitives(self) -> None:
        sys.path.insert(
            0,
            str(
                _WORKFLOW_ROOT
                / "compose"
                / "fact-intake-runner"
                / "fact-intake-eval"
                / "scripts"
            ),
        )
        from fact_intake_eval_adapter import FactIntakeEvalAdapter

        for name in (_READ, _COMMIT, _RESTORE):
            assert hasattr(FactIntakeEvalAdapter, name)
        for name in _OLD_PRIMITIVES:
            assert not hasattr(FactIntakeEvalAdapter, name)

    def test_workflow_adapter_protocol_uses_renamed_primitives(self) -> None:
        import workflow_adapter

        base = inspect.getsource(workflow_adapter.WorkflowAdapter)
        full = inspect.getsource(workflow_adapter.FullRemediationAdapter)
        assert f"def {_READ}" in base
        assert f"def {_COMMIT}" not in base
        assert f"def {_RESTORE}" not in base
        assert f"def {_COMMIT}" in full
        assert f"def {_RESTORE}" in full
        for name in _OLD_PRIMITIVES:
            assert name not in base
            assert name not in full

    def test_decision_satisfies_read_protocol_without_mutation_methods(self) -> None:
        import workflow_adapter

        sys.path.insert(0, str(_WORKFLOW_ROOT / "decision" / "scripts" / "eval"))
        from decision_eval_adapter import DecisionEvalAdapter

        def public_methods(cls: type) -> set[str]:
            return {
                name
                for name, value in inspect.getmembers(cls, predicate=inspect.isfunction)
                if not name.startswith("_")
            }

        required = public_methods(workflow_adapter.WorkflowAdapter)
        mutation = public_methods(workflow_adapter.FullRemediationAdapter) & {
            _COMMIT,
            _RESTORE,
        }
        implemented = public_methods(DecisionEvalAdapter)
        assert _READ in required
        assert _COMMIT not in required
        assert _RESTORE not in required
        assert mutation == {_COMMIT, _RESTORE}
        assert required <= implemented
        assert implemented.isdisjoint(mutation)


class TestCallerCommands:
    def test_decision_routes_complete_probe_only(self) -> None:
        control = (
            _WORKFLOW_ROOT / "decision" / "scripts" / "dec_eval_control.py"
        ).read_text(encoding="utf-8")
        skill = (
            _WORKFLOW_ROOT / "decision" / "runners" / "dc-delivery-runner" / "SKILL.md"
        ).read_text(encoding="utf-8")
        assert "complete-probe-only" in control
        assert "complete-probe-only" in skill
        assert "probe-complete" not in control
        assert "probe-complete" not in skill

    def test_compose_passthrough_uses_remediation_complete(self) -> None:
        source = (
            _WORKFLOW_ROOT / "compose" / "scripts" / "tests" / "test_compose_eval_control.py"
        ).read_text(encoding="utf-8")
        assert "remediation-complete" in source
        assert "complete-round" not in source
