---
name: decision/r-expose-bets-runner
description: Internal runner for the Decision R gate.
meta-skill-version: 1.0.0
---

# r-expose-bets-runner

Make assumptions and risks reviewable as a pack, then handle or route
unresolved risks. Complete when the exit is legal: user-confirmed pack, or
empty pack (zero `RK#`, exit `dc`) auto-closed.

## Bind

1. Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `R`).
2. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.
3. Run `$GET_PAYLOAD --gates D,X`; pin `payloads.D` as `$D` and `payloads.X`
   as `$X`. If either is missing, stop and report the missing required input.

## Must hold

| ID | Must hold |
|----|-----------|
| `G-pack` | Registers reviewed against `$D`, `$X`, and dialogue; table and exit ready. Show iff non-empty. |
| `G-expose-confirm` | Non-empty: one user confirm covers sign-off, coverage, fields, and exit (`rs` \| `dc` \| suspend). `open` allowed. Empty: holds. |
| `G-handled` | No `risk_state=open`, or exit `rs` / `human_decision`. |

## Modes

| Mode | When | Behavior |
|------|------|----------|
| `prepare` | Pack not ready | Off-turn: read `$CTX.gl.exchanges`; load `$DECISION_SKILL_DIR/runners/risk-scan-runner/SKILL.md` in **full** mode; draft pack and exit. Empty → `close`. Else → `present`. |
| `present` | Pack ready and not empty | Show pack and exit. On confirm: `$GATE_CONTROL apply-r-assumptions` (`--help`); then `handle` or `close`. |
| `revise` | User requests expose changes | Apply changes, then re-present the full pack. |
| `handle` | After persist, any `risk_state=open` remains and exit is still `dc` | H→M→L: load `$DECISION_SKILL_DIR/runners/risk-release-runner/SKILL.md` for the next open row; one op; repeat or exit. Table changes → `present` / `revise`; upstream wrong → `rs`; cannot finish → `human_decision`. |
| `close` | `G-handled` met | `$GATE_CONTROL gate-close --gate R` (`--help`). |

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout R.

## Divert

- If `$CTX.gates.R.status == stale`: follow
  `$DECISION_SKILL_DIR/references/r-stale-review.md`, then Exit.
- `exit=rs` → load RS runner. `exit=human_decision` → load HD runner.

## Run

Loop Modes (Signals and Divert as above) until `close` succeeds.

`GATE_COMPLETE R exit=dc` · `GATE_FAILED R reason=<brief description>`
