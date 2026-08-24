---
name: decision/risk-release-runner
description: Internal runner that releases one open RK#.
meta-skill-version: 1.0.0
---

# risk-release-runner

Resolve one `risk_state=open` `RK#` (or leftover Assumption risk row). Complete
when that row is `completed` or `ignore`, or the user routes away.

Does not change `active_gate`. Call once per `open` row.
CLI failure leaves the row `open`.

## Prerequisites

<HARD-GATE>
1. Do NOT proceed until you have read `../../../_runtime.md`.
2. Caller names the current `open` id.
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |

Subcommand contracts: `--help` (`complete-assumption`, `set-risk-state`).

## Goals

| ID | Must be clear |
|----|----------------|
| `G-terms-one` | Current row has legal `release_terms` (Method / Owner / Timing / Release condition, or literal `Accepted`). |
| `G-check-one` | User confirmed terms and the check against the Release condition (or accepted M/L as `Accepted`). |
| `G-complete-one` | Row recorded: `completed` via complete-assumption, `ignore` via set-risk-state, or user routed out. |

## Steps

1. **Identify** — Current id, `risk_level`, `risk_class`, `risk_consequence`,
   `risk_state=open`.
2. **Draft terms** — H (and decision-class M when verifying) use Method /
   Owner / Timing / Release condition; M/L may use `Accepted`. Forbidden:
   `Handoff:` prefix.
3. **Confirm** — User confirms terms and the check result (or `Accepted`).
4. **Persist** — Complete path:
   `$GATE_CONTROL complete-assumption --id <id> --release-terms '<terms>'`
   (the call is the user confirmation). Ignore path:
   `$GATE_CONTROL set-risk-state --id <id> --risk-state ignore`.
   `<id>` is `RK#`, or leftover `A#` if that row still holds risk fields.
5. **Return** — `RELEASE_COMPLETE` or `RELEASE_FAILED`. Caller owns the next
   step.

`completed` is written only by `complete-assumption`, never by `gate-close` or
`apply-r-assumptions`.

## Exit

`RELEASE_COMPLETE` or `RELEASE_FAILED reason=...`
