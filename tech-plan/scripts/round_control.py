#!/usr/bin/env python3
"""Round Iteration control for tech-plan orchestrator.

Subcommands:
    read-context          Return state-vector, anchors, skips, round metadata
    check-l0              List sections still at L0
    apply-zoom            Update state-vector and append signed comment
    append-anchor         Append anchor ledger entry
    append-skip           Append skip ledger entry (rejects L0)
    update-anchor-status  Set anchor ledger entry status (passing | failing)
    check-convergence     Evaluate convergence conditions
    round-probe-input     Gate Probe entry; print prober-runner ## Input block (plain text)

Does not write drafting-progress.md — use draft_control.py for progress transitions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drafting_progress_schema import load_drafting_progress  # noqa: E402
from session_state_schema import load_active_doc  # noqa: E402
from workflow_common import detect_cycle_type  # noqa: E402

_CMD_ROUND_PROBE_INPUT = "round-probe-input"
_STEP_ROUND = "RoundIteration"

SECTION_KEYS = ("NS", "NG", "KD", "SK", "T")
SECTION_HEADINGS = {
    "NS": "North Star",
    "NG": "Non-Goals & Invariants",
    "KD": "Key Decisions",
    "SK": "Approach Skeleton",
    "T": "Tasks",
}
SECTION_ALIASES = {
    **{k: k for k in SECTION_KEYS},
    **{v.lower(): k for k, v in SECTION_HEADINGS.items()},
    **{k.lower(): k for k in SECTION_KEYS},
    "north star": "NS",
    "non-goals & invariants": "NG",
    "non-goals and invariants": "NG",
    "key decisions": "KD",
    "approach skeleton": "SK",
    "tasks": "T",
}

STATE_VECTOR_RE = re.compile(
    r"<!--\s*state-vector:\s*([^>]+)\s*-->", re.IGNORECASE
)


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _fail(message: str, code: int = 1) -> int:
    print(message, file=sys.stderr)
    return code


def _plan_base(cycle_dir: Path) -> Path:
    return cycle_dir / "tech" / "plan"


def _active_revision_dir(cycle_dir: Path) -> Path:
    base = _plan_base(cycle_dir)
    session_state = base / "session-state.md"
    active_doc = load_active_doc(session_state, default=1)
    revision_dir = base / f"revision{active_doc}"
    if not revision_dir.exists():
        raise FileNotFoundError(f"revision dir not found: {revision_dir}")
    return revision_dir


def _template_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / name


def _ensure_ledger(path: Path, template_name: str) -> None:
    if path.exists():
        return
    template = _template_path(template_name)
    if not template.exists():
        raise FileNotFoundError(f"template not found: {template}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")


def _normalize_section(raw: str) -> str:
    key = SECTION_ALIASES.get(raw.strip().lower())
    if not key:
        raise ValueError(f"unknown section: {raw!r}")
    return key


def _parse_state_vector(text: str) -> dict[str, int]:
    match = STATE_VECTOR_RE.search(text)
    if not match:
        return {k: 0 for k in SECTION_KEYS}
    raw: dict[str, int] = {}
    for part in match.group(1).split(","):
        part = part.strip()
        if ":" not in part:
            continue
        key, level = part.split(":", 1)
        key = key.strip().upper()
        level = level.strip().upper()
        if level.startswith("L"):
            level = level[1:]
        if key in SECTION_KEYS or key == "INV":
            raw[key] = int(level)
    result: dict[str, int] = {}
    for key in SECTION_KEYS:
        result[key] = raw.get(key, 0)
    if "INV" in raw:
        result["NG"] = max(result["NG"], raw["INV"])
    return result


def _format_state_vector(levels: dict[str, int]) -> str:
    parts = [f"{k}:L{levels[k]}" for k in SECTION_KEYS]
    return f"<!-- state-vector: {', '.join(parts)} -->"


def _update_state_vector_comment(text: str, levels: dict[str, int]) -> str:
    replacement = _format_state_vector(levels)
    if STATE_VECTOR_RE.search(text):
        return STATE_VECTOR_RE.sub(replacement, text, count=1)
    if "---" in text:
        return text.replace("---\n\n", f"---\n\n{replacement}\n\n", 1)
    return f"{replacement}\n\n{text}"


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
    base = _plan_base(cycle_dir)
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
    for row in _parse_table_rows(path, min_cells=3):
        if len(row) < 3:
            continue
        entry = {
            "section": row[0],
            "probe": row[1],
            "skipped_at_round": row[2],
        }
        if len(row) > 3:
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


def _insert_signed_comment(text: str, section_key: str, round_n: int, level: int) -> str:
    heading = f"## {SECTION_HEADINGS[section_key]}"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    signed = f"<!-- signed: Round {round_n}, L{level}, {timestamp} -->"
    idx = text.find(heading)
    if idx == -1:
        raise ValueError(f"section heading not found: {heading}")
    return text[:idx] + signed + "\n\n" + text[idx:]


def _read_round(revision_dir: Path) -> int:
    progress = revision_dir / "drafting-progress.md"
    if not progress.exists():
        return 1
    try:
        data = load_drafting_progress(progress)
        return max(1, int(data.get("round", "1")))
    except ValueError:
        return 1


def _format_round_probe_input(
    *,
    cycle_dir: Path,
    cycle_id: str,
    cycle_type: str,
    round_n: int,
    tech_doc: Path,
) -> str:
    return (
        f"CYCLE_DIR:      {cycle_dir.resolve().as_posix()}\n"
        f"CYCLE_ID:       {cycle_id}\n"
        f"CYCLE_TYPE:     {cycle_type}\n"
        f"ROUND_N:        {round_n}\n"
        f"TECH_DOC_PATH:  {tech_doc.resolve().as_posix()}"
    )


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

    data = load_drafting_progress(progress_path)
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
    tech_doc = revision_dir / "tech-doc.md"
    dispatch_input = _format_round_probe_input(
        cycle_dir=cycle_dir,
        cycle_id=cycle_id,
        cycle_type=detect_cycle_type(cycle_id),
        round_n=round_n,
        tech_doc=tech_doc,
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
    tech_doc = revision_dir / "tech-doc.md"
    anchor_path, skip_path = _ledger_paths(cycle_dir)

    _ensure_ledger(anchor_path, "anchor-ledger.template.md")
    _ensure_ledger(skip_path, "skip-ledger.template.md")

    if not tech_doc.exists():
        return _fail(f"tech-doc.md not found: {tech_doc}")

    text = tech_doc.read_text(encoding="utf-8")
    _emit(
        {
            "state_vector": _parse_state_vector(text),
            "anchors": _read_anchors(anchor_path),
            "skips": _read_skips(skip_path),
            "round": _read_round(revision_dir),
            "tech_doc_path": str(tech_doc.resolve()),
            "revision_dir": str(revision_dir.resolve()),
        }
    )
    return 0


def cmd_check_l0(cycle_dir: Path) -> int:
    revision_dir = _active_revision_dir(cycle_dir)
    tech_doc = revision_dir / "tech-doc.md"
    if not tech_doc.exists():
        return _fail(f"tech-doc.md not found: {tech_doc}")
    levels = _parse_state_vector(tech_doc.read_text(encoding="utf-8"))
    l0_sections = [SECTION_HEADINGS[k] for k in SECTION_KEYS if levels.get(k, 0) == 0]
    _emit({"l0_sections": l0_sections})
    return 0


def cmd_apply_zoom(
    cycle_dir: Path,
    *,
    section: str,
    from_l: int,
    to_l: int,
    round_n: int,
) -> int:
    section_key = _normalize_section(section)
    revision_dir = _active_revision_dir(cycle_dir)
    tech_doc = revision_dir / "tech-doc.md"
    if not tech_doc.exists():
        return _fail(f"tech-doc.md not found: {tech_doc}")

    text = tech_doc.read_text(encoding="utf-8")
    levels = _parse_state_vector(text)
    current = levels.get(section_key, 0)
    if current != from_l:
        return _fail(f"state mismatch: {section_key} is L{current}, expected L{from_l}")
    if to_l <= from_l:
        return _fail(f"target L{to_l} must be greater than from L{from_l}")

    levels[section_key] = to_l
    text = _update_state_vector_comment(text, levels)
    text = _insert_signed_comment(text, section_key, round_n, to_l)
    tech_doc.write_text(text, encoding="utf-8")
    _emit({"ok": True, "section": section_key, "new_level": to_l})
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
        [anchor_id, SECTION_HEADINGS[section_key], criterion, str(round_n), "passing"],
    )
    _emit({"ok": True, "id": anchor_id})
    return 0


def cmd_append_skip(
    cycle_dir: Path,
    *,
    section: str,
    probe: str,
    round_n: int,
    notes: str = "",
) -> int:
    section_key = _normalize_section(section)
    revision_dir = _active_revision_dir(cycle_dir)
    tech_doc = revision_dir / "tech-doc.md"
    if not tech_doc.exists():
        return _fail(f"tech-doc.md not found: {tech_doc}")

    levels = _parse_state_vector(tech_doc.read_text(encoding="utf-8"))
    if levels.get(section_key, 0) == 0:
        return _fail("L0 sections cannot be written to skip-ledger")

    _, skip_path = _ledger_paths(cycle_dir)
    _ensure_ledger(skip_path, "skip-ledger.template.md")
    _append_table_row(
        skip_path,
        [
            SECTION_HEADINGS[section_key],
            probe.upper(),
            str(round_n),
            notes if notes else "-",
        ],
    )
    _emit({"ok": True})
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
    probes_passed: bool,
) -> int:
    revision_dir = _active_revision_dir(cycle_dir)
    tech_doc = revision_dir / "tech-doc.md"
    anchor_path, _ = _ledger_paths(cycle_dir)
    if not tech_doc.exists():
        return _fail(f"tech-doc.md not found: {tech_doc}")

    _ensure_ledger(anchor_path, "anchor-ledger.template.md")
    anchors = _read_anchors(anchor_path)
    failing_anchors = [a for a in anchors if a.get("status") != "passing"]
    levels = _parse_state_vector(tech_doc.read_text(encoding="utf-8"))
    l0_sections = [SECTION_HEADINGS[k] for k in SECTION_KEYS if levels.get(k, 0) == 0]

    reasons: list[str] = []
    if not no_accept:
        reasons.append("round had accept")
    if not probes_passed:
        reasons.append("probes not all passed")
    if failing_anchors:
        reasons.append(f"{len(failing_anchors)} anchor(s) not passing")
    if l0_sections:
        reasons.append(f"L0 sections remain: {', '.join(l0_sections)}")

    converged = not reasons
    _emit({"converged": converged, "reason": "ok" if converged else "; ".join(reasons)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Round Iteration control")
    parser.add_argument(
        "--cycle-dir",
        required=True,
        type=Path,
        help="Absolute path to cycle directory ($CACHE_DIR/<cycle_id>)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("read-context")
    sub.add_parser("check-l0")

    apply_zoom = sub.add_parser("apply-zoom")
    apply_zoom.add_argument("--section", required=True)
    apply_zoom.add_argument("--from-l", type=int, required=True)
    apply_zoom.add_argument("--to-l", type=int, required=True)
    apply_zoom.add_argument("--round", type=int, required=True)

    append_anchor = sub.add_parser("append-anchor")
    append_anchor.add_argument("--section", required=True)
    append_anchor.add_argument("--criterion", required=True)
    append_anchor.add_argument("--round", type=int, required=True)

    append_skip = sub.add_parser("append-skip")
    append_skip.add_argument("--section", required=True)
    append_skip.add_argument("--probe", required=True)
    append_skip.add_argument("--round", type=int, required=True)
    append_skip.add_argument("--notes", default="")

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
        help="Round had no accepted zoom items",
    )
    check_conv.add_argument(
        "--probes-passed",
        action="store_true",
        help="All probes passed in the current round",
    )

    sub.add_parser(
        _CMD_ROUND_PROBE_INPUT,
        help="Print prober-runner Input block (requires RoundIteration)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cycle_dir = args.cycle_dir.resolve()

    try:
        if args.command == "read-context":
            return cmd_read_context(cycle_dir)
        if args.command == "check-l0":
            return cmd_check_l0(cycle_dir)
        if args.command == "apply-zoom":
            return cmd_apply_zoom(
                cycle_dir,
                section=args.section,
                from_l=args.from_l,
                to_l=args.to_l,
                round_n=args.round,
            )
        if args.command == "append-anchor":
            return cmd_append_anchor(
                cycle_dir,
                section=args.section,
                criterion=args.criterion,
                round_n=args.round,
            )
        if args.command == "append-skip":
            return cmd_append_skip(
                cycle_dir,
                section=args.section,
                probe=args.probe,
                round_n=args.round,
                notes=args.notes,
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
                probes_passed=args.probes_passed,
            )
        if args.command == _CMD_ROUND_PROBE_INPUT:
            return cmd_round_probe_input(cycle_dir)
        return _fail(f"unknown command: {args.command}")
    except (FileNotFoundError, ValueError) as exc:
        return _fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
