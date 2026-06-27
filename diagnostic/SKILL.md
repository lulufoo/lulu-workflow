---
name: diagnostic
---

# diagnostic-workflow

> Framework reference: [diagnostic-decision-framework.md](https://github.com/lulufoo/lulu-workflow-framework/blob/main/lulu-dev-workflow/diagnostic/diagnostic-decision-framework.md)

Run a Diagnostic Decision Framework (DDF) session.

---

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`

- Feature identification logic from `## Session Foundation`

- `$SKILL_DIR` = `$SKILL_ROOT/diagnostic`

</HARD-GATE>

---

<HARD-GATE name="Domain Constraints">
**Runtime SSOT:** `$GATE_CONTROL resolve-context` → `domain_constraints` (`x_dimensions`, `omitted_sections`, `role`), `context_loading`, `after_dc`. Do not infer these from holder SKILL prose or memory.

**Role:** If `role.instruction` is present, apply it at the start of gate **O** (Open Channel).

**Context loading (gate O):** Read `$CTX.context_loading` from resolve-context. If `status` is `loaded`, load `resolved_doc_path` read-only and tell the user `loaded_message`.

**After DC:** Tell the user `$CTX.after_dc.user_message` (next steps from `config/transition-table.json`).
</HARD-GATE>

---

## Script Macros

| Macro | Command |
|-------|---------|
| `$DX_START` | `python3 "$SKILL_DIR/scripts/dx_start.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>"` |
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dx_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>"` |
| `$REGISTER_CONTROL` | `python3 "$SKILL_DIR/scripts/dx_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>"` |
| `$REGISTER_COMMIT` | `python3 "$SKILL_DIR/scripts/dx_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>" register-commit --operations '<json array>'` |
| `$RS_COMMIT` | `python3 "$SKILL_DIR/scripts/dx_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>" rs-commit --gate "<G>" --operations '<json array>'` |

Subcommand contracts: module docstrings / `--help`.

---

## Start

**Step 1: Identify active cycle** — `_runtime.md` § Session Foundation. Do not run `$DX_START` until `$CYCLE_ID` is confirmed.

**Step 2: Run `$DX_START`** — holder stages **must** pass `--constraints` (path to holder `constraints.json`) and `--stage`. Generic `diagnostic` may omit `--constraints`. Non-zero exit → stop and report stderr.

On success, follow stdout (new session ready, or legacy session migrated). Do **not** inspect session directory files directly — artifact layout is `$DX_START` / `init-session` contract (`--help`).

**Archive:** When the platform provides a conversation id, pass `--conversation-id "<id>"` on `$DX_START`.

When `$DX_START` receives `--conversation-id`:

1. **Restore:** if this conversation's diagnostic session is in cold storage, move it back to `cache/<cycle_id>/<cache_subdir>/` (from active-context + session snapshot).
2. **Archive:** other conversations with diagnostic-family stages (`diagnostic`, `product-diagnostic`, `tech-diagnostic`) and `session-state: Delivered` are moved to `cache/_archive/<conversation_id>/<cache_subdir>/`.

SSOT for conversation → cycle mapping: platform `active-context.json`. Does **not** use `cache/diagnostic/<conversation_id>/`.

**Do not** run `$DX_START` again after Delivery (`Delivered`) on the same feature — use a new feature for a new diagnostic.

---

## Session Flow

**Global gates (non-spine):**

- **G0 · Parallel Registers** — entire session · parallel on hit · spine uninterrupted (see § Gate routing · G0).
- **RS · Reopen State Handler** — any gate on invalidation · not parallel · LoopA re-entry (see § Gate routing · RS).

**Spine:** [LoopA] O → Q → E → D → X → R → ([LoopB] V → RR if needed) → DC → `$GATE_CONTROL deliver`.

**Phase grouping** (invalidate scope):
- [LoopA] O → Q → E → D → X → R — decision construction (reopen at Q / E / D / X)
- [LoopB] V → RR — verification release (upstream wrong → RS, not Loop B re-entry)
- [HD] Human Decision — RR exit `human_decision` (see § Gate routing · HD)
- [DC] Delivery Confirmation — terminal gate

### Gate handoff

After a spine runner returns `GATE_COMPLETE`, load the next spine runner per § Gate routing; its pipeline step 1 pins fresh `$CTX`. After `G0_COMPLETE`, resume the active gate dialogue. After `RS_COMPLETE`, load gate `G` runner per § Gate routing.

### Gate routing

<HARD-GATE>
Before executing any gate, read the corresponding runner SKILL first.
Every spine gate runner pipeline step 1 (`$GATE_CONTROL resolve-context`) is mandatory — it pins `$CTX` for that gate. Do not skip it or rely on memory.
On G0 identification hit during spine or RS subroutine dialogue: load G0 runner before the next user-visible reply; after `G0_COMPLETE`, resume the active gate dialogue.
On invalidation trigger: do not `gate-close`; load RS runner before `$RS_COMMIT`; after `RS_COMPLETE`, load gate `G` runner per this table.
Do NOT rely on memory or prior context for gate execution steps.
</HARD-GATE>

Global gates:

| Gate | File | Load condition |
|------|------|----------------|
| **G0** | `$SKILL_DIR/runners/g0-parallel-registers-runner/SKILL.md` | Identification hit · **parallel** |
| **RS** | `$SKILL_DIR/runners/rs-reopen-runner/SKILL.md` | Invalidation · **not parallel** |

Spine gates:

| Gate | File | Load condition |
|------|------|----------------|
| O | `$SKILL_DIR/runners/o-open-channel-runner/SKILL.md` | After `$DX_START` · `active_gate` is `O` |
| Q | `$SKILL_DIR/runners/q-problem-runner/SKILL.md` | O closed |
| E | `$SKILL_DIR/runners/e-direction-runner/SKILL.md` | Q closed |
| D | `$SKILL_DIR/runners/d-decision-runner/SKILL.md` | E closed |
| X | `$SKILL_DIR/runners/x-full-diagnosis-runner/SKILL.md` | D closed |
| R | `$SKILL_DIR/runners/r-expose-bets-runner/SKILL.md` | X closed |
| V | `$SKILL_DIR/runners/v-verification-runner/SKILL.md` | R closed · `skipped_gates` empty |
| RR | `$SKILL_DIR/runners/rr-risk-release-runner/SKILL.md` | V closed · RR-scope items |
| DC | `$SKILL_DIR/runners/dc-delivery-runner/SKILL.md` | R exit `dc` or verification complete |
| Human Decision | `$SKILL_DIR/runners/hd-human-decision-runner/SKILL.md` | RR exit `human_decision` |

Gate contracts (dialogue semantics): `$SKILL_DIR/gates/*.md` — each spine/global runner names its contract in Prerequisites; Gate Routing loads runners only, not gate files directly. Global: `g0-parallel-registers.md` · `rs-reopen-state-handler.md`.

---

## User-Facing Projection Rules

Before every user-visible reply, project internal workflow state into plain-language task wording.

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

Apply this projection at stage start, gate handoff, gate questions, confirmation prompts, blocked/override/incomplete/invalidation messages, and delivery messages.

Do not persist generated display text. `$CTX`, gate contracts, and control command stdout remain the state sources.

---

## Execution Rules

### Core principles

1. **Expose over conclude** — the goal is to surface assumptions and risks. A conclusion is the output of verification, not the target.
2. **User prior over framework** — user's judgments, intuitions, and concerns shape the session; the framework captures and integrates them, does not override them.
3. **Log assumptions immediately** — on identification hit, see § Gate routing · G0.

### Global rules

**G1.** Ask One question at a time — never stack multiple questions in a single message. MUST NOT use checkbox, multiple-choice, button, or other selection UI.

**G2.** Multiple choice preferred; open-ended is fine when options are not enumerable.

**G3.** Each gate has a pass criterion. Do not advance until the criterion is met.

**G4. Context refresh** — Pin `$CTX` from the active gate runner pipeline step 1 (`resolve-context`), or from G0 `$REGISTER_COMMIT` / `$RS_COMMIT` stdout when those run. Do not chain an extra `resolve-context` after those commands. Do **not** show `reply_header` or hand-write gate/register status blocks; read `gates` / `registers` from `$CTX` only. Do **not** read session data files directly.

**G4b. Gate persistence** — Closing a gate requires `$GATE_CONTROL gate-close` after G8 user confirmation. Do not mark a gate closed in conversation only.

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

**G8. Gate confirmation (all gates)** — AI cannot unilaterally declare a gate as passed. Each gate requires an explicit user confirmation step before it closes. Silence does not constitute confirmation.

**G9. Reopen check at gate close** — before closing any gate, check: does the evidence gathered in this gate invalidate any prior gate's pass criterion? If yes, do not close current gate; load RS runner per § Gate routing · RS.

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
