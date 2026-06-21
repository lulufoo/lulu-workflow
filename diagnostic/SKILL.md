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

Two registers run throughout the entire session, not attached to any single gate:

**User Prior Log** — captures user's judgments, preferences, concerns, and excluded options. Reviewed before D; verified at R (R签字确认).

**Assumption Log** — captures unverified premises. Risk-graded at R; not collected from scratch there.

**3-state lifecycle:** `[待验证]` (default) → `[已验证]` (confirmed at R or after Risk Release) → `[失效]` (deleted via RS § Register Reopen Protocol)

**Field semantics** (in `$CTX.registers` after `resolve-context`):
- `<state>`: `?` = 待验证 · `✓` = 已验证
- `<source>`: gate where first discovered — `O` / `Q` / `E` / `D` / `X` / `R` / `V` / `RR`
- `<risk>`: `H`/`M`/`L` — assigned at R; omitted until then

**On reopen:** register entries are not auto-modified by DAG propagation — changes only occur when RS runs with user-confirmed `register-batch-apply`.

<HARD-GATE name="Register SSOT">
- Prior and Assumption data SSOT: `$REGISTER_CONTROL` + `$CTX.registers` (via `resolve-context`). Incremental capture and edits use `$REGISTER_CONTROL` only (`register-append`, `register-update`, `register-batch-apply`, `sync-registers-to-doc`).
- After G0 capture (Prior or Assumption), call `register-append` or `register-update` successfully before the next user-visible reply continues the gate.
- Batch register updates at R / V / RR gate-close are applied via `$GATE_CONTROL gate-close` payload (not a separate `$REGISTER_CONTROL` call).
- If any register CLI exits non-zero: stop the current gate and report the error.
</HARD-GATE>

| Operation | Command |
|-----------|---------|
| G0 append prior / assumption | `$REGISTER_CONTROL register-append --kind prior\|assumption` |
| Single-field update | `$REGISTER_CONTROL register-update` |
| RS batch relabel / delete | `$REGISTER_CONTROL register-batch-apply` |
| Sync registers into decision-doc | `$REGISTER_CONTROL sync-registers-to-doc` |

Subcommand contracts: `$REGISTER_CONTROL --help` (and `$GATE_CONTROL --help` where applicable).

---

## Execution Rules

### Core principles

1. **Expose over conclude** — the goal is to surface assumptions and risks. A conclusion is the output of verification, not the target.
2. **User prior over framework** — user's judgments, intuitions, and concerns shape the session; the framework captures and integrates them, does not override them.
3. **Log assumptions immediately** — any assumption surfaced at any gate goes into the Assumption Log right away; R organizes, does not collect.

### Global rules

**G0. User prior capture (throughout)** — at any gate, if the user states a judgment, preference, concern, or excluded option: confirm briefly, then capture per § Parallel Registers (`register-append`) before continuing. When a `[judgment]` or `[excluded]` rests on an unverified premise, extract the premise as a separate Assumption entry (`[待验证]`, source = current gate).

**G1.** One question at a time — never stack multiple questions in a single message.

**G2.** Multiple choice preferred; open-ended is fine when options are not enumerable.

**G3.** Each gate has a pass criterion. Do not advance until the criterion is met.

**G4. Context refresh** — after any register or gate state change, run `$GATE_CONTROL resolve-context` successfully and pin `$CTX` before the next user-visible reply. Do **not** show `reply_header` or hand-write gate/register status blocks; read `gates` / `registers` from `$CTX` only. Do **not** read session data files directly.

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

Two global rules, applicable at any gate, any time:

**Trigger:** Any participant (AI or user) can re-open a prior gate the moment new information shows its pass criterion no longer holds — without waiting for V.

**Propagation:**
- When a gate is re-opened, all gates reachable from it along prerequisite dependency arrows are automatically invalidated and must be re-satisfied.
- Scope is determined by the DAG structure — no enumeration needed.
- When a reopen trigger fires, load and execute `$SKILL_DIR/runners/rs-reopen-runner/SKILL.md` (gate contract: `gates/rs-reopen-state-handler.md`).

**RS mechanical steps** (do not skip):
1. `$GATE_CONTROL invalidate-from --gate <G>`
2. User-confirmed register relabeling → `$REGISTER_CONTROL register-batch-apply`
3. `$REGISTER_CONTROL sync-registers-to-doc` + `$GATE_CONTROL resolve-context` (refresh `$CTX` — G4)
4. Re-enter LoopA at gate `<G>` via § Gate routing

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
