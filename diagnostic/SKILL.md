---
name: diagnostic
---

# diagnostic-workflow

> Framework reference: [diagnostic-decision-framework.md](https://github.com/lulufoo/lulu-workflow-framework/blob/main/lulu-dev-workflow/diagnostic/diagnostic-decision-framework.md)

Run a Diagnostic Decision Framework (DDF) session. **Mandatory before starting `/product-plan` or `/tech-plan`.**

---

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/diagnostic`

---

<HARD-GATE name="Domain Constraints">
**Runtime SSOT:** `$GATE_CONTROL resolve-context` → `domain_constraints` (`x_dimensions`, `omitted_sections`, `role`). Do not infer these from holder prose or memory.

**Role:** If `role.instruction` is present, apply it at the start of gate **O** (Open Channel).

**Holder prose** (when holder `## Domain Constraints` is in context): follow holder `### Context Loading` during gate **O** and `### After DC` at DC routing.

**Direct `/diagnostic`** (no holder section): built-in defaults at `$DX_START`; after DC, tell the user they may proceed to `/product-plan` or `/tech-plan`.
</HARD-GATE>

---

## Script Macros

| Macro | Command |
|-------|---------|
| `$DX_START` | `python3 "$SKILL_DIR/scripts/dx_start.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>"` |
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dx_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>"` |
| `$REGISTER_CONTROL` | `python3 "$SKILL_DIR/scripts/dx_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>"` |
| `$REGISTER_COMMIT` | `python3 "$SKILL_DIR/scripts/dx_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" register-commit --operations '<json array>'` |
| `$RS_COMMIT` | `python3 "$SKILL_DIR/scripts/dx_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" rs-commit --gate "<G>" --operations '<json array>'` |

Subcommand contracts: module docstrings / `--help`.

---

## Start

**Step 1: Identify active cycle** — `_runtime.md` § Session Foundation. Do not run `$DX_START` until `$CYCLE_ID` is confirmed.

**Step 2: Run `$DX_START`** — pass `--stage` when the invoking holder SKILL specifies one; otherwise omit (defaults to `diagnostic`). Non-zero exit → stop and report stderr.

On success, follow stdout (new session ready, or legacy session migrated). Do **not** inspect session directory files directly — artifact layout is `$DX_START` / `init-session` contract (`--help`).

**Archive:** When the platform provides a conversation id, pass `--conversation-id "<id>"` on `$DX_START`.

**Do not** run `$DX_START` again after Delivery (`Delivered`) on the same feature — use a new feature for a new diagnostic.

---

## Session Flow

**Spine:** [LoopA] O → Q → E → D → X → R → ([LoopB] V → RR if needed) → DC → `$GATE_CONTROL deliver`.

**Phase grouping** (re-open invalidate scope):
- [LoopA] O → Q → E → D → X → R — decision construction
- [LoopB] V → RR — verification release
- [RS] Reopen State Handler — standalone subroutine (see § Re-open & Invalidation)
- [DC] Delivery Confirmation — terminal gate

### Between gates

After each runner returns `GATE_COMPLETE`, run `$GATE_CONTROL resolve-context` before loading the next runner. Pin `$CTX` for routing (`active_gate`, `skipped_gates`, `gates`, `registers`, `domain_constraints`). Do **not** paste `reply_header` to the user — persistence is via `$GATE_CONTROL` / `$REGISTER_CONTROL` only.

### Gate routing

<HARD-GATE>
Before executing any gate, read the corresponding runner SKILL first.
Do NOT rely on memory or prior context for gate execution steps.
</HARD-GATE>

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
| RS | `$SKILL_DIR/runners/rs-reopen-runner/SKILL.md` | Reopen triggered (any gate / DC flag / R exit `rs`) |
| Human Decision | `$SKILL_DIR/runners/hd-human-decision-runner/SKILL.md` | RR exit `human_decision` |

Gate contracts (dialogue semantics): `$SKILL_DIR/gates/*.md` — read via runner reference.

---

## Parallel Registers

Two logs run in parallel for the entire session (not owned by a single gate):

- **User Prior** — user judgments, preferences, concerns, excluded options
- **Assumption** — unverified premises underlying the decision

### G0 — when to capture (Agent)

<HARD-GATE name="G0 capture">
If any row below applies in the current turn, persist via `$REGISTER_COMMIT` successfully before the next user-visible reply continues the gate.
</HARD-GATE>

| Surface in dialogue | Log | Extra rule |
|---------------------|-----|------------|
| Judgment / preference / concern / excluded option | Prior | If it rests on an unverified premise → also add Assumption |
| Explicit or implicit unverified premise | Assumption | Do not defer to R |
| Gate contract requires logging (e.g. X gap, unknown dependency) | Assumption | Immediate |

**Flow:** brief confirm with user → `$REGISTER_COMMIT` with one or more append/update operations (non-zero → stop gate) → pin `$CTX` from stdout → continue dialogue.

**Prohibited:** deferring capture because R is coming; hand-editing register state in prose; reading or writing register data files directly; chaining `register-append` / `register-update` / `sync-registers-to-doc` / `resolve-context` separately for G0.

Gate contracts may add mandatory capture moments — follow those in addition to this table.

### When to read (not collect)

| Moment | Action |
|--------|--------|
| Before D | Review User Prior from `$CTX.registers` — resolve conflicts with chosen direction |
| At R | Organize and sign off priors; risk-grade assumptions — via R `gate-close` payload, not fresh G0 collection |
| After gate-close or when no G0 write in turn | `$GATE_CONTROL resolve-context` → pin `$CTX` (G4) |

### Persistence (script SSOT)

| Path | Macro | Notes |
|------|-------|-------|
| G0 capture / inline edit | `$REGISTER_COMMIT` | stdout = full `$CTX` (registers + gates); satisfies G4 for G0 |
| R / V / RR bulk field updates | `$GATE_CONTROL gate-close` | Coupled to gate transition — not separable |
| RS batch | `$RS_COMMIT` | See § Re-open & Invalidation |
| Read only | `$CTX.registers` | From last `$REGISTER_COMMIT`, `gate-close`, or `resolve-context` stdout |

If any register CLI exits non-zero: stop the current gate and report the error.

Subcommand contracts: `$REGISTER_COMMIT` via `$REGISTER_CONTROL --help` (`register-commit`).

---

## Execution Rules

### Core principles

1. **Expose over conclude** — the goal is to surface assumptions and risks. A conclusion is the output of verification, not the target.
2. **User prior over framework** — user's judgments, intuitions, and concerns shape the session; the framework captures and integrates them, does not override them.
3. **Log assumptions immediately** — see § Parallel Registers · G0 capture; R organizes, does not collect.

### Global rules

**G0.** User prior / assumption capture — see § Parallel Registers · G0 capture.

**G1.** One question at a time — never stack multiple questions in a single message.

**G2.** Multiple choice preferred; open-ended is fine when options are not enumerable.

**G3.** Each gate has a pass criterion. Do not advance until the criterion is met.

**G4. Context refresh** — after any gate state change, or after G0 when not using `$REGISTER_COMMIT`, run `$GATE_CONTROL resolve-context` successfully and pin `$CTX` before the next user-visible reply. `$REGISTER_COMMIT` and `$RS_COMMIT` stdout already include full `$CTX`. Do **not** show `reply_header` or hand-write gate/register status blocks; read `gates` / `registers` from `$CTX` only. Do **not** read session data files directly.

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

**G9. Reopen check at gate close** — before closing any gate, check: does the evidence gathered in this gate invalidate any prior gate's pass criterion? If yes, do not close current gate; trigger RS per § Re-open & Invalidation.

---

## Re-open & Invalidation

> Global rules — any gate, any time. RS dialogue and register proposals:
> `$SKILL_DIR/runners/rs-reopen-runner/SKILL.md` + `gates/rs-reopen-state-handler.md`.

### When to reopen (Trigger)

- Any participant may trigger reopen when a **prior gate's pass criterion no longer holds** — without waiting for V.
- Loop B discovering upstream is wrong → RS (not a Loop B re-entry).
- **G9:** before gate-close, check whether this gate's evidence invalidates any prior gate; if yes → do not gate-close; trigger RS.
- Agent duties: detect reopen need, propose reopen gate `G` (Q / E / D / X), obtain G8 confirmation.
- Agent **must not** manually mark gates invalidated, edit gate-state, or enumerate downstream gates.

### Consequences (script SSOT)

- Gate and decision-doc downstream invalidation: **`$GATE_CONTROL` only**; scope computed by DAG — agent does not enumerate.
- Registers are **not** auto-modified by gate invalidation (see § Parallel Registers · Persistence).
- Re-entry point after RS: **Loop A gate `G`** (Q / E / D / X), not V / RR.
- Loop B-only new assumptions while Loop A still holds → RR `return_r` back to R; not RS.

### RS subroutine

After trigger and G8 confirm reopen gate `G`:

1. Load `$SKILL_DIR/runners/rs-reopen-runner/SKILL.md`
2. Runner: baseline `$CTX` → propose register 3-state labels → G8 → **`$RS_COMMIT`**
3. Pin `$CTX` from `$RS_COMMIT` stdout; load gate `G` runner via § Gate routing

<HARD-GATE name="RS commit">
- Do **not** call `$RS_COMMIT` before G8 confirms `G` and register operations.
- Non-zero exit → stop RS, report stderr, wait for user direction.
- After success, read `reenter`, `gates`, `registers` from stdout only — do not chain `invalidate-from` / `register-batch-apply` / `sync-registers-to-doc` separately for RS.
</HARD-GATE>

Subcommand contracts: `$RS_COMMIT` via `$GATE_CONTROL --help` (`rs-commit`).

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
