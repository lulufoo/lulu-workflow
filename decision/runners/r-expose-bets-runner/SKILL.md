---
name: decision/r-expose-bets-runner
description: >-
  R gate runner for decision. Expose the Bets: batch-present Prior, assumption
  coverage, and full-table risk draft with proposed exit; one confirm; gate-close
  R. Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# r-expose-bets-runner

Execute **R — Expose the Bets**. Prepare the expose pack off-turn, present it
once, revise by re-presenting the full pack, then one confirm and `gate-close`.

## Blocking policy

If any control CLI exits non-zero: **stop**, report the error, wait for user
direction. Do not continue the gate dialogue.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- `$CTX.active_gate` must be `R` (from resolve-context)
- `$CTX.gates.X.status` must be `closed`
- Dialogue semantics SSOT: this file’s **Cognitive map** (no separate gate file)

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstring / `--help`.

## Cognitive map

### Goals

| ID | Must be clear |
|----|----------------|
| `G-pack` | Expose pack ready and shown: User Prior; Assumption coverage vs D/X/history; full-table `risk` / `risk_class` / consequence draft; proposed exit. No undigested user revise pending. |
| `G-confirm` | One user confirm covers prior sign-off, coverage, risk/class (incl. reclass), and exit (`rs` \| `loop_b` \| `dc`). |

### Coverage / bounds

- **Empty Prior / empty assumptions:** legal; present as empty — do not block close for lack of prior dump.
- **Do not recollect Prior via G0** at R; sign-off is on `$CTX.registers.prior` as shown in the pack.
- **Coverage:** review `$CTX.registers.assumptions` against D, X, and conversation; do not collect the log from scratch.
- **Read `$CTX.gl.exchanges` in full** during `prepare` (prefer `gap_check` / risk-narrative / confirmation intents); fold into the draft — **no separate confirm turn**.
- **Classify only on the full table here** — never assign `risk_class` at G0 / append time.
- **Risk (H/M/L)** — impact on whether the **delivered decision** is overturned (orthogonal to `risk_class`):
  - **High:** failure would seriously undermine or overturn the delivered decision
  - **Medium:** failure forces a significant adjustment, not necessarily full overturn
  - **Low:** limited impact; absorbable in execution
- **`risk_class`:**
  - **decision** — verification (or equivalent) can / must complete before DC
  - **implementation** — cannot meaningfully verify before DC; handoff at RR terms; does not enter release-check
  - **pending** — gray; may leave R only via `loop_b`; resolve at RR terms entry. If unclear whether verification can finish before DC → `pending` (do not silently default to `decision`)
- **Batch present (required on non-stale path):** one screen with Prior + coverage + risk draft + proposed exit. **Forbidden** as the default: separate confirm rounds for Prior alone, coverage alone, then risk alone, then exit alone.
- **Revise:** on any change request, update the draft and **re-present the full pack** (`present`); do not reopen split confirm rounds.
- **One confirm** must establish: prior sign-off (or empty prior OK); coverage complete (or “no missing rows” accepted); every assumption has `risk` / `risk_class` / consequence; exit chosen and legal.
- **Exits (mutually exclusive; AI must not unilaterally pick):**
  - `rs` — assumption confirmed wrong/invalid → RS at `realign_gate`
  - `loop_b` — any remaining uncertain / `implementation` / `pending` / unresolved `[待验证]` → RR
  - `dc` — all `decision` and resolved → DC (**forbidden** if any `pending` or `implementation`)
- **Bulk assumption field updates** only via R `gate-close` payload — not fresh G0 collection for risk fields.
- **vs RR:** R exposes and classifies; RR sets terms / release-check.

### Dialogue modes

| Mode | When | Behavior |
|------|------|----------|
| `prepare` | Pack not ready | Off-turn: read prior, assumptions, `gl.exchanges`; draft full-table risk/class/consequence; propose exit. **No user confirm turn.** |
| `present` | Pack ready; awaiting user | Show the full pack (four blocks). Ask for one confirm or change points. |
| `revise` | User requests changes | Apply changes; return to `present` with the full pack. |
| `close` | `G-confirm` met | `gate-close` with payload below. |

### Pass criterion

`G-confirm` with explicit user confirmation; close payload includes `exit` and per-assumption `risk` / `risk_class` / `consequence`.

### Side routes

- Identification hit → load G0 runner → `G0_COMPLETE` → resume R at `prepare`/`present` (batch rules still apply).
- G9 hit → load RS runner → after return, resume (R may be `stale` → Per-gate path below).

## Pipeline

**Entry:** `$CTX.active_gate` is `R`. Run `$GATE_CONTROL resolve-context`; pin
stdout JSON as `$CTX`. If `$CTX.gates.R.status == stale`: follow
`$SKILL_DIR/references/stale-gate-update.md` steps 1–4 only (three-part update +
user confirm + `gate-close`; payload must include `exit`, and `realign_gate`
when `exit=rs`); do **not** follow that file’s step 5 return — go to Done
handoff below. **Do not** force the non-stale R5 pack on the stale path.

**Act (non-stale):**

1. Apply `$CTX.domain_constraints` for all dialogue in this gate:
   - `objective` — session intent; frame the gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
2. Cognitive map loop:
   - `G-pack` unmet → `prepare` → `present`.
   - On revise → `revise` → `present`.
   - On confirm → `close`:
     `$GATE_CONTROL gate-close --gate R --payload '<json>'` → break.

**Done:**

- `exit=rs` → load `$SKILL_DIR/runners/rs-realign-runner/SKILL.md` with `realign_gate`
- Otherwise return `GATE_COMPLETE R exit=<loop_b|dc>`

**Stop:** Non-zero CLI, or confirmation cannot be judged → stop and wait for
user direction.

## gate-close payload

```json
{
  "exit": "loop_b",
  "assumptions": [
    {"id": "A1", "risk": "H", "risk_class": "decision", "consequence": "..."},
    {"id": "A2", "risk": "H", "risk_class": "implementation", "consequence": "..."},
    {"id": "A3", "risk": "L", "risk_class": "pending", "consequence": "..."}
  ]
}
```

RS exit:

```json
{
  "exit": "rs",
  "realign_gate": "D",
  "assumptions": [{"id": "A1", "risk": "H", "risk_class": "decision", "consequence": "..."}]
}
```

- `exit`: `rs` | `loop_b` | `dc`
- each assumption requires `risk`, `risk_class`, `consequence`
- `exit=dc` forbids `risk_class` of `pending` or `implementation`
- `loop_b` / `dc`: marks all pending **prior** entries `verified`; `dc` also marks pending assumptions `verified`

## Exit

On success:

```
GATE_COMPLETE R exit=loop_b|dc
```

`exit=rs` → RS runner (`GATE_COMPLETE R exit=rs realign_gate=<G>` handoff as today).

On failure:

```
GATE_FAILED R reason=<brief description>
```
