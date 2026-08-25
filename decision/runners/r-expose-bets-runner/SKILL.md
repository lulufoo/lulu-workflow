---
name: decision/r-expose-bets-runner
description: Internal runner for the Decision R gate.
meta-skill-version: 1.0.0
---

# r-expose-bets-runner

Make assumptions and risks reviewable as a complete risk pack, then handle or
route unresolved risks. Complete when the pack is confirmed and the selected exit
is legal.

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$GET_PAYLOAD` | `$GATE_CONTROL get-payload` |

Subcommand contracts: module docstring / `--help` (`apply-r-assumptions`,
R `gate-close`).

## Bind

1. Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `R`).
2. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.
3. Run `$GET_PAYLOAD --gates D,X`; pin `payloads.D` as `$D` and `payloads.X`
   as `$X`. If either is missing, stop and report the missing required input.

## Hold

| ID | Must hold |
|----|----------------|
| `G-pack` | Expose pack ready and shown: `$CTX.registers` reviewed against `$D`, `$X`, and current dialogue; classified risk table; proposed exit. No undigested revise pending. |
| `G-expose-confirm` | One user confirm covers sign-off, coverage, risk fields (incl. reclass), and intended exit (`rs` \| `dc` \| suspend). **`open` rows allowed** here. |
| `G-handled` | No remaining `risk_state=open`, **or** user chose `rs` / `human_decision` to leave R. |

## Modes

| Mode | When | Behavior |
|------|------|----------|
| `prepare` | Pack not ready | Off-turn: read `$CTX.gl.exchanges` in full; load `$SKILL_DIR/runners/risk-scan-runner/SKILL.md` in **full** mode; draft the pack and proposed exit. **No user confirm.** |
| `present` | Pack ready | Show the pack and proposed exit together. On confirm: `$GATE_CONTROL apply-r-assumptions` (`--help`); then `handle` or `close`. |
| `revise` | User requests expose changes | Apply changes, then re-present the full pack. |
| `handle` | After persist, any `risk_state=open` remains and exit is still `dc` | H→M→L: load `$SKILL_DIR/runners/risk-release-runner/SKILL.md` for the next open row; one op; repeat or exit. Table changes → `present` / `revise`; upstream wrong → `rs`; cannot finish → `human_decision`. |
| `close` | `G-handled` met | `$GATE_CONTROL gate-close --gate R` (`--help`). |

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout R.

## Divert

- If `$CTX.gates.R.status == stale`: follow
  `$SKILL_DIR/references/r-stale-review.md`, then Exit.
- `exit=rs` → load RS runner. `exit=human_decision` → load HD runner.

## Run

Loop Modes (Signals and Divert as above) until `close` succeeds.

`GATE_COMPLETE R exit=dc` · `GATE_FAILED R reason=<brief description>`
