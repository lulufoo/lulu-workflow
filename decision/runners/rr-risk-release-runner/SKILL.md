---
name: decision/rr-risk-release-runner
description: >-
  RR gate runner for decision Loop B. Risk Release: set terms
  (verify/accept/handoff), release-check RR-scope, exit dc / return_r / HD.
  Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# rr-risk-release-runner

Execute **RR — Risk Release** (LoopB): clear delivery risk terms, then
release-check RR-scope items. One `gate-close` ends the gate.

## Blocking policy

If any control CLI exits non-zero: **stop**, report the error, wait for user
direction. Do not continue the gate dialogue.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- `$CTX.active_gate` must be `RR` (from resolve-context)
- `$CTX.gates.R.status` must be `closed`
- `$CTX.skipped_gates` must be empty
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
| `G-terms` | Pending `risk_class` resolved; every settled assumption has verification — decision H/tracking: Method/Owner/Timing/Release; decision M/L: `Accepted`; implementation: `Handoff:`. |
| `G-released` | Every RR-scope item release-checked (`released: true`), **or** no RR-scope (goal satisfied without `release` mode). |

### Coverage / bounds

- **Entry:** R exit `loop_b` only (R exit `dc` skips this gate).
- **RR-scope:** `risk_class=decision` AND (High **or** `release_tracking`). `implementation` never enters `release` mode and never blocks DC after handoff.
- **Terms first:** resolve every `pending` → `decision` or `implementation` before close.
- **Forbidden:** `release_tracking` on `implementation` (reclassify to `decision` first).
- **Batch confirm:** when taking `exit=dc` with no RR-scope, `batch_confirmed` must be true (M/L Accepted path).
- **One close:** do not emit a spine `exit=rr`; stay in this gate from `terms` through optional `release`.
- **vs R:** R exposes risk (`risk` / `risk_class` / consequence). This gate sets terms and releases — does not re-classify the full table from scratch.

### Dialogue modes

| Mode | When | Behavior |
|------|------|----------|
| `terms` | `G-terms` unmet | Resolve pending; assign verification / Accepted / Handoff by class; batch-confirm Accepted items when relevant. |
| `release` | `G-terms` met and RR-scope remains | Check each scope item’s result against its Release condition; mark released or leave unreleased. |
| `close` | Both goals met (or HD / return_r chosen) | One `$GATE_CONTROL gate-close --gate RR` with payload below. |

After `terms` confirmation, if `G-released` is unmet, continue into `release` in the **same** turn when possible (avoid a pure process confirm between modes).

### Pass criterion

`G-terms` and `G-released` hold for `exit=dc`; or exit is `return_r` / `human_decision` per Side routes / Exit.

### Side routes

- Identification hit → load G0 runner → `G0_COMPLETE` → resume RR dialogue.
- G9 / prior pass criterion fails → load RS runner → after return, resume (RR may be `stale` → Per-gate update).
- `exit=human_decision` → load HD runner (do not treat as `GATE_COMPLETE` success path alone).
- `exit=return_r` → R re-enters for new pending assumptions from this gate (LoopA not restarted).

## Pipeline

**Entry:** `$CTX.active_gate` is `RR`. Run `$GATE_CONTROL resolve-context`; pin
stdout JSON as `$CTX`. If `$CTX.gates.RR.status == stale`: follow
`$SKILL_DIR/references/stale-gate-update.md` steps 1–4 only (three-part update +
user confirm + `gate-close`; payload must include `exit`); do **not** follow
that file’s step 5 return — go to Done handoff below.

**Act:**

1. Apply `$CTX.domain_constraints` for all dialogue in this gate:
   - `objective` — session intent; frame the gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
2. Cognitive map loop:
   - `G-terms` unmet → `terms`.
   - `G-terms` met ∧ `G-released` unmet → `release`.
   - On close → `$GATE_CONTROL gate-close --gate RR --payload '<json>'` → break.

**Done:**

- `exit=human_decision` → load `$SKILL_DIR/runners/hd-human-decision-runner/SKILL.md`
- Otherwise return `GATE_COMPLETE RR exit=<dc|return_r>`

**Stop:** Non-zero CLI, or confirmation cannot be judged → stop and wait for
user direction.

## gate-close payload

```json
{
  "exit": "dc",
  "batch_confirmed": true,
  "assumptions": [
    {
      "id": "A1",
      "risk": "H",
      "risk_class": "decision",
      "verification": "Method: … / Owner: … / Timing: … / Release condition: …",
      "released": true
    },
    {
      "id": "A2",
      "risk": "H",
      "risk_class": "implementation",
      "verification": "Handoff: …"
    },
    {
      "id": "A3",
      "risk": "L",
      "risk_class": "decision",
      "verification": "Accepted",
      "release_tracking": false
    }
  ]
}
```

- `exit`: `dc` | `return_r` | `human_decision`
- Every settled assumption needs `verification`
- RR-scope rows need `released` when exiting `dc` / `return_r` / `human_decision`
- `batch_confirmed: true` required for `exit=dc` when there is no RR-scope
- No `pending` risk_class at close; `implementation` + `release_tracking` forbidden

## Exit

On success:

```
GATE_COMPLETE RR exit=dc|return_r
```

`exit=human_decision` → HD runner (not a normal `GATE_COMPLETE` handoff alone).

On failure:

```
GATE_FAILED RR reason=<brief description>
```
