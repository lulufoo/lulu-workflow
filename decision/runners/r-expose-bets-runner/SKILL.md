---
name: decision/r-expose-bets-runner
description: Internal runner for the Decision R gate.
meta-skill-version: 1.0.0
---

# r-expose-bets-runner

Make assumptions and risks reviewable as a complete risk pack, then handle or
route unresolved risks. Complete when the pack is confirmed and the selected exit
is legal.

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
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$GET_PAYLOAD` | `$GATE_CONTROL get-payload` |

Subcommand contracts: module docstring / `--help` (including
`apply-r-assumptions`, `complete-assumption`, `set-risk-state`, and R
`gate-close`).

## Cognitive map

### Goals

| ID | Must be clear |
|----|----------------|
| `G-pack` | Expose pack ready and shown: User Prior; assumption coverage vs D/X/history; full-table `risk_level` / `risk_class` / `risk_state` / `risk_consequence`; proposed exit. No undigested user revise pending. |
| `G-expose-confirm` | One user confirm covers prior sign-off, coverage, risk fields (incl. reclass), and intended exit (`rs` \| `dc` \| suspend). **`open` rows allowed** at this goal. |
| `G-handled` | No remaining `risk_state=open`, **or** user chose `rs` / `human_decision` to leave R. |

### Coverage / bounds

- **Empty Prior / empty assumptions:** legal; present as empty — do not block close for lack of prior dump.
- **Do not recollect Prior via G0** at R; sign-off is on `$CTX.registers.prior` as shown in the pack.
- **Coverage:** review `$CTX.registers.assumptions` against D, X, and conversation; do not collect the log from scratch.
- **Read `$CTX.gl.exchanges` in full** during `prepare` (prefer `gap_check` / risk-narrative / confirmation intents); fold into the draft — **no separate confirm turn**.
- **Classify only on the full table here** — never assign `risk_class` at G0 / append time.
- **Non-risk rows:** `risk_level` / `risk_class` / `risk_state` all `none`; `risk_consequence` still required (may be empty or “—”).
- **Risk row defaults (draft):** H/M → `risk_state=open`; L → `ignore`. User may override at confirm.
- **`risk_level` (H/M/L)** — impact on whether the **delivered decision** is overturned (orthogonal to `risk_class`):
  - **High:** failure would seriously undermine or overturn the delivered decision
  - **Medium:** failure forces a significant adjustment, not necessarily full overturn
  - **Low:** limited impact; absorbable in execution
- **`risk_class`:** judgment label only — **does not** drive release ops or block DC.
  Delivery gating is **only** `risk_state=open`.
  - **decision** — risk about the decision itself (classify for human reading)
  - **implementation** — risk about later implementation (classify for human reading)
  - **pending** — class not yet judged; still no gate effect
  - **none** — not a risk row (triad with `risk_level`/`risk_state` all `none`)
- **Batch present (required on non-stale path):** one screen with Prior + coverage + risk draft + proposed exit. **Forbidden** as the default: separate confirm rounds for Prior alone, coverage alone, then risk alone, then exit alone.
- **Revise:** on any change request, update the draft and **re-present the full pack** (`present`); do not reopen split confirm rounds.
- **Expose confirm** → `$GATE_CONTROL apply-r-assumptions --payload '{"assumptions":[...]}'` (no `completed`). Mid-`handle`: `complete-assumption` / `set-risk-state` only.
- **Exits (mutually exclusive; AI must not unilaterally pick):**
  - `rs` — assumption confirmed wrong/invalid → RS at `realign_gate`
  - `dc` — no `risk_state=open` remains → DC
  - `human_decision` — user suspends (open items unresolved or cannot proceed) → HD runner
- **Final close** uses `gate-close --gate R` with `exit` + current assumptions snapshot — do not invent `completed` in that payload.
- **Stale review:** preserve the full risk pack from `$CTX.registers`; compare
  updated upstream payloads, propose affected rows and dispositions, and obtain
  one explicit confirmation. Persist risk changes before close; `exit=dc`
  closes with `assumptions: []` plus the confirmed `stale_review` receipt.

### Dialogue modes

| Mode | When | Behavior |
|------|------|----------|
| `prepare` | Pack not ready | Off-turn: read prior, assumptions, `gl.exchanges`; draft full-table risk fields + proposed exit. **No user confirm turn.** |
| `present` | Pack ready; awaiting expose confirm | Show the full pack (Prior, coverage, risk table, proposed exit). Ask for one confirm or change points. |
| `revise` | User requests expose changes | Apply changes; return to `present` with the full pack. |
| `handle` | After `apply-r-assumptions` and any `risk_state=open` | H→M→L: pick next open; load `$SKILL_DIR/references/risk-release.md`; one op; repeat or exit. |
| `review-stale` | R is stale | Show the full pack with affected-row diffs; confirm impact and dispositions; persist changes; handle reopened risks. |
| `close` | `G-handled` met for `dc` / `rs` / `human_decision` | `$GATE_CONTROL gate-close --gate R` with payload below. |

### Pass criterion

`G-expose-confirm` with explicit user confirmation; after handle (if any),
`G-handled`; close payload legal for chosen `exit`.

### Side routes

- Identification hit → load G0 runner → `G0_COMPLETE` → resume R at `prepare`/`present` (batch rules still apply).
- G9 hit → load RS runner → after return, resume (R may be `stale` → Per-gate path below).
- During `handle`: user wants table changes → `present`/`revise` (no control `return_expose`).
- During `handle`: upstream wrong → `rs`; cannot finish → `human_decision` → HD runner.

## Pipeline

**Entry:**

1. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as `$CTX`.
2. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.

**Stale entry:** If `$CTX.gates.R.status == stale`:

1. Run `$GET_PAYLOAD --stale-only`; compare updated upstream conclusions with
   the complete risk pack in `$CTX.registers`.
2. Enter `review-stale`: present the full pack, highlight affected rows and
   incremental diffs, propose affected IDs and dispositions, then obtain one
   user confirmation.
3. Persist classification changes with `$GATE_CONTROL apply-r-assumptions`.
   For invalidated completed evidence, use `$GATE_CONTROL set-risk-state
   --risk-state open` (which clears old release terms), then enter `handle`
   until no open risk remains.
4. If the review finds an upstream conclusion wrong, use `$GATE_CONTROL
   gate-close` with `exit=rs`; if the user suspends, close with
   `exit=human_decision`.
5. Otherwise use `$GATE_CONTROL gate-close` with `exit=dc`,
   `assumptions: []`, and the confirmed `stale_review` receipt. Do not close
   before this confirmation.
6. Go to Done handoff below; skip the non-stale Act loop.

**Act (non-stale):**

1. Cognitive map loop:
   - `G-pack` unmet → `prepare` → `present`.
   - On revise → `revise` → `present`.
   - On expose confirm → `$GATE_CONTROL apply-r-assumptions --payload` with
     full `assumptions` (no `completed`; no `exit`). If any row is `open` and
     user did not choose `rs` / `human_decision`, → `handle` (R stays active).
     If user chose `rs` / `human_decision` at expose → skip `handle` → `close`
     with that exit. If no `open` and intended exit is `dc` → `close` with
     `exit=dc`.
   - `handle` → when no `open` remains → `close` with `exit=dc`; or user
     chooses `rs` / `human_decision` → `close` with that exit.
   - On final close → break.

**Done:**

- `exit=rs` → load `$SKILL_DIR/runners/rs-realign-runner/SKILL.md` with `realign_gate`
- `exit=human_decision` → load `$SKILL_DIR/runners/hd-human-decision-runner/SKILL.md`
- `exit=dc` → return `GATE_COMPLETE R exit=dc`

**Stop:** Non-zero CLI, or confirmation cannot be judged → stop and wait for
user direction.

## Payloads

### `apply-r-assumptions` (expose confirm)

```json
{
  "assumptions": [
    {
      "id": "A1",
      "risk_level": "H",
      "risk_class": "decision",
      "risk_state": "open",
      "risk_consequence": "Export blocked"
    },
    {
      "id": "A2",
      "risk_level": "L",
      "risk_class": "implementation",
      "risk_state": "ignore",
      "risk_consequence": "Minor post-ship tweak"
    },
    {
      "id": "A3",
      "risk_level": "none",
      "risk_class": "none",
      "risk_state": "none",
      "risk_consequence": "—"
    }
  ]
}
```

- each assumption requires `risk_level`, `risk_class`, `risk_state`, `risk_consequence`
- **Forbidden:** `risk_state=completed` (use `complete-assumption` in `handle`)

### Final `gate-close --gate R`

```json
{
  "exit": "dc",
  "assumptions": []
}
```

RS exit (may still carry non-`completed` snapshot fields):

```json
{
  "exit": "rs",
  "realign_gate": "D",
  "assumptions": [
    {
      "id": "A1",
      "risk_level": "H",
      "risk_class": "decision",
      "risk_state": "open",
      "risk_consequence": "Export blocked"
    }
  ]
}
```

- `exit`: `dc` | `rs` | `human_decision`
- `exit=dc` forbids any `risk_state=open` (complete or reclass via handle first)
- do not invent `completed` in close payload
- `exit=dc`: marks all pending **prior** entries `verified`
- Final `dc` close may use `"assumptions": []` when rows are already persisted
- Stale `exit=dc` requires `stale_review.user_confirmed=true`; affected IDs are
  unique and each has a final disposition accepted by CLI validation.
- Stale `exit=rs` / `human_decision` does not require `stale_review`.

## Exit

On success:

```
GATE_COMPLETE R exit=dc
```

`exit=rs` → RS runner. `exit=human_decision` → HD runner (not a normal spine advance).

On failure:

```
GATE_FAILED R reason=<brief description>
```
