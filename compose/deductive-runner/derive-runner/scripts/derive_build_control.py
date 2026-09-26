#!/usr/bin/env python3
"""Prepare mechanical context for derive-runner (Derive step).

Subcommands:
    context       Registry + section_order; require intake eval done
    lens-bundle   Per-lens KW slice (## LENS) + Ceiling material facts

Rationale (design): docs/archive/lulu-workflow/compose/archive-32.0/
compose-derive-edge-holes-lifecycle-scheme-draft.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_COMPOSE = Path(__file__).resolve().parents[3]
_SCRIPTS = _COMPOSE / "scripts"
_INTAKE_EVAL = _COMPOSE / "fact-intake-runner" / "fact-intake-eval" / "scripts"
_EVAL_SCRIPTS = _COMPOSE.parent / "eval" / "scripts"
for _path in (_SCRIPTS, _SCRIPTS / "_kernel", _SCRIPTS / "templates", _INTAKE_EVAL, _EVAL_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from eval_path import ensure_eval_script_layers  # noqa: E402

ensure_eval_script_layers()
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from execution_state_schema import execution_dir  # noqa: E402
from evaluate_state_schema import load_evaluate_state  # noqa: E402
from fact_intake_eval_runtime_schema import (  # noqa: E402
    evaluate_state_path,
    gate_allows_derive_from_evaluate_state,
)
from facts_schema import (  # noqa: E402
    facts_path,
    filter_by_lens,
    load_facts,
    pd_material_facts,
)
from compose_template_loader import (  # noqa: E402
    ComposeTemplateLoadError,
    load_compose_template,
)
from section_registry_schema import fetch_section_registry, lens_key_sequence  # noqa: E402
from workflow_paths import resolve_revision_runtime_profile  # noqa: E402

_H2_RE = re.compile(r"^##\s+(\S+)\s*$", re.MULTILINE)


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _require_intake_eval(revision_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    slice_dir = execution_dir(revision_dir.resolve())
    es = evaluate_state_path(slice_dir)
    legacy = slice_dir / "atomize-eval" / "evaluate-state.md"
    gate = es if es.is_file() else legacy
    if not gate.is_file():
        return None, f"intake eval gate missing (expected {es.as_posix()})"
    try:
        data = load_evaluate_state(gate)
    except (OSError, ValueError) as exc:
        return None, f"intake eval gate unreadable: {exc}"
    if not gate_allows_derive_from_evaluate_state(data):
        return None, (
            f"intake eval not done (eval_status={data.get('eval_status')!r})"
        )
    return data, None


def _fetch_registry_and_kw(
    root: Path,
    profile: str,
    cycle_id: str | None,
    *,
    profile_path: Path | None = None,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    try:
        reg = fetch_section_registry(
            root,
            profile_id=profile,
            cycle_id=cycle_id,
            profile_path=profile_path,
        )
        kw_raw = load_compose_template(
            "section-kw-criteria",
            root,
            profile_id=profile,
            cycle_id=cycle_id,
            profile_path=profile_path,
        )
    except (ComposeTemplateLoadError, OSError, ValueError, json.JSONDecodeError) as exc:
        return None, None, str(exc)
    if not isinstance(kw_raw, str) or not kw_raw.strip():
        return None, None, "section-kw-criteria must be non-empty text"
    return reg, kw_raw, None


def _section_order(reg: dict[str, Any]) -> list[str]:
    return lens_key_sequence(reg)


def slice_kw_criteria(kw_raw: str, lens: str) -> str | None:
    """Return body under ``## <LENS>`` until the next ATX h2, or None."""
    key = lens.strip().upper()
    matches = list(_H2_RE.finditer(kw_raw))
    for index, match in enumerate(matches):
        if match.group(1).strip().upper() != key:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(kw_raw)
        return kw_raw[start:end].strip("\n")
    return None


def cmd_context(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    cycle_id = (args.cycle_id or "").strip() or None
    data, err = _require_intake_eval(Path(args.revision_dir))
    if err:
        return _fail(err)
    assert data is not None
    try:
        runtime = resolve_revision_runtime_profile(
            Path(args.revision_dir),
            root,
            cycle_id=cycle_id,
        )
    except (OSError, ValueError) as exc:
        return _fail(str(exc))
    reg, kw_raw, ferr = _fetch_registry_and_kw(
        root,
        runtime.profile_id,
        cycle_id,
        profile_path=runtime.profile_path,
    )
    if ferr:
        return _fail(ferr)
    assert reg is not None and kw_raw is not None
    order = _section_order(reg)
    if not order:
        return _fail("section-registry missing non-empty section_order")
    return _ok(
        {
            "ok": True,
            "command": "context",
            "eval_status": data.get("eval_status"),
            "section_order": order,
            "section_registry": reg,
            "section_kw_criteria": kw_raw,
        }
    )


def cmd_lens_bundle(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    cycle_id = (args.cycle_id or "").strip() or None
    lens = args.lens.strip().upper()
    if not lens:
        return _fail("--lens must be a non-empty lens key")
    _data, err = _require_intake_eval(Path(args.revision_dir))
    if err:
        return _fail(err)
    try:
        runtime = resolve_revision_runtime_profile(
            Path(args.revision_dir),
            root,
            cycle_id=cycle_id,
        )
    except (OSError, ValueError) as exc:
        return _fail(str(exc))
    reg, kw_raw, ferr = _fetch_registry_and_kw(
        root,
        runtime.profile_id,
        cycle_id,
        profile_path=runtime.profile_path,
    )
    if ferr:
        return _fail(ferr)
    assert reg is not None and kw_raw is not None
    order = _section_order(reg)
    if not order:
        return _fail("section-registry missing non-empty section_order")
    if lens not in order:
        return _fail(f"lens {lens!r} not in section_order")
    kw_slice = slice_kw_criteria(kw_raw, lens)
    if kw_slice is None:
        return _fail(f"KW criteria missing ATX heading ## {lens}")
    slice_dir = execution_dir(Path(args.revision_dir).resolve())
    try:
        facts = load_facts(facts_path(slice_dir))
    except ValueError as exc:
        return _fail(str(exc))
    materials = pd_material_facts(facts)
    lens_facts = filter_by_lens(materials, lens)
    return _ok(
        {
            "ok": True,
            "command": "lens-bundle",
            "lens": lens,
            "kw_criteria": kw_slice,
            "facts": lens_facts,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    context = sub.add_parser(
        "context",
        help="Fetch Derive context; require intake-eval done",
    )
    context.add_argument("--revision-dir", required=True)
    context.add_argument("--project-root", required=True)
    context.add_argument("--cycle-id", default="")
    context.set_defaults(func=cmd_context)

    bundle = sub.add_parser(
        "lens-bundle",
        help="Per-lens KW slice + Ceiling material facts",
    )
    bundle.add_argument("--lens", required=True)
    bundle.add_argument("--revision-dir", required=True)
    bundle.add_argument("--project-root", required=True)
    bundle.add_argument("--cycle-id", default="")
    bundle.set_defaults(func=cmd_lens_bundle)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
