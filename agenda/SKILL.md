---
name: agenda
description: >-
  Stage agenda (阶段议程): session/revision-local blocker and note items outside
  design substance. Shared library used by compose deliver gate; human-driven
  add/update; list --blocking-only for delivery.
---

# agenda

Shared **stage agenda** library (not a user stage). Holds design-external items (`blocker` / `note`) beside the current session/revision directory. Compose `deliver` mechanically refuses when blocking items remain.

## Boundary

- **In:** add / update / list / menu via `$AGENDA_CTL`; deliver gate reads blocking list.
- **Out:** not `inductive-opens`, not `deductive-pending`, not design lens `OQ`.
- **Does not** discover current stage — caller passes `--revision-dir`.
- **Writes** only after **explicit human instruction** (no silent add).

## Prerequisites

- `$SKILL_ROOT`, revision directory for the active compose (or other) session.
- Presentation labels: `$SKILL_ROOT/agenda/references/agenda-presentation.md`

## Script Macros

| Macro | Command |
|-------|---------|
| `$AGENDA_CTL` | `python3 "$SKILL_ROOT/agenda/scripts/agenda_control.py" <subcommand> [args...]` |

Session identity (preferred — same as compose session controls):

```bash
$AGENDA_CTL add \
  --project-root "$(pwd)" \
  --cycle-id "$CYCLE_ID" \
  --profile <profile_id> \
  --class blocker \
  --text "..."
```

Python resolves `session-state.md` → `active_doc` → `revision{N}/`. Do **not** ask the user for a revision path. `--revision-dir` is only for tests / escape hatch.

Subcommands and stdout: `agenda_control.py --help`.

## When to use

1. **User says `agenda 查看命令`** (or clearly wants the agenda action list) → `$AGENDA_CTL menu` → offer **only** prefixed L1 labels from stdout / `agenda-presentation.md` (every phrase starts with `agenda`).
2. **User picks a prefixed option** (e.g. `agenda 新增 blocker`) → run matching `$AGENDA_CTL add|update|list` with `--cycle-id` / `--profile` (writes only after that explicit pick).
3. **Compose deliver** — mechanical (in `session_control.deliver`); agents do not skip this by calling schema directly.

**Hard rule:** never offer bare labels without the `agenda` prefix (avoids colliding with other workflow stops).

## Item rules (summary)

| class | Delivery |
|-------|----------|
| `blocker` + `open` + `async=false` | Blocks `deliver` |
| `blocker` + `async=true` | Tracked, does not block |
| `note` | Never blocks |
| `released` / `waived` (+ `reason` required) | Does not block |

Missing `agenda.json` ⇒ no blockers (empty).

## Done

- Write commands: `$AGENDA_CTL` stdout `ok: true` and item echoes intent.
- Deliver path: non-empty blocking list ⇒ `deliver` fails with `agenda_blocking` (compose session control).
