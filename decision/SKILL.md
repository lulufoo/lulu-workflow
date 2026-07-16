---
name: decision
---

# decision-workflow

> Framework reference: [diagnostic-decision-framework.md](https://github.com/lulufoo/lulu-workflow-framework/blob/main/lulu-dev-workflow/diagnostic/diagnostic-decision-framework.md)

Run a Diagnostic Decision Framework (DDF) session.

---

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`

- Feature identification logic from `## Session Foundation`

- `$SKILL_DIR` = `$SKILL_ROOT/decision`

</HARD-GATE>

---

<HARD-GATE name="Domain Constraints">

**Runtime SSOT:** Pin `$CTX` via `$GATE_CONTROL resolve-context`. Authoritative fields: `domain_constraints` (`objective`, `role`, `domain`, `x_dimensions`, `omitted_sections`), `context`, `after_dc`. Do not infer from holder SKILL prose or memory.

</HARD-GATE>

---

## Script Macros

| Macro | Command |
|-------|---------|
| `$DEC_START` | `python3 "$SKILL_DIR/scripts/dec_start.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>" [--domain-constraints-file "<path>"]` |
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>"` |
| `$REGISTER_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>"` |
| `$REGISTER_COMMIT` | `python3 "$SKILL_DIR/scripts/dec_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>" register-commit --operations '<json array>'` |
| `$RS_COMMIT` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>" rs-commit --gate "<G>" --operations '<json array>'` |
| `$SESSION_INTEGRITY` | `python3 "$SKILL_DIR/scripts/dec_session_integrity.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstrings / `--help`.

---

## Start

**Step 1: Identify active cycle** — `_runtime.md` § Session Foundation. Do not run `$DEC_START` until `$CYCLE_ID` is confirmed.

**Step 2: Run `$DEC_START`** — holder stages **must** pass `--constraints` (path to holder `constraints.json`) and `--stage`. Generic `decision` may omit `--constraints`. Non-zero exit → stop and report stderr.

Every holder SKILL **must** resolve its own `context` (its own `scripts/resolve_context.py` or equivalent, which auto-derives `context.sources` from `(cycle_id, stage)` — see `scripts/context_loading.py`) before calling `$DEC_START`. The resolver writes the result to a file and hands `decision` the file's *path* via `--domain-constraints-file` — never raw JSON on the command line. `decision` performs no path resolution of its own — it only reads that file once, at init, and stores its contents as-is.

On success, follow stdout (new session ready, or legacy session migrated). Do **not** inspect session directory files directly — artifact layout is `$DEC_START` / `init-session` contract (`--help`).

**Archive:** When the platform provides a conversation id, pass `--conversation-id "<id>"` on `$DEC_START`.

When `$DEC_START` receives `--conversation-id`:

1. **Restore:** if this conversation's decision session is in cold storage, move it back to `cache/<cycle_id>/<cache_subdir>/` (from active-context + session snapshot).
2. **Archive:** other conversations with decision-family stages (`decision`, `lulu-bet`, `lulu-approach`) and `session-state: Delivered` are moved to `cache/_archive/<conversation_id>/<cache_subdir>/`.

SSOT for conversation → cycle mapping: platform `active-context.json`. Does **not** use `cache/decision/<conversation_id>/`.

**Do not** run `$DEC_START` again after Delivery (`Delivered`) on the same feature — use a new feature for a new decision session.

---

## Session Flow

**Global gates (non-spine):**

- **G0 · Parallel Registers** — entire session · parallel on hit · spine uninterrupted (see § Gate routing · G0).
- **G9 · Upstream-change detect** — any turn · not parallel · on hit load RS (no dedicated G9 runner).
- **RS · Realign State Handler** — upstream change needs downstream sync · not parallel · LoopA re-entry at align gate `G` (see § Gate routing · RS).

**Spine:** [LoopA] O → Q → E → D → X → R → ([LoopB] V → RR if needed) → DC → `$GATE_CONTROL deliver`.

**Phase grouping** (realign scope):
- [LoopA] O → Q → E → D → X → R — decision construction (realign at Q / E / D / X)
- [LoopB] V → RR — verification release (upstream wrong → RS, not Loop B re-entry)
- [HD] Human Decision — RR exit `human_decision` (see § Gate routing · HD)
- [DC] Delivery Confirmation — terminal gate

### Gate handoff

After a spine runner returns `GATE_COMPLETE`, load the next spine runner per § Gate routing; its pipeline step 1 pins fresh `$CTX`. After `G0_COMPLETE`, resume the active gate dialogue. After `RS_COMPLETE`, load gate `G` runner per § Gate routing (`gates.G.status` is `stale` → follow `$SKILL_DIR/references/stale-gate-update.md`).

### Gate routing

<HARD-GATE>
Before executing any gate, read the corresponding runner SKILL first.
Every spine gate runner pipeline step 1 (`$GATE_CONTROL resolve-context`) is mandatory — it pins `$CTX` for that gate. Do not skip it or rely on memory.
On G0 identification hit during spine or RS subroutine dialogue: load G0 runner before the next user-visible reply; after `G0_COMPLETE`, resume the active gate dialogue.
On G9 hit (any turn: information revises or contradicts a closed gate): do not advance past the hit; load RS runner before `$RS_COMMIT`; after `RS_COMPLETE`, load gate `G` runner per this table.
Do NOT rely on memory or prior context for gate execution steps.
</HARD-GATE>

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
| E | `$SKILL_DIR/runners/e-direction-runner/SKILL.md` | Q closed |
| D | `$SKILL_DIR/runners/d-decision-runner/SKILL.md` | E closed |
| X | `$SKILL_DIR/runners/x-full-diagnosis-runner/SKILL.md` | D closed |
| R | `$SKILL_DIR/runners/r-expose-bets-runner/SKILL.md` | X closed |
| V | `$SKILL_DIR/runners/v-verification-runner/SKILL.md` | R closed · `skipped_gates` empty |
| RR | `$SKILL_DIR/runners/rr-risk-release-runner/SKILL.md` | V closed · RR-scope items |
| DC | `$SKILL_DIR/runners/dc-delivery-runner/SKILL.md` | R exit `dc` or verification complete |
| Human Decision | `$SKILL_DIR/runners/hd-human-decision-runner/SKILL.md` | RR exit `human_decision` |

Gate contracts (dialogue semantics): `$SKILL_DIR/gates/*.md` — each spine/global runner names its contract in Prerequisites; Gate Routing loads runners only, not gate files directly. Global: `g0-parallel-registers.md` · `rs-realign-state-handler.md`. Stale entry: `$SKILL_DIR/references/stale-gate-update.md`.

---

## User-Facing Projection Rules

Before every user-visible reply, project internal workflow **machinery** into user-facing task meaning. Projection controls *identifier visibility only* — it renders gate names, register codes, phase labels, and control flow into task language. It does **not** lower the domain register: technical vocabulary required by `domain_constraints` is preserved.

**Precedence (conflict resolution):** `domain.instruction` > `role.instruction` > this section's plain-language rule. "Plain language" means *do not expose internal identifiers* — never *do not use domain/technical vocabulary*. When "say it plainly" and "use technical terms" appear to conflict, they are on different axes: strip the internal label, keep the technical term.

Use only:

- Pinned `$CTX`
- The active runner/gate contract
- Gate routing next-step information
- `$CTX.domain_constraints`

Do not infer the active phase from conversation wording, visible prompts, or memory.

Do not expose internal identifiers in normal guidance unless the user asks about implementation or failure details are needed.

Render:

- Workflow identifiers as user-facing task meaning
- Completion criteria as the user's needed answer or confirmation
- Remaining internal steps as remaining work, not as internal labels

Apply this projection at stage start, gate handoff, gate questions, confirmation prompts, blocked/override/incomplete/realign messages, and delivery messages.

Do not persist generated display text. `$CTX`, gate contracts, and control command stdout remain the state sources.

---

## Execution Rules

### Core principles

1. **Expose over conclude** — the goal is to surface assumptions and risks. A conclusion is the output of verification, not the target.
2. **User prior over framework** — user's judgments, intuitions, and concerns shape the session; the framework captures and integrates them, does not override them.
3. **Log assumptions immediately** — on identification hit, see § Gate routing · G0.

### Global rules

**G1.** Ask One question at a time — never stack multiple questions in a single message. MUST NOT use checkbox, multiple-choice, or other selection UI.

**G2.** Prefer numbered plain-text options when they help the user answer one clear question; use open-ended prompts when the options cannot be enumerated. Do not use selection UI.

**G3.** Each gate has a pass criterion. Do not advance until the criterion is met.

**G4. Session SSOT** — Do not read session directory data files except reads required by the active runner pipeline (DC runner).

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

**G8. Gate close** — User must confirm explicitly; then `$GATE_CONTROL gate-close`. Conversation-only close does not count.

**G9. Upstream-change detect (global · any turn)** — on any user turn, if information revises or contradicts a **closed** gate's conclusion (pass criterion broken **or** context update), do not ignore it: load RS runner per § Gate routing · G9 → RS. Prefer earliest hit among Q / E / D / X. Not a per-turn full scan — identification-hit style (same family as G0). No dedicated G9 runner.

---

<HARD-GATE name="Session Exit">
Do NOT exit diagnostic or transition to the next stage until:

- All DDF gates (O → Q / E / D / X → R → [LoopB if uncertain: V / RR] → DC) have passed
- `$GATE_CONTROL check-delivery-ready` returns `ready: true`; DC closed; `$GATE_CONTROL deliver` succeeded
- User has explicitly confirmed readiness to proceed

This applies to EVERY intent, regardless of perceived clarity.
"I already know what I want to build" is the most common reason to skip this —
and the most common source of wasted downstream work.
</HARD-GATE>
