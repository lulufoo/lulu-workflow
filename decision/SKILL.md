---
name: decision
---

# decision-workflow

The goal is a delivered Diagnostic Decision Framework session the user has
confirmed. This file starts, routes, and finishes; Signals fire beside the
spine, and each runner owns dialogue.

---

## Runtime Contract

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/decision` (before Session Foundation)
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

<HARD-GATE name="Domain Constraints">

**Runtime SSOT:** Pin `$CTX` via `$GATE_CONTROL resolve-context`. Authoritative
fields: `domain_constraints` (`objective`, `role`, `domain`, `x_dimensions`,
`omitted_sections`), `context`. Do not infer from holder SKILL prose or memory.

</HARD-GATE>

## Script Macros

| Macro | Command |
|-------|---------|
| `$DEC_START` | `python3 "$SKILL_DIR/scripts/dec_start.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" [--conversation-id "<conversation_id>"] [--domain-constraints-file "<path>"] [--session-dir "<session_dir>"]` |
| `$DEC_REOPEN` | `python3 "$SKILL_DIR/scripts/dec_reopen.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" [--permit "<permit_path>"]` |
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$REGISTER_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$REGISTER_COMMIT` | `python3 "$SKILL_DIR/scripts/dec_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" register-commit --operations '<json array>'` |
| `$RS_COMMIT` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" rs-commit --gate "<G>" --operations '<json array>'` |
| `$BATCH_RECLOSE` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" batch-reclose --payloads '<json object>'` |

Subcommand contracts: module docstrings / `--help`. Runner-only macros stay in
that runner.

---

## Start

1. Identify the active cycle through `_runtime.md` § Session Foundation. Do not
   run `$DEC_START` until `$CYCLE_ID` is confirmed.
2. Run `$DEC_START`. Holder stages pass their own `--constraints`; generic
   `decision` may omit it. When the platform provides a conversation ID, pass
   `--conversation-id`.
3. After `$DEC_START` or a holder binding returns `context_docs`: run
   `$GATE_CONTROL resolve-context`; pin `$CTX`; load each returned context
   document once; declare the bound session and use only the new `$CTX`.

Do not run `$DEC_START` again for a session being revised. Freeze with
`$DEC_REOPEN`; keep `Frozen` until RS commits. A holder that requires a reopen
permit owns that flow. Holders own nested-session binding; prior-session
conclusions do not carry over unless re-registered or re-closed.

---

## Router

<HARD-GATE>
Before executing any gate, read that runner SKILL first. Each runner owns its
context rule and map. Do not skip it or rely on memory.
</HARD-GATE>

**Spine:** O → Q → GL → E → D → X → R → DC → `$GATE_CONTROL complete`.
Realign at Q / GL / E / D / X. R exit `human_decision` → HD. R exit `dc` → DC.

After `GATE_COMPLETE`, load the next spine runner. After RS or Batch, load the
runner named by its completion result. S1–S3 load from the table below;
contracts are in Signals.

Dialogue semantics: each runner owns its map. This file only loads runners.

| Gate | File | When |
|------|------|------|
| P | `$SKILL_DIR/runners/p-registers-runner/SKILL.md` | S1 · parallel |
| Scan | `$SKILL_DIR/runners/risk-scan-runner/SKILL.md` | S2 incremental · R full |
| Release | `$SKILL_DIR/runners/risk-release-runner/SKILL.md` | Scan incremental Done · R `handle` |
| RS | `$SKILL_DIR/runners/rs-realign-runner/SKILL.md` | S3 · upstream realign |
| O | `$SKILL_DIR/runners/o-open-channel-runner/SKILL.md` | After `$DEC_START` · `active_gate` is `O` |
| Q | `$SKILL_DIR/runners/q-problem-runner/SKILL.md` | O closed |
| GL | `$SKILL_DIR/runners/gl-grill-runner/SKILL.md` | Q closed |
| E | `$SKILL_DIR/runners/e-direction-runner/SKILL.md` | GL closed |
| D | `$SKILL_DIR/runners/d-decision-runner/SKILL.md` | E closed |
| X | `$SKILL_DIR/runners/x-full-diagnosis-runner/SKILL.md` | D closed |
| R | `$SKILL_DIR/runners/r-expose-bets-runner/SKILL.md` | X closed |
| DC | `$SKILL_DIR/runners/dc-delivery-runner/SKILL.md` | R exit `dc` |
| HD | `$SKILL_DIR/runners/hd-human-decision-runner/SKILL.md` | R exit `human_decision` |

---

## Signals

When both trigger, complete S2 before handling S3.

| ID | Contract |
|----|----------|
| S1 | Any new Register item in dialogue → load P in parallel before replying; resume the current runner on `P_COMPLETE`. |
| S2 | Any new Register write or gate-payload write → use its stdout as Diff; run Scan incremental. |
| S3 | Any new Register write, gate-payload write, or user input that conflicts with a closed conclusion → load RS. |

---

## Cross-gate

### Projection

1. Before every user-visible reply, translate workflow identifiers and control
   flow into task meaning. Hide internal identifiers unless implementation or
   failure details are needed.
2. Preserve `$CTX.domain_constraints` vocabulary. Precedence:
   `domain.instruction > role.instruction > projection rules`.
3. Ground replies in pinned `$CTX`, the active runner's map, Router,
   Signals, and domain constraints. Never infer workflow state from
   conversation or memory.
4. Do not persist projected text. `$CTX`, the active runner's map, and command
   stdout remain the state sources.

### Stance

1. **Expose over conclude** — surface assumptions and risks; a conclusion is
   the output of verification, not the target.
2. **User prior over framework** — capture and integrate the user's judgments;
   do not override them.

### Operating rules

**G1.** One question per message. No checkbox, multiple-choice, or selection UI.

**G2.** Prefer numbered plain-text options when they help answer one question;
use an open prompt when the options cannot be enumerated.

**G3.** Do not advance until the active runner's map holds.

**G4. Session SSOT** — Route only from `$CTX` and macro stdout. Do not read or
write session artifacts directly.

**G5.** If the intent input itself has a fundamental error, exit; tell the user
to fix the input and restart.

**G6. Override Guard** — on "skip" / "just implement it" / equivalent: stop;
state which gates are not yet closed; ask "Continue diagnostic or exit
intentionally?" Confirmed exit → incomplete, exit gracefully.

**G7. Collect-or-Ask** — if the user already stated it: quote, restate, confirm.
Do not re-ask.

---

## Done

<HARD-GATE name="Decision completion">
Do NOT exit decision or transition to the next stage until:

- DC has completed the decision session successfully.
- The user has explicitly confirmed readiness to proceed.

In a holder, this applies to this decision node only. Holder delivery owns the
outer stage transition and delivered references.
</HARD-GATE>
