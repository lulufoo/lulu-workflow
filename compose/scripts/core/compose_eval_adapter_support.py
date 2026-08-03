"""Compose-owned implementation of generic Eval adapter runtime operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eval_handoff_control import (
    commit_artifacts,
    commit_evaluate_state,
    discard_staging_for_cycle,
    request_handoff,
)
from eval_handoff_schema import (
    build_eval_handoff_v2,
    validate_artifact_manifest_v2,
    validate_eval_handoff_v2,
)


class ComposeEvalAdapterSupport:
    """Mixin that keeps Compose handoff and lease mechanics out of Eval."""

    WORKFLOW_ID = ""

    def _workflow_id(self) -> str:
        workflow_id = str(self.WORKFLOW_ID).strip()
        if not workflow_id:
            raise ValueError("ComposeEvalAdapterSupport.WORKFLOW_ID is required")
        return workflow_id

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

        # Retain Compose-only values solely to translate a later v2 manifest
        # for the existing Compose commit implementation.
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
            policy_context=dict(context["policy_context"]),
        )
        errors = validate_eval_handoff_v2(generic_handoff)
        if errors:
            raise ValueError("; ".join(errors))
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
            "pointer_fingerprint": legacy_context["pointer_fingerprint"],
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
