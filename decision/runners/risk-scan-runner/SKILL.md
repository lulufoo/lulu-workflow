---
name: decision/risk-scan-runner
description: Internal runner that classifies risks onto RK#.
meta-skill-version: 1.0.0
---

# risk-scan-runner

Classify risks and persist hits as `RK#`. Complete when hits are written or
there is no risk (incremental: after this Diff's `open` is released or routed
away; full: `open` may remain).

Does not change `active_gate`. Does not write `completed` (Release does).

## Prerequisites

<HARD-GATE>
1. Caller states the mode: **incremental** (G8) or **full** (R).
2. Incremental: caller has pinned Diff from the triggering write stdout.
</HARD-GATE>

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$GET_PAYLOAD` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>" get-payload` |

Subcommand contracts: module docstring / `--help` (`apply-r-assumptions`).

## Modes

| Mode | Scope | Evidence |
|------|-------|----------|
| incremental | Diff = the triggering write stdout (caller pin). Do not walk the full P / A / C set. | That stdout + current conversation. Do not load persisted files to evaluate. |
| full | All current P / A / C. This is the R / `r-expose-bets-runner` input. | Load persisted registers and gate payloads (`$CTX` / `$GET_PAYLOAD`). |

Incremental miss ≠ full scan complete. R cannot be skipped.

## Classification

Every hit has `risk_level`, `risk_class`, `risk_state`, `risk_consequence`.
A non-risk conclusion uses `none` in the pack only — do not write a `none`
`RK#` row.

| Field | Values | Meaning |
|-------|--------|---------|
| `risk_level` | H | Failure seriously undermines or overturns the delivered decision. |
| `risk_level` | M | Failure requires a significant adjustment without necessarily overturning the decision. |
| `risk_level` | L | Failure has limited, absorbable execution impact. |
| `risk_class` | `decision` | Risk concerns the decision itself. |
| `risk_class` | `implementation` | Risk concerns later implementation. |
| `risk_class` | `pending` | Class is not yet judged. |

Draft defaults: H / M → `open`; L → `ignore`. User may override at confirm.
`risk_class` is a label only. Only `open` blocks ordinary close.
`completed` is forbidden here — Release writes it.

One `RK#` has exactly one source: `P#` / `A#` / `C#`. Do not rewrite a hit
into a Constraint.

## Pipeline

**Act:**

1. Judge hits per mode (incremental: Diff only; full: entire set).
2. Confirm the draft with the user (incremental: Diff hits only; full: the pack).
3. Persist hits with `$GATE_CONTROL apply-r-assumptions`. Item `id` is the
   source `P#` / `A#` / `C#` or an existing `RK#`. Omit `none` rows.
4. Pin `$CTX` if the command returns context; otherwise keep the caller's pin.

**Done:**
- incremental: if this Diff left `open`, load
  `$SKILL_DIR/runners/risk-release-runner/SKILL.md` for each such row. Return
  `SCAN_COMPLETE` only when none of those rows remain `open`, or the user
  routed away.
- full: return `SCAN_COMPLETE` with `open` left for the caller.

**Stop:** No silent rewrite.

## apply-r-assumptions

```json
{
  "assumptions": [
    {
      "id": "A1",
      "risk_level": "H",
      "risk_class": "decision",
      "risk_state": "open",
      "risk_consequence": "..."
    }
  ]
}
```

## Exit

`SCAN_COMPLETE` or `SCAN_FAILED reason=...`
