---
name: lulu-approach
---

# lulu-approach

Domain holder for technical diagnostic decisions. It orchestrates one `decision` session under approach constraints; scripts own transitions, validation, and persistence.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and `../decision/SKILL.md` in full, and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-approach`
- `$DECISION_SKILL_DIR` = `$SKILL_ROOT/decision`
- `$APPROACH_ROOT` = `$CACHE_DIR/<cycle_id>/lulu-approach` (the decision session)
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

## Script Macros

| Macro | Command |
|-------|---------|
| `$RESOLVE_CONTEXT` | `python3 "$SKILL_DIR/scripts/resolve_context.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json" [--session-dir "<approach_root>"]` |
| `$RESOLVE_CONTEXT_DOCS` | `python3 "$SKILL_DIR/scripts/resolve_context_docs.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` |
| `$RESOLVE_CONSTRAINT_DOCS` | `python3 "$SKILL_DIR/scripts/resolve_constraint_docs.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` |
| `$APPROACH_SHELL` | `python3 "$SKILL_DIR/scripts/approach_shell_control.py" --approach-root "$APPROACH_ROOT"` |
| `$APPROACH_SESSION` | `python3 "$SKILL_DIR/scripts/approach_shell_control.py" --approach-root "$APPROACH_ROOT" <subcommand> --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` |
| `$APPROACH_DELIVER` | `python3 "$SKILL_DIR/scripts/approach_shell_control.py" --approach-root "$APPROACH_ROOT" deliver --cycle-id "<cycle_id>" --project-root "$(pwd)" --confirm` |

Decision macros (`$DEC_START`, `$GATE_CONTROL`, `$RS_COMMIT`, ...) are defined in `../decision/SKILL.md`; `<constraints_path>` is `$SKILL_DIR/constraints-$CYCLE_TYPE.json`.

- Subcommand and stdout contracts remain in script module docstrings or `--help`.
- Any command that exits non-zero stops the flow: report stderr.

## Shared procedures

Steps that Start, Resume, and Reopen invoke by name.

### Pre-entry loading

Run before `$DEC_START`, `$APPROACH_SESSION enter`, or `$APPROACH_SESSION reopen`. For each kind, in this order:

| Kind | Docs macro | Rules |
|------|------------|-------|
| Context | `$RESOLVE_CONTEXT_DOCS` | `$SKILL_DIR/references/context-rules.md` |
| Constraint | `$RESOLVE_CONSTRAINT_DOCS` | `$SKILL_DIR/references/constraint-rules.md` |

1. Run the docs macro. Parse stdout for `files`.
2. Read each path in `files` once. If `files` is empty, skip reading.
3. Load the rules file and apply its sections in order (Principle → materials → Obligation → Body entry → Self-check). Do not classify documents into kinds yourself.

### Context activation

Run after `$DEC_START`, `$APPROACH_SESSION enter`, or `$APPROACH_SESSION reopen` returns `context_docs`:

1. Run `$GATE_CONTROL resolve-context` and pin `$CTX`.
2. Read each returned `context_docs` path once.
3. Declare the active session to the user. Use only the newly pinned `$CTX`.

Do not re-run Pre-entry loading; it runs only before session entry.

## Routes

Resume and Reopen require the approach shell in Session state. From PackageReady or Delivered, report an unsupported state and stop.

### Start

Once Session Foundation is complete:

1. Complete [Pre-entry loading](#pre-entry-loading).
2. Run `$RESOLVE_CONTEXT` with `--session-dir "$APPROACH_ROOT"`; capture stdout path as `$RESOLVED_CONTEXT_PATH`.
3. Run `$APPROACH_SHELL init-shell`.
4. Run `$DEC_START` with:

   ```bash
   --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json" \
   --domain-constraints-file "$RESOLVED_CONTEXT_PATH" \
   --session-dir "$APPROACH_ROOT"
   ```

   If it reports a blocked prior stage, report that stage and do not retry.
5. Complete [Context activation](#context-activation).
6. Run the delegated DDF on Active. DC close includes `$GATE_CONTROL complete`.

When the session is Completed, continue with [Deliver](#deliver).

### Resume

When Active remains this session:

1. Complete [Pre-entry loading](#pre-entry-loading).
2. Run `$APPROACH_SESSION enter`.
3. Complete [Context activation](#context-activation).

Then resume the delegated DDF on Active.

### Reopen

Requires the approach shell in Session state. If the state is unknown, stop and report rather than infer it from files.

1. Complete [Pre-entry loading](#pre-entry-loading).
2. Run `$APPROACH_SESSION reopen`. Capture stdout `permit_path` as `$PERMIT_PATH` and `transaction_id` as `$TRANSACTION_ID`.
3. Complete [Context activation](#context-activation).
4. Run `$DEC_REOPEN --permit "$PERMIT_PATH"`, perform RS dialogue, then run `$RS_COMMIT --gate "<G>" --operations '<json array>'`.
5. Run `$APPROACH_SESSION complete-reopen --transaction-id "$TRANSACTION_ID"`.

Once the session is repaired, resume the delegated DDF on Active. Do not enter Deliver before then.

### Deliver

Once the session is Completed (`$GATE_CONTROL complete`), enter PackageReady before delivering; Completed is not stage Delivered (`$APPROACH_DELIVER`):

1. Run `$APPROACH_SHELL enter-package-ready`.
2. Run `$APPROACH_DELIVER`. Session Completed authorizes this deliver.

On success, announce stage complete from stdout `next_steps` (join when non-empty).

## Interrupted binding

When any route reports an unresolved binding:

1. Stop and report the binding ID and state from stderr.
2. Wait for an explicit human recovery decision; do not auto-select `compensate-active` or `cancel`.
3. After external recovery, restart the applicable route and obtain fresh command output; do not infer the restored target.
