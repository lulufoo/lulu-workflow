---
name: decision/risk-scan-runner
description: Internal runner that classifies risks onto RK#.
meta-skill-version: 1.0.0
---

# risk-scan-runner

Classify risks. Incremental mode confirms and persists hits as `RK#`. Full mode
returns a draft to the caller (R persists after pack confirm).

Does not change `active_gate`. Does not write `completed` (Release does).
Full mode does not persist.

## Prerequisites

<HARD-GATE>
1. Caller states the mode: **incremental** (S2) or **full** (R).
2. Incremental: caller has pinned Diff from the triggering write stdout.
</HARD-GATE>

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$GET_PAYLOAD` | `$GATE_CONTROL get-payload` |

Subcommand contracts: module docstring / `--help` (`apply-r-assumptions`).

## Modes

| Mode | Scope | Evidence |
|------|-------|----------|
| incremental | Diff = the triggering write stdout (caller pin). Do not walk the full P / A / C set. | That stdout + current conversation. Do not load persisted files to evaluate. |
| full | All current P / A / C. This is the R / `r-expose-bets-runner` input. | Load persisted registers and gate payloads (`$CTX` / `$GET_PAYLOAD`, including `$D` / `$X`). |

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

Draft defaults: H / M → `open`; L → `ignore`. User may override at confirm
(incremental: this runner; full: caller R).
`risk_class` is a label only. Only `open` blocks ordinary close.
`completed` is forbidden here — Release writes it.

One `RK#` has exactly one source: `P#` / `A#` / `C#`. Do not rewrite a hit
into a Constraint.

## Act

1. Judge hits per mode (incremental: Diff only; full: entire set).
2. **incremental:** confirm Diff hits with the user; persist with
   `$GATE_CONTROL apply-r-assumptions` (`--help`); pin `$CTX` if returned.
   If this Diff left `open`, load
   `$SKILL_DIR/runners/risk-release-runner/SKILL.md` for each such row. Return
   `SCAN_COMPLETE` only when none of those rows remain `open`, or the user
   routed away.
3. **full:** return the draft to the caller — no user confirm, no
   `apply-r-assumptions`. Return `SCAN_COMPLETE` with the draft; `open` is
   not persisted.

No silent rewrite.

## Exit

`SCAN_COMPLETE` or `SCAN_FAILED reason=...`
