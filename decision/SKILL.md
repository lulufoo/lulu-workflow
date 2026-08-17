---
name: decision
---

# decision-workflow

> Framework reference: the local decision runners, scripts, and templates shipped with this skill.

Run a Diagnostic Decision Framework (DDF) session.

---

## Runtime Contract

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`

- `$SKILL_DIR` = `$SKILL_ROOT/decision` (before Session Foundation)

- Feature identification logic from `## Session Foundation`

- `../_subagent.md` — `$SUBAGENT_*` (DC Eval probe)

</HARD-GATE>

<HARD-GATE name="Domain Constraints">

**Runtime SSOT:** Pin `$CTX` via `$GATE_CONTROL resolve-context`. Authoritative fields: `domain_constraints` (`objective`, `role`, `domain`, `x_dimensions`, `omitted_sections`), `context`. Do not infer from holder SKILL prose or memory.

</HARD-GATE>

## Script Macros

| Macro | Command |
|-------|---------|
| `$DEC_START` | `python3 "$SKILL_DIR/scripts/dec_start.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" [--conversation-id "<conversation_id>"] [--domain-constraints-file "<path>"] [--session-dir "<session_dir>"]` |
| `$DEC_GET_ACTIVE` | `python3 "$SKILL_DIR/scripts/dec_active_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" get-active` |
| `$DEC_REOPEN` | `python3 "$SKILL_DIR/scripts/dec_reopen.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" [--permit "<permit_path>"]` |
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$GET_PAYLOAD` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" get-payload` |
| `$BATCH_RECLOSE` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" batch-reclose --payloads '<json object>'` |
| `$REGISTER_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$REGISTER_COMMIT` | `python3 "$SKILL_DIR/scripts/dec_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" register-commit --operations '<json array>'` |
| `$RS_COMMIT` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" rs-commit --gate "<G>" --operations '<json array>'` |
| `$SESSION_INTEGRITY` | `python3 "$SKILL_DIR/scripts/dec_session_integrity.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$DEC_EVAL` | `python3 "$SKILL_DIR/scripts/dec_eval_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$EVAL_CONTROL` | `python3 "$SKILL_ROOT/eval/scripts/eval_entry.py" --adapter-config-file "$SKILL_DIR/eval/eval-profile.json" --project-root "$(pwd)" --cycle-id "<cycle_id>"` |

Subcommand contracts: module docstrings / `--help`.

---

## Session Lifecycle

### Start

1. Identify the active cycle through `_runtime.md` § Session Foundation. Do not
   run `$DEC_START` until `$CYCLE_ID` is confirmed.
2. Run `$DEC_START`. Holder stages pass their own `--constraints`; generic
   `decision` may omit it. When the platform provides a conversation ID, pass
   `--conversation-id`.

Holders resolve and supply their own context inputs. Archive, restore, and
session-path mechanics belong to the lifecycle scripts and holder SKILLs.

### Reopen

Do not run `$DEC_START` again for a session being revised. When revision must
freeze the active session, use `$DEC_REOPEN`; keep it `Frozen` until RS commits
realignment. A holder that requires a reopen permit owns the permit flow.

### Context activation

After `$DEC_START` or a holder binding action returns `context_docs`:

1. Run `$GATE_CONTROL resolve-context`; pin `$CTX`.
2. Load each returned context document once.
3. Declare the bound decision session, then use only the new `$CTX`.

Holder SKILLs own nested-session navigation and binding. A binding changes the
decision I/O subject; conclusions from the prior session do not carry over
unless re-registered or re-closed.

---

## Workflow Router

### Topology

- **G0 · Parallel Registers** — entire session · parallel on hit · spine uninterrupted (see § Gate routing · G0).
- **G9 · Upstream-change detect** — any turn · not parallel · on hit load RS (no dedicated G9 runner).
- **RS · Realign State Handler** — upstream change needs downstream sync · not parallel · LoopA re-entry at align gate `G` (see § Gate routing · RS).

**Spine:** [LoopA] O → Q → GL → E → D → X → R → DC → `$GATE_CONTROL complete`.

**Phase grouping** (realign scope):
- [LoopA] O → Q → GL → E → D → X → R — decision construction (realign at Q / GL / E / D / X)
- [HD] Human Decision — R exit `human_decision` (see § Gate routing · HD)
- [DC] Delivery Confirmation — terminal gate

### Runner handoff

<HARD-GATE>
Before executing any gate, read the corresponding runner SKILL first. Each
runner owns its context acquisition or reuse rule. Do not skip it or rely on
memory.
</HARD-GATE>

1. After `GATE_COMPLETE`, load the next spine runner per the table.
2. On an eligible G0 identification hit, load G0 before the next user-visible
   reply. After `G0_COMPLETE`, resume the interrupted flow.
3. On G9, load RS before `$RS_COMMIT`. After RS or Batch completion, load the
   runner named by its completion result.

### Gate routing

Global gates:

| Gate | File | Load condition |
|------|------|----------------|
| **G0** | `$SKILL_DIR/runners/g0-parallel-registers-runner/SKILL.md` | Identification hit · **parallel** |
| **G9** | _(no runner)_ → load **RS** | Any turn: revise/contradict a closed gate · **not parallel** |
| **RS** | `$SKILL_DIR/runners/rs-realign-runner/SKILL.md` | Upstream change → realign · **not parallel** |

Spine gates:

| Gate | File | Load condition |
|------|------|----------------|
| O | `$SKILL_DIR/runners/o-open-channel-runner/SKILL.md` | After `$DEC_START` · `active_gate` is `O` |
| Q | `$SKILL_DIR/runners/q-problem-runner/SKILL.md` | O closed |
| GL | `$SKILL_DIR/runners/gl-grill-runner/SKILL.md` | Q closed |
| E | `$SKILL_DIR/runners/e-direction-runner/SKILL.md` | GL closed |
| D | `$SKILL_DIR/runners/d-decision-runner/SKILL.md` | E closed |
| X | `$SKILL_DIR/runners/x-full-diagnosis-runner/SKILL.md` | D closed |
| R | `$SKILL_DIR/runners/r-expose-bets-runner/SKILL.md` | X closed |
| DC | `$SKILL_DIR/runners/dc-delivery-runner/SKILL.md` | R exit `dc` |
| Human Decision | `$SKILL_DIR/runners/hd-human-decision-runner/SKILL.md` | R exit `human_decision` |

Dialogue semantics SSOT: each runner owns its Cognitive map. Gate routing loads
runners only.

---

## Cross-Gate Rules

### User-facing projection

1. **Task meaning** — Before every user-visible reply, translate workflow
   identifiers, completion conditions, and control flow into user-facing task
   meaning.
2. **Technical precision** — Hide internal identifiers unless implementation or
   failure details are needed. Preserve vocabulary required by
   `$CTX.domain_constraints`; precedence is
   `domain.instruction > role.instruction > projection rules`.
3. **State-grounded** — Ground replies in pinned `$CTX`, the active runner's
   Cognitive map, gate routing, and domain constraints. Never infer workflow
   state from conversation or memory.
4. **Display only** — Do not persist projected text. `$CTX`, the active
   Cognitive map, and command stdout remain the state sources.

### Global operating rules

1. **Expose over conclude** — the goal is to surface assumptions and risks. A conclusion is the output of verification, not the target.
2. **User prior over framework** — user's judgments, intuitions, and concerns shape the session; the framework captures and integrates them, does not override them.

**G1.** Ask One question at a time — never stack multiple questions in a single message. MUST NOT use checkbox, multiple-choice, or other selection UI.

**G2.** Prefer numbered plain-text options when they help the user answer one clear question; use open-ended prompts when the options cannot be enumerated. Do not use selection UI.

**G3.** Each gate has a pass criterion. Do not advance until the criterion is met.

**G4. Session SSOT** — Route only from `$CTX` and macro stdout. Do not read or
write session artifacts directly.

**G5.** Upstream input error — if the intent input itself has a fundamental error, exit the loop; tell the user to fix the input and restart.

**G6. Override Guard (reactive)** — when override signal detected ("skip" / "just implement it" / etc.):
1. Stop immediately — do not execute
2. State which gates are not yet closed
3. Ask: "Continue diagnostic or exit intentionally?"

If user confirms exit → exit gracefully; mark as incomplete.

**G7. Collect-or-Ask** (applies to all information-gathering):
1. Check: is this information already explicitly stated by user?
2. Yes → quote original + restate + confirm ("Is this correct?")
3. No → ask normally

**Prohibited:** re-asking information already stated.

**G9. Upstream-change detect (global · any turn)** — on any user turn, if
information revises or contradicts a closed gate's conclusion, load RS per
§ Workflow Router. RS determines the realign point. This is an
identification-hit check, not a per-turn full scan.

---

## Completion & Holder Handoff

<HARD-GATE name="Decision completion">
Do NOT exit decision or transition to the next stage until:

- DC runner has completed the decision session successfully.
- The user has explicitly confirmed readiness to proceed.

In a holder, completion applies to this decision node only. Holder delivery owns
the outer stage transition and delivered references.

This applies to EVERY intent, regardless of perceived clarity.
"I already know what I want to build" is the most common reason to skip this —
and the most common source of wasted downstream work.
</HARD-GATE>
