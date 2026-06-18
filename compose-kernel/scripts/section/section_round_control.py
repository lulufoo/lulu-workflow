#!/usr/bin/env python3
"""Section-gated Round Iteration control for compose orchestrators (tech-plan, tech-design, …).

Subcommands:
    read-context           Return anchors, skips, round metadata
    append-anchor          Append anchor ledger entry
    append-skip            Append skip ledger entry
    update-anchor-status   Set anchor ledger entry status (passing | failing)
    check-convergence      Evaluate convergence conditions
    round-probe-input      Gate Probe entry; print prober-runner ## Input block (plain text)
    init-round-dir         Create round-{N}/ and section-pointer.json
    read-section-pointer   Return section pointer for current round
    read-upstream-context  Return stable upstream edges for active section
    read-section-body      Return compose document section body by section key
    advance-section        Mark active stable and activate next section
    rewind-section         Rewind to section and invalidate downstream
    mark-section-stable      Mark one section stable (no advance)
    write-probe-report     Write round-{N}/{section}/probe-{seq}.json
    read-probe-report      Return latest probe report for a section
    write-refiner-artifact   Write round-{N}/{section}/refiner-{seq}-{id}.json
    read-gap-report        Return probe report for active section (pointer required)
    read-gap-item          Return one gap item + refiner dispatch fields
    update-gap-decision    Set gap item decision (accept | skip | redirect)
    update-gap-status      Set gap item status (open | no_gap | resolved)

Does not write drafting-progress.md — use draft_control.py for progress transitions.

Global option ``--round`` applies to round-scoped subcommands (place before subcommand name).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from compose_profile_context import get_active_profile, set_active_profile  # noqa: E402
from compose_session import workflow_state_path  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, KERNEL_TEMPLATES, load_profile  # noqa: E402
from probe_report_schema import (  # noqa: E402
    find_item,
    intent_open_items,
    intent_undecided_items,
    kw0_pending_items,
    load_probe_report,
    normalize_probe_report,
    open_items,
    refiner_payload as probe_refiner_payload,
    save_probe_report,
    undecided_items,
    update_probe_item_decision,
    update_probe_item_status,
    upstream_open_items,
    upstream_undecided_items,
)
from section_dependency_schema import (  # noqa: E402
    load_dependency_graph,
    stable_upstream_edges,
    upstream_edges,
)
from refiner_artifact_schema import (  # noqa: E402
    next_refiner_seq,
    refiner_artifact_path,
    save_refiner_artifact,
)
from section_pointer_schema import (  # noqa: E402
    advance_section,
    all_sections_stable,
    init_section_pointer,
    load_section_pointer,
    mark_section_stable,
    next_probe_seq,
    probe_report_path,
    rewind_section,
    round_directory,
    save_section_pointer,
    section_pointer_path,
    update_latest_probe,
)
from session_state_schema import load_active_doc  # noqa: E402
from section_registry_schema import (  # noqa: E402
    normalize_section as _normalize_section_impl,
    project_root_from_cycle_dir,
    section_heading,
)
from compose_doc_schema import section_body_by_key, section_display_heading  # noqa: E402
from workflow_common import parse_frontmatter_fields  # noqa: E402
from delivered_refs_schema import (  # noqa: E402
    delivered_path,
    init_scope_ref_from_state,
    parse_delivered_refs,
)
from workflow_state_schema import load_workflow_state  # noqa: E402

_CMD_ROUND_PROBE_INPUT = "round-probe-input"
_STEP_ROUND = "RoundIteration"


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _normalize_section(raw: str) -> str:
    return _normalize_section_impl(raw)


def _fail(message: str, code: int = 1) -> int:
    print(message, file=sys.stderr)
    return code


def _compose_base(cycle_dir: Path) -> Path:
    profile = load_profile(get_active_profile())
    return cycle_dir / profile["cache_subdir"]


def _document_filename() -> str:
    return load_profile(get_active_profile())["document"]["filename"]


def _compose_document(revision_dir: Path) -> Path:
    return revision_dir / _document_filename()


def _load_drafting_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"drafting-progress.md not found: {path}")
    fields = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
    if not fields:
        raise ValueError(f"empty or invalid frontmatter in {path}")
    return fields


def _active_revision_dir(cycle_dir: Path) -> Path:
    base = _compose_base(cycle_dir)
    session_state = base / "session-state.md"
    active_doc = load_active_doc(session_state, default=1)
    revision_dir = base / f"revision{active_doc}"
    if not revision_dir.exists():
        raise FileNotFoundError(f"revision dir not found: {revision_dir}")
    return revision_dir


def _template_path(name: str) -> Path:
    return KERNEL_TEMPLATES / name


def _ensure_ledger(path: Path, template_name: str) -> None:
    if path.exists():
        return
    template = _template_path(template_name)
    if not template.exists():
        raise FileNotFoundError(f"template not found: {template}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")


def _parse_table_rows(path: Path, *, min_cells: int = 1) -> list[list[str]]:
    if not path.exists():
        return []
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0].lower() in {"id", "section"}:
            continue
        if len(cells) >= min_cells and cells[0]:
            rows.append(cells)
    return rows


def _ledger_paths(cycle_dir: Path) -> tuple[Path, Path]:
    base = _compose_base(cycle_dir)
    return base / "anchor-ledger.md", base / "skip-ledger.md"


def _read_anchors(path: Path) -> list[dict[str, str]]:
    anchors: list[dict[str, str]] = []
    for row in _parse_table_rows(path, min_cells=5):
        if len(row) < 5:
            continue
        anchors.append(
            {
                "id": row[0],
                "section": row[1],
                "criterion": row[2],
                "committed_at_round": row[3],
                "status": row[4].lower(),
            }
        )
    return anchors


def _read_skips(path: Path) -> list[dict[str, str]]:
    skips: list[dict[str, str]] = []
    if not path.exists():
        return skips

    header_cells: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and "---" not in stripped and "section" in stripped.lower():
            header_cells = [cell.strip().lower() for cell in stripped.strip("|").split("|")]
            break

    has_skip_key = "skip key" in header_cells

    for row in _parse_table_rows(path, min_cells=3):
        if len(row) < 3:
            continue
        entry = {
            "section": row[0],
            "kw_gap": row[1],
            "skipped_at_round": row[2],
        }
        if has_skip_key and len(row) >= 5:
            entry["skip_key"] = row[3]
            entry["notes"] = row[4]
        elif len(row) > 3:
            entry["notes"] = row[3]
        skips.append(entry)
    return skips


def _next_anchor_id(anchors: list[dict[str, str]]) -> str:
    max_n = 0
    for anchor in anchors:
        match = re.match(r"A(\d+)", anchor.get("id", ""))
        if match:
            max_n = max(max_n, int(match.group(1)))
    return f"A{max_n + 1}"


def _append_table_row(path: Path, cells: list[str]) -> None:
    line = "| " + " | ".join(cells) + " |"
    text = path.read_text(encoding="utf-8").rstrip() + "\n" + line + "\n"
    path.write_text(text, encoding="utf-8")


def _read_round(revision_dir: Path) -> int:
    progress = revision_dir / "drafting-progress.md"
    if not progress.exists():
        return 1
    try:
        data = _load_drafting_progress(progress)
        return max(1, int(data.get("round", "1")))
    except ValueError:
        return 1


def _format_round_probe_input(
    *,
    cycle_dir: Path,
    cycle_id: str,
    round_n: int,
    compose_doc: Path,
    round_dir: Path | None = None,
    active_section: str | None = None,
) -> str:
    doc_path = compose_doc.resolve().as_posix()
    lines = [
        f"CYCLE_DIR:        {cycle_dir.resolve().as_posix()}",
        f"CYCLE_ID:         {cycle_id}",
        f"ROUND_N:          {round_n}",
        f"COMPOSE_DOC_PATH: {doc_path}",
    ]
    if round_dir is not None:
        lines.append(f"ROUND_DIR:      {round_dir.resolve().as_posix()}")
    if active_section is not None:
        lines.append(f"ACTIVE_SECTION: {active_section}")
    return "\n".join(lines) + "\n"


def _pointer_file(cycle_dir: Path, round_n: int) -> Path:
    revision_dir = _active_revision_dir(cycle_dir)
    return section_pointer_path(revision_dir, round_n)


def _load_pointer_if_exists(cycle_dir: Path, round_n: int) -> dict[str, Any] | None:
    path = _pointer_file(cycle_dir, round_n)
    if not path.exists():
        return None
    return load_section_pointer(path)


def _resolve_probe_path(
    cycle_dir: Path,
    *,
    round_n: int,
    section_key: str | None = None,
) -> Path:
    pointer = _load_pointer_if_exists(cycle_dir, round_n)
    if pointer is None:
        raise FileNotFoundError(
            f"section pointer not found for round {round_n}; run init-round-dir first"
        )
    key = (section_key or pointer["active_section"]).upper()
    entry = pointer["sections"][key]
    latest = entry.get("latest_probe")
    if not latest:
        raise FileNotFoundError(f"no probe report for section {key!r}")
    revision_dir = _active_revision_dir(cycle_dir)
    round_dir = round_directory(revision_dir, round_n)
    return round_dir / latest


def _load_active_probe_report(
    cycle_dir: Path,
    *,
    round_n: int,
    section_key: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    path = _resolve_probe_path(cycle_dir, round_n=round_n, section_key=section_key)
    return path, load_probe_report(path)


def _save_active_probe_report(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_probe_report(report)
    save_probe_report(path, normalized)
    return normalized


def _probe_report_summary(report: dict[str, Any], *, path: Path) -> dict[str, Any]:
    return {
        "ok": True,
        "path": str(path.resolve()),
        "round": report["round"],
        "section_key": report["section_key"],
        "probe_seq": report["probe_seq"],
        "open_count": len(open_items(report)),
        "undecided_count": len(undecided_items(report)),
        "kw0_pending_count": len(kw0_pending_items(report)),
        "upstream_open_count": len(upstream_open_items(report)),
        "upstream_undecided_count": len(upstream_undecided_items(report)),
        "intent_open_count": len(intent_open_items(report)),
        "intent_undecided_count": len(intent_undecided_items(report)),
        "items": report["items"],
        "anchor_failures": report["anchor_failures"],
        "anchor_candidates": report["anchor_candidates"],
    }


def round_probe_input(cycle_dir: Path) -> dict[str, Any]:
    """Return probe dispatch input when current_step is RoundIteration."""
    cycle_id = cycle_dir.name
    progress_path: Path | None = None
    try:
        revision_dir = _active_revision_dir(cycle_dir)
        progress_path = revision_dir / "drafting-progress.md"
    except FileNotFoundError:
        return {
            "ok": False,
            "command": _CMD_ROUND_PROBE_INPUT,
            "reason": "drafting-progress.md not found; run begin-round first",
        }

    if not progress_path.exists():
        return {
            "ok": False,
            "command": _CMD_ROUND_PROBE_INPUT,
            "reason": "drafting-progress.md not found; run begin-round first",
        }

    data = _load_drafting_progress(progress_path)
    step = data.get("current_step")
    if step != _STEP_ROUND:
        payload: dict[str, Any] = {
            "ok": False,
            "command": _CMD_ROUND_PROBE_INPUT,
            "reason": (
                f"cannot generate probe input: current_step is {step!r} "
                f"(expected {_STEP_ROUND})"
            ),
        }
        if step is not None:
            payload["current_step"] = step
        return payload

    round_n = max(1, int(data.get("round", "1")))
    compose_doc = _compose_document(revision_dir)
    round_dir_path = round_directory(revision_dir, round_n)
    pointer = _load_pointer_if_exists(cycle_dir, round_n)
    if pointer is None:
        return {
            "ok": False,
            "command": _CMD_ROUND_PROBE_INPUT,
            "reason": (
                f"section pointer not found for round {round_n}; "
                "run init-round-dir first"
            ),
        }
    dispatch_input = _format_round_probe_input(
        cycle_dir=cycle_dir,
        cycle_id=cycle_id,
        round_n=round_n,
        compose_doc=compose_doc,
        round_dir=round_dir_path,
        active_section=pointer["active_section"],
    )
    return {
        "ok": True,
        "command": _CMD_ROUND_PROBE_INPUT,
        "dispatch_input": dispatch_input,
    }


def cmd_round_probe_input(cycle_dir: Path) -> int:
    result = round_probe_input(cycle_dir)
    if result.get("ok"):
        dispatch_input = result["dispatch_input"]
        sys.stdout.write(dispatch_input)
        if not dispatch_input.endswith("\n"):
            sys.stdout.write("\n")
        return 0
    _emit(result)
    return 1


def _update_anchor_row(path: Path, anchor_id: str, status: str) -> None:
    status = status.lower()
    if status not in {"passing", "failing"}:
        raise ValueError(f"status must be passing or failing, got {status!r}")

    lines = path.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines: list[str] = []
    for line in lines:
        if line.startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and cells[0] == anchor_id and len(cells) >= 5:
                cells[4] = status
                line = "| " + " | ".join(cells) + " |"
                updated = True
        new_lines.append(line)
    if not updated:
        raise ValueError(f"anchor id not found: {anchor_id!r}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def cmd_read_context(cycle_dir: Path) -> int:
    revision_dir = _active_revision_dir(cycle_dir)
    compose_doc = _compose_document(revision_dir)
    anchor_path, skip_path = _ledger_paths(cycle_dir)

    _ensure_ledger(anchor_path, "anchor-ledger.template.md")
    _ensure_ledger(skip_path, "skip-ledger.template.md")

    if not compose_doc.exists():
        return _fail(f"{compose_doc.name} not found: {compose_doc}")

    project_root = project_root_from_cycle_dir(cycle_dir)
    cycle_id = cycle_dir.name

    doc_path = str(compose_doc.resolve())
    payload: dict[str, Any] = {
            "anchors": _read_anchors(anchor_path),
            "skips": _read_skips(skip_path),
            "round": _read_round(revision_dir),
            "compose_doc_path": doc_path,
            "decision_doc_path": "",
            "revision_dir": str(revision_dir.resolve()),
        }
    profile_id = get_active_profile()
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    if ws_path.exists():
        state = load_workflow_state(ws_path)
        payload["delivered_refs"] = [
            ref.to_dict() for ref in parse_delivered_refs(state)
        ]
        scope_ref = init_scope_ref_from_state(state, profile_id)
        if scope_ref is not None:
            payload["decision_doc_path"] = str(Path(scope_ref.path).resolve())
        design_path = delivered_path(state, "tech-design")
        if design_path:
            payload["design_doc_path"] = design_path
    if not payload["decision_doc_path"]:
        from workflow_profile_paths import decision_doc_path  # noqa: WPS433

        payload["decision_doc_path"] = str(
            (project_root / decision_doc_path(cycle_id)).resolve(),
        )

    _emit(payload)
    return 0


def cmd_append_anchor(
    cycle_dir: Path,
    *,
    section: str,
    criterion: str,
    round_n: int,
) -> int:
    section_key = _normalize_section(section)
    anchor_path, _ = _ledger_paths(cycle_dir)
    _ensure_ledger(anchor_path, "anchor-ledger.template.md")

    anchor_id = _next_anchor_id(_read_anchors(anchor_path))
    _append_table_row(
        anchor_path,
        [anchor_id, section_heading(section_key), criterion, str(round_n), "passing"],
    )
    _emit({"ok": True, "id": anchor_id})
    return 0


def _append_skip_row(
    cycle_dir: Path,
    *,
    section: str,
    kw_gap: str,
    round_n: int,
    notes: str = "",
    skip_key: str = "",
) -> None:
    section_key = _normalize_section(section)
    _, skip_path = _ledger_paths(cycle_dir)
    _ensure_ledger(skip_path, "skip-ledger.template.md")
    _append_table_row(
        skip_path,
        [
            section_heading(section_key),
            kw_gap,
            str(round_n),
            skip_key if skip_key else "-",
            notes if notes else "-",
        ],
    )


def cmd_append_skip(
    cycle_dir: Path,
    *,
    section: str,
    kw_gap: str,
    round_n: int,
    notes: str = "",
    skip_key: str = "",
) -> int:
    _append_skip_row(
        cycle_dir,
        section=section,
        kw_gap=kw_gap,
        round_n=round_n,
        notes=notes,
        skip_key=skip_key,
    )
    _emit({"ok": True})
    return 0


def init_round_dir_if_needed(cycle_dir: Path, *, round_n: int) -> dict[str, Any]:
    """Create round-{N}/ and section-pointer.json if missing (idempotent)."""
    revision_dir = _active_revision_dir(cycle_dir)
    path = section_pointer_path(revision_dir, round_n)
    round_dir = round_directory(revision_dir, round_n)
    round_dir.mkdir(parents=True, exist_ok=True)
    if path.exists():
        pointer = load_section_pointer(path)
        return {
            "ok": True,
            "round_dir": str(round_dir.resolve()),
            "pointer_path": str(path.resolve()),
            "active_section": pointer["active_section"],
            "already_initialized": True,
        }

    active_doc = load_active_doc(revision_dir.parent / "session-state.md", default=1)
    pointer = init_section_pointer(
        round_n=round_n,
        revision=active_doc,
        cycle_id=cycle_dir.name,
    )
    save_section_pointer(path, pointer)
    return {
        "ok": True,
        "round_dir": str(round_dir.resolve()),
        "pointer_path": str(path.resolve()),
        "active_section": pointer["active_section"],
        "already_initialized": False,
    }


def cmd_init_round_dir(cycle_dir: Path, *, round_n: int) -> int:
    _emit(init_round_dir_if_needed(cycle_dir, round_n=round_n))
    return 0


def cmd_read_section_pointer(cycle_dir: Path, *, round_n: int) -> int:
    path = _pointer_file(cycle_dir, round_n)
    pointer = load_section_pointer(path)
    _emit({"ok": True, "path": str(path.resolve()), **pointer})
    return 0


def cmd_advance_section(cycle_dir: Path, *, round_n: int) -> int:
    path = _pointer_file(cycle_dir, round_n)
    pointer = load_section_pointer(path)
    updated = advance_section(pointer)
    save_section_pointer(path, updated)
    _emit(
        {
            "ok": True,
            "active_section": updated["active_section"],
            "path": str(path.resolve()),
        }
    )
    return 0


def cmd_rewind_section(
    cycle_dir: Path,
    *,
    round_n: int,
    to_section: str,
    reason: str = "",
) -> int:
    path = _pointer_file(cycle_dir, round_n)
    pointer = load_section_pointer(path)
    target = _normalize_section(to_section)
    updated = rewind_section(pointer, to_section=target, reason=reason)
    save_section_pointer(path, updated)
    _emit(
        {
            "ok": True,
            "active_section": updated["active_section"],
            "invalidated_from": target,
            "path": str(path.resolve()),
        }
    )
    return 0


def cmd_mark_section_stable(cycle_dir: Path, *, round_n: int, section: str) -> int:
    path = _pointer_file(cycle_dir, round_n)
    pointer = load_section_pointer(path)
    section_key = _normalize_section(section)
    updated = mark_section_stable(pointer, section_key)
    save_section_pointer(path, updated)
    _emit({"ok": True, "section": section_key, "status": "stable"})
    return 0


def cmd_write_probe_report(cycle_dir: Path, *, payload: dict[str, Any]) -> int:
    round_n = int(payload["round"])
    revision_dir = _active_revision_dir(cycle_dir)
    pointer_path = section_pointer_path(revision_dir, round_n)
    pointer = load_section_pointer(pointer_path)

    section_key = str(payload["section_key"]).upper()
    if section_key != pointer["active_section"]:
        raise ValueError(
            f"probe section_key {section_key!r} must match active_section "
            f"{pointer['active_section']!r}"
        )

    probe_seq = next_probe_seq(pointer, section_key)
    payload = dict(payload)
    payload["probe_seq"] = probe_seq
    payload.setdefault("kind", "probe")
    payload.setdefault("version", "3")

    round_dir = round_directory(revision_dir, round_n)
    path = probe_report_path(round_dir, section_key, probe_seq)
    save_probe_report(path, payload)
    report = load_probe_report(path)

    updated_pointer = update_latest_probe(pointer, section_key=section_key, probe_seq=probe_seq)
    save_section_pointer(pointer_path, updated_pointer)

    _emit(
        {
            "ok": True,
            "path": str(path.resolve()),
            "round": round_n,
            "section_key": section_key,
            "probe_seq": probe_seq,
            "open_count": len(open_items(report)),
            "undecided_count": len(undecided_items(report)),
            "kw0_pending_count": len(kw0_pending_items(report)),
            "upstream_open_count": len(upstream_open_items(report)),
            "intent_open_count": len(intent_open_items(report)),
            "item_count": len(report["items"]),
        }
    )
    return 0


def cmd_read_probe_report(
    cycle_dir: Path,
    *,
    round_n: int,
    section: str | None = None,
) -> int:
    section_key = _normalize_section(section) if section else None
    path, report = _load_active_probe_report(
        cycle_dir,
        round_n=round_n,
        section_key=section_key,
    )
    pointer = _load_pointer_if_exists(cycle_dir, round_n)
    payload = _probe_report_summary(report, path=path)
    if pointer is not None:
        payload["active_section"] = pointer["active_section"]
    _emit(payload)
    return 0


def cmd_write_refiner_artifact(cycle_dir: Path, *, payload: dict[str, Any]) -> int:
    round_n = int(payload["round"])
    revision_dir = _active_revision_dir(cycle_dir)
    round_dir = round_directory(revision_dir, round_n)
    section_key = str(payload["section_key"]).upper()
    gap_item_id = str(payload["gap_item_id"])
    refiner_seq = payload.get("refiner_seq")
    if refiner_seq is None:
        refiner_seq = next_refiner_seq(round_dir, section_key)
    payload = dict(payload)
    payload["refiner_seq"] = int(refiner_seq)
    payload.setdefault("kind", "refiner")
    payload.setdefault("version", "1")
    path = refiner_artifact_path(round_dir, section_key, int(refiner_seq), gap_item_id)
    save_refiner_artifact(path, payload)
    _emit(
        {
            "ok": True,
            "path": str(path.resolve()),
            "refiner_seq": int(refiner_seq),
            "gap_item_id": gap_item_id,
        }
    )
    return 0


def cmd_read_upstream_context(cycle_dir: Path, *, round_n: int) -> int:
    pointer_path = _pointer_file(cycle_dir, round_n)
    pointer = load_section_pointer(pointer_path)
    graph = load_dependency_graph(project_root=project_root_from_cycle_dir(cycle_dir))
    active = pointer["active_section"]
    _emit(
        {
            "ok": True,
            "active_section": active,
            "stable_upstream": stable_upstream_edges(active, graph, pointer),
            "all_upstream": upstream_edges(active, graph),
        }
    )
    return 0


def cmd_read_section_body(cycle_dir: Path, *, section: str) -> int:
    revision_dir = _active_revision_dir(cycle_dir)
    compose_doc = _compose_document(revision_dir)
    if not compose_doc.exists():
        raise FileNotFoundError(f"{compose_doc.name} not found: {compose_doc}")
    raw = compose_doc.read_text(encoding="utf-8")
    project_root = project_root_from_cycle_dir(cycle_dir)
    key = _normalize_section(section)
    _emit(
        {
            "ok": True,
            "section_key": key,
            "display_heading": section_display_heading(
                raw,
                key,
                project_root=project_root,
            ),
            "body": section_body_by_key(raw, key, project_root=project_root),
            "path": str(compose_doc.resolve()),
        }
    )
    return 0


def cmd_read_gap_report(cycle_dir: Path, *, round_n: int) -> int:
    pointer = _load_pointer_if_exists(cycle_dir, round_n)
    if pointer is None:
        return _fail(
            f"section-pointer not found for round {round_n}; "
            "run init-round-dir before reading the gap report"
        )
    try:
        path, report = _load_active_probe_report(
            cycle_dir,
            round_n=round_n,
            section_key=pointer["active_section"],
        )
    except FileNotFoundError:
        _emit(
            {
                "ok": True,
                "path": str(_pointer_file(cycle_dir, round_n).resolve()),
                "round": round_n,
                "active_section": pointer["active_section"],
                "open_count": 0,
                "undecided_count": 0,
                "kw0_pending_count": 0,
                "upstream_open_count": 0,
                "upstream_undecided_count": 0,
                "intent_open_count": 0,
                "intent_undecided_count": 0,
                "items": [],
                "anchor_failures": [],
                "anchor_candidates": [],
            }
        )
        return 0
    payload = _probe_report_summary(report, path=path)
    payload["active_section"] = pointer["active_section"]
    _emit(payload)
    return 0


def cmd_read_gap_item(cycle_dir: Path, *, round_n: int, item_id: str) -> int:
    pointer = _load_pointer_if_exists(cycle_dir, round_n)
    if pointer is None:
        return _fail(
            f"section-pointer not found for round {round_n}; "
            "run init-round-dir before reading gap items"
        )
    path, report = _load_active_probe_report(
        cycle_dir,
        round_n=round_n,
        section_key=pointer["active_section"],
    )
    item = find_item(report, item_id)
    if item is None:
        return _fail(f"gap item not found: {item_id!r}")
    _emit(
        {
            "ok": True,
            "path": str(path.resolve()),
            "round": report["round"],
            "section_key": report["section_key"],
            "probe_seq": report["probe_seq"],
            "item": item,
            "refiner": probe_refiner_payload(item),
        }
    )
    return 0


def _skip_kw_label(item: dict[str, Any]) -> str:
    gap_kind = str(item.get("gap_kind", "kw")).lower()
    if gap_kind.startswith("upstream_") or gap_kind.startswith("intent_"):
        return gap_kind
    if item.get("target_kw") is not None:
        return f"KW{item['target_kw']}"
    return "—"


def cmd_update_gap_decision(
    cycle_dir: Path,
    *,
    round_n: int,
    item_id: str,
    decision: str,
) -> int:
    pointer = _load_pointer_if_exists(cycle_dir, round_n)
    if pointer is None:
        return _fail(
            f"section-pointer not found for round {round_n}; "
            "run init-round-dir before updating gap decisions"
        )
    path, report = _load_active_probe_report(
        cycle_dir,
        round_n=round_n,
        section_key=pointer["active_section"],
    )
    item = find_item(report, item_id)
    if item is None:
        return _fail(f"gap item not found: {item_id!r}")
    updated = update_probe_item_decision(report, item_id=item_id, decision=decision)
    _save_active_probe_report(path, updated)
    if decision == "skip":
        _append_skip_row(
            cycle_dir,
            section=item["section_key"],
            kw_gap=_skip_kw_label(item),
            round_n=round_n,
            skip_key=item.get("skip_key", ""),
            notes=f"gap-item {item_id}",
        )
    _emit({"ok": True, "id": item_id, "decision": decision})
    return 0


def cmd_update_gap_status(
    cycle_dir: Path,
    *,
    round_n: int,
    item_id: str,
    status: str,
) -> int:
    pointer = _load_pointer_if_exists(cycle_dir, round_n)
    if pointer is None:
        return _fail(
            f"section-pointer not found for round {round_n}; "
            "run init-round-dir before updating gap statuses"
        )
    path, report = _load_active_probe_report(
        cycle_dir,
        round_n=round_n,
        section_key=pointer["active_section"],
    )
    updated = update_probe_item_status(report, item_id=item_id, status=status)
    _save_active_probe_report(path, updated)
    _emit({"ok": True, "id": item_id, "status": status})
    return 0


def cmd_update_anchor_status(
    cycle_dir: Path,
    *,
    anchor_id: str,
    status: str,
) -> int:
    anchor_path, _ = _ledger_paths(cycle_dir)
    _ensure_ledger(anchor_path, "anchor-ledger.template.md")
    _update_anchor_row(anchor_path, anchor_id, status)
    _emit({"ok": True, "id": anchor_id, "status": status.lower()})
    return 0


def cmd_check_convergence(
    cycle_dir: Path,
    *,
    no_accept: bool,
    gaps_resolved: bool,
    round_n: int | None = None,
) -> int:
    revision_dir = _active_revision_dir(cycle_dir)
    if round_n is None:
        round_n = _read_round(revision_dir)

    anchor_path, _ = _ledger_paths(cycle_dir)
    _ensure_ledger(anchor_path, "anchor-ledger.template.md")
    anchors = _read_anchors(anchor_path)
    failing_anchors = [a for a in anchors if a.get("status") != "passing"]

    reasons: list[str] = []
    if not no_accept:
        reasons.append("round had accept")
    if not gaps_resolved:
        reasons.append("open gaps remain undecided")
    if failing_anchors:
        reasons.append(f"{len(failing_anchors)} anchor(s) not passing")

    pointer = _load_pointer_if_exists(cycle_dir, round_n)
    round_dir = round_directory(revision_dir, round_n)
    if round_dir.exists():
        if pointer is None:
            reasons.append("section pointer not initialized")
        elif not all_sections_stable(pointer):
            reasons.append("not all sections stable")
    elif pointer is not None and not all_sections_stable(pointer):
        reasons.append("not all sections stable")

    converged = not reasons
    _emit({"converged": converged, "reason": "ok" if converged else "; ".join(reasons)})
    return 0


_ROUND_REQUIRED_COMMANDS = frozenset(
    {
        "append-anchor",
        "append-skip",
        "init-round-dir",
        "read-section-pointer",
        "read-upstream-context",
        "advance-section",
        "rewind-section",
        "mark-section-stable",
        "read-probe-report",
        "read-gap-report",
        "read-gap-item",
        "update-gap-decision",
        "update-gap-status",
    }
)


def _resolve_round_n(args: argparse.Namespace, cycle_dir: Path) -> int | None:
    if args.round is not None:
        return int(args.round)
    if args.command in _ROUND_REQUIRED_COMMANDS:
        return None
    if args.command == "check-convergence":
        return _read_round(_active_revision_dir(cycle_dir))
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Round Iteration control")
    parser.add_argument(
        "--cycle-dir",
        required=True,
        type=Path,
        help="Absolute path to cycle directory ($CACHE_DIR/<cycle_id>)",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_COMPOSE_PROFILE_ID,
        help="Compose profile / stage name (default: tech-plan)",
    )
    parser.add_argument(
        "--round",
        type=int,
        default=None,
        help="Macro round N for round-scoped subcommands",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("read-context")

    append_anchor = sub.add_parser("append-anchor")
    append_anchor.add_argument("--section", required=True)
    append_anchor.add_argument("--criterion", required=True)

    append_skip = sub.add_parser("append-skip")
    append_skip.add_argument("--section", required=True)
    append_skip.add_argument("--kw-gap", required=True, dest="kw_gap")
    append_skip.add_argument("--notes", default="")
    append_skip.add_argument("--skip-key", default="")

    sub.add_parser("init-round-dir")

    sub.add_parser("read-section-pointer")

    sub.add_parser("read-upstream-context")

    read_section_body = sub.add_parser("read-section-body")
    read_section_body.add_argument("--section", required=True)

    sub.add_parser("advance-section")

    rewind = sub.add_parser("rewind-section")
    rewind.add_argument("--to", required=True, dest="to_section")
    rewind.add_argument("--reason", default="")

    mark_stable = sub.add_parser("mark-section-stable")
    mark_stable.add_argument("--section", required=True)

    write_probe = sub.add_parser("write-probe-report")
    write_probe.add_argument("--json", required=True, help="Probe report JSON payload")

    write_refiner = sub.add_parser("write-refiner-artifact")
    write_refiner.add_argument("--json", required=True, help="Refiner artifact JSON payload")

    read_probe = sub.add_parser("read-probe-report")
    read_probe.add_argument("--section", default=None)

    sub.add_parser("read-gap-report")

    read_item = sub.add_parser("read-gap-item")
    read_item.add_argument("--id", required=True)

    update_decision = sub.add_parser("update-gap-decision")
    update_decision.add_argument("--id", required=True)
    update_decision.add_argument(
        "--decision",
        required=True,
        choices=["accept", "skip", "redirect"],
    )

    update_status = sub.add_parser("update-gap-status")
    update_status.add_argument("--id", required=True)
    update_status.add_argument(
        "--status",
        required=True,
        choices=["open", "no_gap", "resolved"],
    )

    update_anchor = sub.add_parser("update-anchor-status")
    update_anchor.add_argument("--id", required=True)
    update_anchor.add_argument(
        "--status",
        required=True,
        choices=["passing", "failing"],
    )

    check_conv = sub.add_parser("check-convergence")
    check_conv.add_argument(
        "--no-accept",
        action="store_true",
        help="Round had no accepted gap items",
    )
    check_conv.add_argument(
        "--gaps-resolved",
        action="store_true",
        help="Every initial open gap was decided (accept/skip/redirect)",
    )

    sub.add_parser(
        _CMD_ROUND_PROBE_INPUT,
        help="Print prober-runner Input block (requires RoundIteration)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    set_active_profile(args.profile.strip())
    cycle_dir = args.cycle_dir.resolve()
    round_n = _resolve_round_n(args, cycle_dir)
    if args.command in _ROUND_REQUIRED_COMMANDS and round_n is None:
        return _fail("--round is required for this subcommand")

    try:
        if args.command == "read-context":
            return cmd_read_context(cycle_dir)
        if args.command == "append-anchor":
            return cmd_append_anchor(
                cycle_dir,
                section=args.section,
                criterion=args.criterion,
                round_n=round_n,
            )
        if args.command == "append-skip":
            return cmd_append_skip(
                cycle_dir,
                section=args.section,
                kw_gap=args.kw_gap,
                round_n=round_n,
                notes=args.notes,
                skip_key=args.skip_key,
            )
        if args.command == "init-round-dir":
            return cmd_init_round_dir(cycle_dir, round_n=round_n)
        if args.command == "read-section-pointer":
            return cmd_read_section_pointer(cycle_dir, round_n=round_n)
        if args.command == "read-upstream-context":
            return cmd_read_upstream_context(cycle_dir, round_n=round_n)
        if args.command == "read-section-body":
            return cmd_read_section_body(cycle_dir, section=args.section)
        if args.command == "advance-section":
            return cmd_advance_section(cycle_dir, round_n=round_n)
        if args.command == "rewind-section":
            return cmd_rewind_section(
                cycle_dir,
                round_n=round_n,
                to_section=args.to_section,
                reason=args.reason,
            )
        if args.command == "mark-section-stable":
            return cmd_mark_section_stable(
                cycle_dir,
                round_n=round_n,
                section=args.section,
            )
        if args.command == "write-probe-report":
            payload = json.loads(args.json)
            return cmd_write_probe_report(cycle_dir, payload=payload)
        if args.command == "write-refiner-artifact":
            payload = json.loads(args.json)
            return cmd_write_refiner_artifact(cycle_dir, payload=payload)
        if args.command == "read-probe-report":
            return cmd_read_probe_report(
                cycle_dir,
                round_n=round_n,
                section=args.section,
            )
        if args.command == "read-gap-report":
            return cmd_read_gap_report(cycle_dir, round_n=round_n)
        if args.command == "read-gap-item":
            return cmd_read_gap_item(
                cycle_dir,
                round_n=round_n,
                item_id=args.id,
            )
        if args.command == "update-gap-decision":
            return cmd_update_gap_decision(
                cycle_dir,
                round_n=round_n,
                item_id=args.id,
                decision=args.decision,
            )
        if args.command == "update-gap-status":
            return cmd_update_gap_status(
                cycle_dir,
                round_n=round_n,
                item_id=args.id,
                status=args.status,
            )
        if args.command == "update-anchor-status":
            return cmd_update_anchor_status(
                cycle_dir,
                anchor_id=args.id,
                status=args.status,
            )
        if args.command == "check-convergence":
            return cmd_check_convergence(
                cycle_dir,
                no_accept=args.no_accept,
                gaps_resolved=args.gaps_resolved,
                round_n=round_n,
            )
        if args.command == _CMD_ROUND_PROBE_INPUT:
            return cmd_round_probe_input(cycle_dir)
        return _fail(f"unknown command: {args.command}")
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
