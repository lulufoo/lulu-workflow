---
name: lulu-approach
---

# lulu-approach

Domain holder for technical diagnostic decisions. It orchestrates `decision`
sessions under approach constraints; scripts own transitions, validation, and
persistence.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-approach` (before Session Foundation)
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

<HARD-GATE>
Do NOT proceed until you have read `../decision/SKILL.md` in full.
All DDF rules, gates, and registers defined there apply to this session.
</HARD-GATE>

`$DECISION_SKILL_DIR` = `$SKILL_ROOT/decision`  
`$APPROACH_ROOT` = `$CACHE_DIR/<cycle_id>/lulu-approach`  
`$MAIN_SESSION_DIR` = `$APPROACH_ROOT/main`

Use `$SKILL_DIR/constraints-$CYCLE_TYPE.json` on every approach and decision
invocation. Do not read session data files for routing.

## Script Macros

### Local approach macros

| Macro | Command |
|-------|---------|
| `$RESOLVE_CONTEXT` | `python3 "$SKILL_DIR/scripts/resolve_context.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json" [--session-dir "<main>"]` |
| `$RESOLVE_CONTEXT_DOCS` | `python3 "$SKILL_DIR/scripts/resolve_context_docs.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` |
| `$RESOLVE_CONSTRAINT_DOCS` | `python3 "$SKILL_DIR/scripts/resolve_constraint_docs.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` |
| `$APPROACH_SHELL` | `python3 "$SKILL_DIR/scripts/approach_shell_control.py" --approach-root "$APPROACH_ROOT"` |
| `$APPROACH_NODE` | `python3 "$SKILL_DIR/scripts/approach_shell_control.py" --approach-root "$APPROACH_ROOT" <subcommand> --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` |
| `$APPROACH_DELIVER` | `python3 "$SKILL_DIR/scripts/approach_shell_control.py" --approach-root "$APPROACH_ROOT" deliver --cycle-id "<cycle_id>" --project-root "$(pwd)"` |

### Imported decision macros

| Macro | Command |
|-------|---------|
| `$DEC_START` | `python3 "$DECISION_SKILL_DIR/scripts/dec_start.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" [--domain-constraints-file "<path>"] [--session-dir "<session_dir>"]` |
| `$DEC_GET_ACTIVE` | `python3 "$DECISION_SKILL_DIR/scripts/dec_active_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" get-active` |
| `$DEC_REOPEN` | `python3 "$DECISION_SKILL_DIR/scripts/dec_reopen.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" [--permit "<permit_path>"]` |
| `$GATE_CONTROL` | `python3 "$DECISION_SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$GET_PAYLOAD` | `python3 "$DECISION_SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" get-payload` |
| `$BATCH_RECLOSE` | `python3 "$DECISION_SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" batch-reclose --payloads '<json object>'` |
| `$REGISTER_CONTROL` | `python3 "$DECISION_SKILL_DIR/scripts/dec_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$REGISTER_COMMIT` | `python3 "$DECISION_SKILL_DIR/scripts/dec_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" register-commit --operations '<json array>'` |
| `$RS_COMMIT` | `python3 "$DECISION_SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" rs-commit --gate "<G>" --operations '<json array>'` |
| `$SESSION_INTEGRITY` | `python3 "$DECISION_SKILL_DIR/scripts/dec_session_integrity.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |

Subcommand and stdout contracts remain in script module docstrings or `--help`.

## Outer spine

```text
Main (node Completed) → PackageReady → stage Delivered
```

Node/session **Completed** (`$GATE_CONTROL complete`) is not approach-stage
**Delivered** (`$APPROACH_DELIVER`). After Main Completes, enter PackageReady
and stage-deliver.

## Load Context (before Main enter)

**Entry:** About to enter Main. Do not call `$DEC_START` yet.

**Act:**

1. Run `$RESOLVE_CONTEXT_DOCS`. Parse stdout for `files`.
2. For each path in `files`, read the file once.
   If `files` is empty, skip reading and continue.
3. Load `$SKILL_DIR/references/context-rules.md`.
4. Apply Context rules for this Main entry:
   - Follow the sections in order
     (Principle → Context materials → Obligation → Body entry → Self-check).
   - Do not classify documents into kinds yourself.

**Done:** Context materials (if any) and Context rules are loaded and applied.

**Stop:** On non-zero output, stop and report stderr.

## Load Constraint (before Main enter)

**Entry:** [Load Context (before Main enter)](#load-context-before-main-enter)
is complete. Do not call `$DEC_START` yet.

**Act:**

1. Run `$RESOLVE_CONSTRAINT_DOCS`. Parse stdout for `files`.
2. For each path in `files`, read the file once.
   If `files` is empty, skip reading and continue.
3. Load `$SKILL_DIR/references/constraint-rules.md`.
4. Apply Constraint rules for this Main entry:
   - Follow the sections in order
     (Principle → Constraint materials → Obligation → Body entry → Self-check).
   - Do not classify documents into kinds yourself.

**Done:** Constraint materials (if any) and Constraint rules are loaded and
applied.

**Stop:** On non-zero output, stop and report stderr.

## Shared context activation

**Entry:** `$DEC_START`, `$APPROACH_NODE enter-node`, or
`$APPROACH_NODE reopen-node` returned `context_docs`.

**Act:** Run `$GATE_CONTROL resolve-context`, read each returned `context_docs`
path once, then declare the active session. Use only the newly pinned `$CTX`.
Do **not** re-run Load Context or Load Constraint.
(Those run only before Main enter.)

**Done:** `$CTX` is pinned, the listed documents are loaded, and the active
session is declared to the user.

**Stop:** On non-zero output, stop and report stderr.

## Main

**Entry:** Session Foundation is complete.

**Act:**

1. Complete [Load Context (before Main enter)](#load-context-before-main-enter).
2. Complete [Load Constraint (before Main enter)](#load-constraint-before-main-enter).
3. Run `$RESOLVE_CONTEXT` with `--session-dir "$MAIN_SESSION_DIR"`; capture
   stdout path as `$RESOLVED_CONTEXT_PATH`.
4. Run `$APPROACH_SHELL init-shell`.
5. Run `$DEC_START` with:

   ```bash
   --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json" \
   --domain-constraints-file "$RESOLVED_CONTEXT_PATH" \
   --session-dir "$MAIN_SESSION_DIR"
   ```

6. Complete [Shared context activation](#shared-context-activation).
   Do **not** re-run Load Context or Load Constraint here.
7. Run the delegated DDF on Active. After the DDF is ready to complete, run
   `$GATE_CONTROL complete`.

**Done:** `main` is **Completed** (node/session). Tell the user this is not
approach-stage **Delivered**.

**Exit:** Continue with
[PackageReady → stage Deliver](#packageready--stage-deliver).

**Stop:** On non-zero output, stop and report stderr. If `$DEC_START` reports a
blocked prior stage, report that stage and do not retry.

## PackageReady → stage Deliver

**Entry:** `main` is Completed.

**Act:**

1. Run `$APPROACH_SHELL enter-package-ready`.
2. Run `$APPROACH_DELIVER --confirm`.
   Main Completed authorizes this deliver. Pass `--confirm` and stage-deliver
   in this step.

**Done:** On `$APPROACH_DELIVER` success, announce stage complete from stdout
`next_steps` (join when non-empty).

**Stop:** On non-zero output, stop and report.

## Reopen paths

Before `$APPROACH_NODE reopen-node --node-id main`, retain the currently
declared source outer state. If it is unknown, stop and report; do not infer it
from files. Until the reopen completes, do not enter PackageReady
or stage deliver.

### Main reopen

**Entry:** The source outer state is known.

**Act:**

1. Complete [Load Context (before Main enter)](#load-context-before-main-enter).
2. Complete [Load Constraint (before Main enter)](#load-constraint-before-main-enter).
3. Run `$APPROACH_NODE reopen-node --node-id main`. Capture stdout
   `permit_path` as `$PERMIT_PATH` and `transaction_id` as `$TRANSACTION_ID`.
4. Complete [Shared context activation](#shared-context-activation).
5. Run `$DEC_REOPEN --permit "$PERMIT_PATH"`, perform RS dialogue, then run
   `$RS_COMMIT --gate "<G>" --operations '<json array>'`.
6. Run `$APPROACH_NODE complete-main-reopen --transaction-id "$TRANSACTION_ID"`.

**Exit:** Continue with
[PackageReady → stage Deliver](#packageready--stage-deliver).

**Done:** Main is repaired.

**Stop:** On non-zero output, stop and report stderr.

### Same-Active restore (Main)

**Entry:** Active remains Main.

**Act:**

1. Complete [Load Context (before Main enter)](#load-context-before-main-enter).
2. Complete [Load Constraint (before Main enter)](#load-constraint-before-main-enter).
3. Run `$APPROACH_NODE enter-node --node-id main`, then complete
   [Shared context activation](#shared-context-activation).

**Done:** Resume Main.

**Stop:** On non-zero output, stop and report stderr.

PackageReady and stage-Delivered are not normal reopen entry states; report an unsupported
state instead.

## Interrupted binding

**Entry:** A normal entry or reopen reports an unresolved binding.

**Act:** Stop and report the binding ID and state from stderr.

**Done:** An explicit human recovery decision is received.

**Stop:** Do not auto-select `commit-focus`, `compensate-active`, or `cancel`.
After external recovery, restart the applicable documented entry route and obtain
fresh command output; do not infer the restored target.
