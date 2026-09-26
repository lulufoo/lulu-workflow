---
name: decision
---

# decision-workflow

The goal is a delivered Diagnostic Decision Framework session the user has confirmed. This file starts, routes, and finishes; Signals fire beside the spine, and each runner owns dialogue.

---

## Principles

1. **Fully expose risks** — surface risks arising from any Prior, Constraint, or Assumption.
2. **Clear unresolved doubts** — offer `/converge` when doubts remain.
3. **Respect evidence boundaries** — never present an unverified premise as a verified conclusion.
4. **User prior over framework** — integrate the user's judgments; never let the framework override them.

---

## Contract

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/decision` (before Session Foundation)
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

<HARD-GATE name="Domain Constraints">

1. Pin `$CTX` via `$GATE_CONTROL resolve-context`.
2. Apply `$CTX.domain_constraints` (`objective`, `role`, `domain`, `x_dimensions`, `omitted_sections`) to the session.
3. Do not infer domain constraints from holder SKILL prose or memory.

</HARD-GATE>

## Script Macros

| Macro | Command |
|-------|---------|
| `$DEC_START` | `python3 "$SKILL_DIR/scripts/dec_start.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" [--conversation-id "<conversation_id>"] [--domain-constraints-file "<path>"] [--session-dir "<session_dir>"]` |
| `$DEC_REOPEN` | `python3 "$SKILL_DIR/scripts/dec_reopen.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" [--permit "<permit_path>"]` |
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$GET_PAYLOAD` | `$GATE_CONTROL get-payload` |
| `$REGISTER_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$REGISTER_COMMIT` | `python3 "$SKILL_DIR/scripts/dec_register_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" register-commit --operations '<json array>'` |
| `$RS_COMMIT` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" rs-commit --gate "<G>" --operations '<json array>'` |
| `$BATCH_RECLOSE` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" batch-reclose --payloads '<json object>'` |

Subcommand contracts: module docstrings / `--help`. Loaded runners inherit these
macros; runner-only macros stay local.

---

## Start

1. Identify the active cycle through `_runtime.md` § Session Foundation. Do not run `$DEC_START` until `$CYCLE_ID` is confirmed.
2. Run `$DEC_START`. Holder stages pass their own `--constraints`; generic `decision` may omit it. When the platform provides a conversation ID, pass `--conversation-id`.
3. After `$DEC_START` or a holder binding returns `context_docs`: run `$GATE_CONTROL resolve-context`; pin `$CTX`; load each returned context document once; declare the bound session and use only the new `$CTX`.

---

## Router

<HARD-GATE>
Load the routed runner before execution; never rely on memory. The runner owns its context and dialogue map.
Route only from `$CTX` and macro stdout; never access session artifacts directly.
</HARD-GATE>

**Spine:** O → Q → GL → E → D → X → R → DC → `$GATE_CONTROL complete`.

**Dispatch:** `GATE_COMPLETE` → next spine runner; RS / Batch → returned runner. Signals route P / Scan / RS. Scan incremental `open` or R `handle` → Release.

**Global**

| Route | Runner |
|-------|--------|
| P | `$SKILL_DIR/runners/p-registers-runner/SKILL.md` |
| RS | `$SKILL_DIR/runners/rs-realign-runner/SKILL.md` |

**Gate**

| Route | Runner |
|-------|--------|
| O | `$SKILL_DIR/runners/o-open-channel-runner/SKILL.md` |
| Q | `$SKILL_DIR/runners/q-problem-runner/SKILL.md` |
| GL | `$SKILL_DIR/runners/gl-grill-runner/SKILL.md` |
| E | `$SKILL_DIR/runners/e-direction-runner/SKILL.md` |
| D | `$SKILL_DIR/runners/d-decision-runner/SKILL.md` |
| X | `$SKILL_DIR/runners/x-full-diagnosis-runner/SKILL.md` |
| R | `$SKILL_DIR/runners/r-expose-bets-runner/SKILL.md` |
| DC | `$SKILL_DIR/runners/dc-delivery-runner/SKILL.md` |

**Tools**

| Route | Runner |
|-------|--------|
| Scan | `$SKILL_DIR/runners/risk-scan-runner/SKILL.md` |
| Release | `$SKILL_DIR/runners/risk-release-runner/SKILL.md` |
| HD | `$SKILL_DIR/runners/hd-human-decision-runner/SKILL.md` |

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

1. Speak in task terms; name internal IDs only for implementation or failure.
2. Preserve `$CTX.domain_constraints` vocabulary. Precedence: `domain.instruction > role.instruction > projection rules`.
3. Projected text is presentation only; never persist it.

### Operating rules

**G1.** Ask one question at a time. Apply the full [Ask Protocol](../shared/references/ask-protocol.md) only where the active runner binds it.

**G2.** Advance only when the active runner's map holds.

**G3.** Bypassing unclosed gates requires explicit user confirmation; confirmed exit ends incomplete.

---

## Freeze and Resume

`Frozen` is external-revision-only; `$RS_COMMIT` releases it. In-session RS stays `InProgress`.

1. **Freeze** — For a revision, run `$DEC_REOPEN`, not `$DEC_START`. The holder owns any required reopen permit.
2. **Hold** — While `Frozen`, block ordinary gate advancement and complete RS.
3. **Resume** — After RS confirmation, run `$RS_COMMIT`; it returns the session to `InProgress` and names the gate to resume.

---

## Done

<HARD-GATE name="Decision completion">

1. Do not exit Decision or transition to the next stage until DC succeeds and the user explicitly confirms readiness.
2. In a holder, Decision completion closes only the decision node; holder delivery owns the outer transition and delivered references.

</HARD-GATE>
