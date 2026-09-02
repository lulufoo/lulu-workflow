#!/usr/bin/env python3
"""Compose-owned WorkflowAdapter. Stage code contributes Dimensions only."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from workflow_paths import EVAL_SCRIPTS, load_profile, shell_path

# Eval's eval_handoff_schema must win the module name before Compose session
# schema is cached via eval_handoff_control.
if str(EVAL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(EVAL_SCRIPTS))
from eval_path import ensure_eval_script_layers  # noqa: E402

ensure_eval_script_layers()
from eval_handoff_schema import (  # noqa: E402
    build_eval_handoff_v2,
    validate_artifact_manifest_v2,
    validate_eval_handoff_v2,
)

from compose_common_eval import (
    compose_common_dimensions,
    merge_common_and_stage,
    resolve_scope_continuity_sot,
)
from compose_corpus_versions import compose_corpus_id, compose_corpus_ref, compose_corpus_version
from compose_eval_envelope import canonical_profile_digest
from eval_handoff_control import (
    commit_artifacts,
    commit_evaluate_state,
    commit_eval_target,
    discard_staging_for_cycle,
    read_eval_target_digest,
    request_handoff,
    resolve_evaluate_state_abs,
    restore_eval_target,
)
from l_ledger_schema import eval_session_phase, focus_state, l_ledger_path, load_l_ledger
from l_step_control import enter_evaluating_state, rollback_evaluating_phase
from resolved_refs_schema import resolved_refs_path, strict_load_resolved_refs
from session_state_schema import load_active_doc_from_cycle
from stage_eval_contributor import (
    ComposeEvalContext,
    StageEvalContribution,
    validate_contribution,
)
from workflow_common import detect_cycle_type
from workflow_profile_paths import (
    document_path,
    eval_layout_for_revision,
    eval_round_dir_for_layout,
)
from workflow_state_schema import (
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
    save_workflow_state,
)
from corpus_composition import compose_corpus  # noqa: E402
from corpus_schema import expand_corpus  # noqa: E402
from corpus_snapshot import SNAPSHOT_REF  # noqa: E402
from eval_admission import (  # noqa: E402
    EvalAdmissionContext,
    can_abort_admission,
    delete_journal,
    discard_published_snapshot,
    discard_staging,
    file_digest,
    fingerprint_parts,
    load_journal,
    mark_prepared,
    mark_transitioned,
    prepare_snapshot,
    reserve_journal,
)
from workflow_adapter import SessionContext  # noqa: E402

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]


class ComposeEvalAdapter:
    """Outer Eval adapter for every delivery Compose stage."""

    def __init__(
        self,
        *,
        workflow_id: str,
        contributor: Any,
        eval_capability: str = "full-remediation",
        profile_digest: str = "",
    ) -> None:
        workflow = str(workflow_id).strip()
        if not workflow:
            raise ValueError("ComposeEvalAdapter.workflow_id is required")
        if not callable(getattr(contributor, "contribute", None)):
            raise ValueError("contributor must implement contribute()")
        self.WORKFLOW_ID = workflow
        self.EVAL_CAPABILITY = eval_capability
        self._contributor = contributor
        self._profile_digest = str(profile_digest or "")

    @classmethod
    def from_config(cls, envelope: dict[str, Any], *, contributor: Any) -> ComposeEvalAdapter:
        return cls(
            workflow_id=str(envelope.get("workflow_id") or "").strip(),
            contributor=contributor,
            eval_capability=str(envelope.get("eval_capability") or "full-remediation"),
            profile_digest=str(envelope.get("profile_digest") or ""),
        )

    def _workflow_id(self) -> str:
        workflow_id = str(self.WORKFLOW_ID).strip()
        if not workflow_id:
            raise ValueError("ComposeEvalAdapter.workflow_id is required")
        return workflow_id

    def resolve_workflow_state_path(self, cycle_id: str, project_root: Path) -> Path:
        return resolve_workflow_state_path_from_cycle(
            cycle_id,
            project_root,
            profile_id=self._workflow_id(),
        )

    def load_workflow_state(self, cycle_id: str, project_root: Path) -> dict[str, str]:
        return load_workflow_state(self.resolve_workflow_state_path(cycle_id, project_root))

    def save_workflow_state(
        self,
        cycle_id: str,
        project_root: Path,
        updates: dict[str, str],
        *,
        merge: bool = True,
    ) -> None:
        save_workflow_state(
            self.resolve_workflow_state_path(cycle_id, project_root),
            updates,
            merge=merge,
        )

    def resolve_evaluate_state_path(self, cycle_id: str, project_root: Path) -> Path:
        return resolve_evaluate_state_abs(
            cycle_id,
            project_root,
            profile_id=self._workflow_id(),
        )

    def session_context(self, cycle_id: str, project_root: Path) -> SessionContext:
        state = self.load_workflow_state(cycle_id, project_root)
        revision_dir = self.resolve_workflow_state_path(cycle_id, project_root).parent
        try:
            phase = eval_session_phase(revision_dir)
        except (FileNotFoundError, ValueError, OSError):
            phase = "pending"
        contribution = self._contribution(cycle_id, project_root)
        return SessionContext(
            active_doc=load_active_doc_from_cycle(
                cycle_id,
                project_root,
                profile_id=self._workflow_id(),
            ),
            mode=state["mode"],
            upstream_baseline_ref=contribution.upstream_baseline_ref,
            cycle_type=detect_cycle_type(cycle_id),
            focus_phase=phase,
        )

    def eval_paths(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        active_doc: int,
        evaluate_round: int,
        es_path: Path,
    ) -> dict[str, str]:
        root = project_root.resolve()
        workflow_id = self._workflow_id()
        revision_dir = self.resolve_workflow_state_path(cycle_id, project_root).parent
        layout = eval_layout_for_revision(revision_dir)
        focus_l = self._focus_l(revision_dir)
        return {
            "compose_doc": self._compose_doc_path(
                cycle_id, project_root, active_doc=active_doc
            ),
            "evaluate_state": es_path.resolve().as_posix(),
            "evaluate_dir": (
                root
                / eval_round_dir_for_layout(
                    cycle_id,
                    active_doc,
                    evaluate_round,
                    workflow_id,
                    project_root,
                    layout=layout,
                    focus_l=focus_l,
                )
            ).as_posix(),
        }

    def corpus_ref_for_mode(self, mode: str) -> str:
        if mode not in frozenset({"product", "tech"}):
            raise ValueError(f"invalid mode: {mode!r} (allowed: ['product', 'tech'])")
        return compose_corpus_ref(self._workflow_id())

    def resolve_eval_corpus(self, cycle_id: str, project_root: Path) -> dict[str, Any]:
        corpus, _skip_reasons = self._merged_corpus(cycle_id, project_root)
        return corpus

    def dimension_defs_dir(self) -> Path:
        return shell_path(load_profile(self._workflow_id()), "dimension_defs_dir")

    def corpus_bind_extensions(self, cycle_id: str, project_root: Path) -> dict[str, str]:
        return dict(self._contribution(cycle_id, project_root).bindings)

    def detect_cycle_type(self, cycle_id: str) -> str:
        return detect_cycle_type(cycle_id)

    def request_eval_handoff(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        require_evaluating: bool = True,
    ) -> dict[str, Any]:
        result = request_handoff(
            cycle_id,
            project_root,
            profile_id=self._workflow_id(),
            require_evaluating=require_evaluating,
        )
        if not result.get("ok"):
            raise ValueError(str(result.get("error") or "Compose EvalHandoff failed"))
        handoff = result.get("handoff")
        if not isinstance(handoff, dict):
            raise ValueError("Compose EvalHandoff missing")
        context = handoff.get("context")
        if not isinstance(context, dict):
            raise ValueError("Compose EvalHandoff context missing")
        self._legacy_eval_handoff = handoff
        generic_handoff = build_eval_handoff_v2(
            workflow_id=self._workflow_id(),
            cycle_id=str(context["cycle_id"]),
            session_key=str(context["focus_l"]),
            evaluate_round=int(context["evaluate_round"]),
            evaluate_state_path=str(context["evaluate_state_path"]),
            evaluate_dir=str(context["evaluate_dir"]),
            write_staging_dir=str(context["write_staging_dir"]),
            lease_id=str(context["lease_id"]),
            bindings={"eval_target_path": str(context["compose_doc"])},
            policy_context={
                **dict(context["policy_context"]),
                "eval_capability": self.EVAL_CAPABILITY,
            },
        )
        errors = validate_eval_handoff_v2(generic_handoff)
        if errors:
            raise ValueError("; ".join(errors))
        if self._profile_digest:
            profile = load_profile(
                self._workflow_id(),
                project_root=project_root,
                cycle_id=cycle_id,
            )
            actual = canonical_profile_digest(profile)
            if actual != self._profile_digest:
                raise ValueError("profile digest mismatch")
        return generic_handoff

    def commit_eval_artifacts(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        errors = validate_artifact_manifest_v2(manifest)
        if errors:
            return {"ok": False, "error": "; ".join(errors)}
        legacy_handoff = getattr(self, "_legacy_eval_handoff", None)
        legacy_context = (
            legacy_handoff.get("context")
            if isinstance(legacy_handoff, dict)
            else None
        )
        if not isinstance(legacy_context, dict):
            return {"ok": False, "error": "Compose legacy EvalHandoff unavailable"}
        legacy_manifest = {
            "lease_id": manifest["lease_id"],
            "ledger_fingerprint": legacy_context["ledger_fingerprint"],
            "eval_run_id": legacy_context["eval_run_id"],
            "focus_l": legacy_context["focus_l"],
            "evaluate_round": manifest["evaluate_round"],
            "staged_relative_path": manifest["staged_relative_path"],
            "final_relative_path": manifest["final_relative_path"],
            "artifact_digest": manifest["artifact_digest"],
            "state_patch": manifest.get("state_patch", {}),
        }
        return commit_artifacts(
            cycle_id,
            project_root,
            profile_id=self._workflow_id(),
            manifest=legacy_manifest,
        )

    def commit_evaluate_state(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        staged_state_path: Path,
        set_phase_evaluating: bool = False,
        previous_done_required: bool = False,
    ) -> dict[str, Any]:
        return commit_evaluate_state(
            cycle_id,
            project_root,
            profile_id=self._workflow_id(),
            staged_state_path=staged_state_path,
            set_phase_evaluating=set_phase_evaluating,
            previous_done_required=previous_done_required,
        )

    def read_eval_target_digest(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        target_path: Path,
    ) -> str:
        del cycle_id, project_root
        return read_eval_target_digest(target_path=target_path)

    def commit_eval_target(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        staged_target_path: Path,
        base_digest: str,
        lease_id: str,
    ) -> dict[str, Any]:
        return commit_eval_target(
            cycle_id,
            project_root,
            profile_id=self._workflow_id(),
            staged_target_path=staged_target_path,
            base_digest=base_digest,
            lease_id=lease_id,
        )

    def restore_eval_target(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        snapshot_path: Path,
        expected_current_digest: str,
        lease_id: str,
    ) -> dict[str, Any]:
        return restore_eval_target(
            cycle_id,
            project_root,
            profile_id=self._workflow_id(),
            snapshot_path=snapshot_path,
            expected_current_digest=expected_current_digest,
            lease_id=lease_id,
        )

    def discard_eval_staging(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        lease_id: str,
    ) -> dict[str, Any]:
        return discard_staging_for_cycle(
            cycle_id,
            project_root,
            profile_id=self._workflow_id(),
            lease_id=lease_id,
        )

    def eval_admission_context(
        self, cycle_id: str, project_root: Path
    ) -> EvalAdmissionContext:
        revision_dir = self.resolve_workflow_state_path(cycle_id, project_root).parent
        focus_l = self._focus_l(revision_dir)
        slice_dir = revision_dir / focus_l
        target = Path(
            self._compose_doc_path(
                cycle_id,
                project_root,
                active_doc=load_active_doc_from_cycle(
                    cycle_id,
                    project_root,
                    profile_id=self._workflow_id(),
                ),
            )
        )
        if not target.is_file():
            raise ValueError(f"compose eval target missing: {target}")
        cell = focus_state(load_l_ledger(revision_dir))
        previous = cell if cell in {"Writing", "FreeEdit"} else "Evaluating"
        return EvalAdmissionContext(
            admission_root=slice_dir,
            session_key=focus_l,
            provider_state_fingerprint=self._provider_fingerprint(revision_dir),
            previous_phase=previous,
            target_path=target,
            target_digest=file_digest(target),
            candidate_round=self._candidate_round(slice_dir),
        )

    def prepare_eval_admission(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, Any]:
        ctx = self.eval_admission_context(cycle_id, project_root)
        journal = reserve_journal(ctx)
        token = str(journal["token"])
        try:
            corpus, skip_reasons = self._expanded_admission_corpus(
                cycle_id, project_root, ctx
            )
            manifest = prepare_snapshot(
                ctx,
                token=token,
                corpus=corpus,
                method_roots=self._method_roots(project_root),
                method_must_stay_under=_WORKFLOW_ROOT,
                sot_roots=[project_root.resolve()],
            )
            mark_prepared(
                ctx,
                token=token,
                snapshot_digest=str(manifest["corpus_digest"]),
                skip_reasons=skip_reasons,
            )
        except Exception:
            discard_staging(ctx.admission_root, token)
            if str(journal.get("status")) == "preparing":
                delete_journal(ctx.admission_root)
            raise
        evaluate_dir = (
            project_root.resolve()
            / eval_round_dir_for_layout(
                cycle_id,
                load_active_doc_from_cycle(
                    cycle_id, project_root, profile_id=self._workflow_id()
                ),
                ctx.candidate_round,
                self._workflow_id(),
                project_root,
                layout=eval_layout_for_revision(
                    self.resolve_workflow_state_path(cycle_id, project_root).parent
                ),
                focus_l=ctx.session_key,
            )
        )
        return {
            "ok": True,
            "token": token,
            "corpus": corpus,
            "skip_reasons": skip_reasons,
            "snapshot_digest": str(manifest["corpus_digest"]),
            "snapshot_ref": SNAPSHOT_REF,
            "evaluate_dir": evaluate_dir.as_posix(),
            "context": ctx,
        }

    def abort_eval_admission(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        token: str,
    ) -> dict[str, Any]:
        ctx = self.eval_admission_context(cycle_id, project_root)
        journal = load_journal(ctx.admission_root)
        if journal is None:
            return {"ok": True, "aborted": False}
        evaluate_dir = Path(self.eval_paths(
            cycle_id,
            project_root,
            active_doc=load_active_doc_from_cycle(
                cycle_id, project_root, profile_id=self._workflow_id()
            ),
            evaluate_round=int(journal.get("candidate_round") or ctx.candidate_round),
            es_path=self.resolve_evaluate_state_path(cycle_id, project_root),
        )["evaluate_dir"])
        if not can_abort_admission(
            journal=journal,
            token=token,
            evaluate_state_path=self.resolve_evaluate_state_path(cycle_id, project_root),
            operations_path=evaluate_dir / "eval-operations.json",
        ):
            return {"ok": False, "error": "admission abort refused"}
        discard_published_snapshot(evaluate_dir)
        revision_dir = self.resolve_workflow_state_path(cycle_id, project_root).parent
        rollback_evaluating_phase(
            revision_dir,
            focus=ctx.session_key,
            previous_phase=str(journal.get("previous_phase") or ""),
        )
        lease_id = str(journal.get("lease_id") or "")
        if lease_id:
            discard_staging_for_cycle(
                cycle_id,
                project_root,
                profile_id=self._workflow_id(),
                lease_id=lease_id,
            )
        discard_staging(ctx.admission_root, token)
        delete_journal(ctx.admission_root)
        return {"ok": True, "aborted": True}

    def enter_evaluating(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        admission_token: str | None = None,
    ) -> dict[str, Any]:
        result = enter_evaluating_state(
            cycle_id,
            project_root,
            profile_id=self._workflow_id(),
        )
        if result.get("ok") and admission_token:
            revision_dir = self.resolve_workflow_state_path(cycle_id, project_root).parent
            mark_transitioned(
                revision_dir / self._focus_l(revision_dir),
                token=admission_token,
                provider_state_fingerprint=self._provider_fingerprint(revision_dir),
            )
        return result

    def _provider_fingerprint(self, revision_dir: Path) -> str:
        parts = [self._profile_digest]
        for path in (l_ledger_path(revision_dir), resolved_refs_path(revision_dir)):
            if path.is_file():
                parts.append(file_digest(path))
        return fingerprint_parts(*parts)

    def _candidate_round(self, slice_dir: Path) -> int:
        es_path = slice_dir / "evaluate-state.md"
        if not es_path.is_file():
            return 1
        status = ""
        current = 1
        for line in es_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("eval_status:"):
                status = line.split(":", 1)[1].strip()
            if line.startswith("evaluate_round:"):
                try:
                    current = int(line.split(":", 1)[1].strip())
                except ValueError:
                    current = 1
        if status in {"done", "abandoned"}:
            return current + 1
        return current if current >= 1 else 1

    def _method_roots(self, project_root: Path) -> list[Path]:
        del project_root
        # Refs are either workflow-relative or repo-relative (`lulu-dev-workflow/...`).
        return [_WORKFLOW_ROOT, _WORKFLOW_ROOT.parent]

    def _expanded_admission_corpus(
        self,
        cycle_id: str,
        project_root: Path,
        ctx: EvalAdmissionContext,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        corpus, skip_reasons = self._merged_corpus(cycle_id, project_root)
        bind = {
            "eval_target_path": ctx.target_path.resolve().as_posix(),
            "upstream_baseline_ref": self._contribution(
                cycle_id, project_root
            ).upstream_baseline_ref,
            "cycle_type": detect_cycle_type(cycle_id),
            "M": str(ctx.candidate_round),
        }
        bind.update(self.corpus_bind_extensions(cycle_id, project_root))
        return expand_corpus(corpus, bind), skip_reasons

    def _merged_corpus(
        self, cycle_id: str, project_root: Path
    ) -> tuple[dict[str, Any], dict[str, str]]:
        contribution = self._contribution(cycle_id, project_root)
        ctx = self._eval_context(cycle_id, project_root)
        refs = strict_load_resolved_refs(
            ctx.revision_dir,
            expected_cycle_id=cycle_id,
            expected_stage=self._workflow_id(),
        )
        parent = resolve_scope_continuity_sot(
            ctx.revision_dir,
            focus_l=ctx.focus_l,
            project_root=project_root,
            scope_ref=refs.scope_ref,
        )
        common, skip_reasons = compose_common_dimensions(
            refs,
            parent_sot=parent,
            project_root=project_root,
        )
        dimensions = merge_common_and_stage(common, contribution.dimensions)
        workflow_id = self._workflow_id()
        return (
            compose_corpus(
                corpus_id=compose_corpus_id(workflow_id),
                corpus_version=compose_corpus_version(workflow_id),
                scope=workflow_id,
                dimensions=dimensions,
                review_output_prefix=contribution.review_output_prefix,
            ),
            skip_reasons,
        )

    def _focus_l(self, revision_dir: Path) -> str:
        try:
            return str(load_l_ledger(revision_dir)["focus"])
        except (FileNotFoundError, ValueError, OSError, KeyError):
            return "L1"

    def _compose_doc_path(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        active_doc: int,
    ) -> str:
        root = project_root.resolve()
        workflow_id = self._workflow_id()
        try:
            return (
                root / document_path(cycle_id, active_doc, workflow_id, project_root)
            ).as_posix()
        except (FileNotFoundError, ValueError, OSError, KeyError):
            from workflow_profile_paths import doc_dir  # noqa: WPS433

            profile = load_profile(
                workflow_id, project_root=project_root, cycle_id=cycle_id
            )
            filename = str(profile["document"]["filename"])
            return (root / doc_dir(cycle_id, active_doc, workflow_id, project_root) / filename).as_posix()

    def _eval_context(self, cycle_id: str, project_root: Path) -> ComposeEvalContext:
        cycle_type = detect_cycle_type(cycle_id)
        mode = "tech"
        revision_dir = project_root
        focus_l = "L1"
        try:
            ws_path = self.resolve_workflow_state_path(cycle_id, project_root)
            revision_dir = ws_path.parent
            state = load_workflow_state(ws_path)
            mode = state.get("mode", "tech")
            focus_l = self._focus_l(revision_dir)
        except (FileNotFoundError, ValueError, OSError):
            pass
        return ComposeEvalContext(
            cycle_id=cycle_id,
            project_root=project_root,
            workflow_id=self._workflow_id(),
            revision_dir=revision_dir,
            cycle_type=cycle_type,
            mode=mode,
            dimension_defs_dir=self.dimension_defs_dir(),
            focus_l=focus_l,
        )

    def _contribution(self, cycle_id: str, project_root: Path) -> StageEvalContribution:
        raw = self._contributor.contribute(context=self._eval_context(cycle_id, project_root))
        return validate_contribution(raw)
