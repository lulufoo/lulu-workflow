---
name: decision/gl-grill-runner
description: Internal runner for the Decision GL gate.
meta-skill-version: 1.0.0
---

# gl-grill-runner

Surface decision-relevant user intent and critical uncertainties before direction
setting. Complete when the input is sufficient to enter E.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `GL`).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.
- Probe questions: before the first probe in each GL entry, read
  `$SKILL_ROOT/shared/references/ask-protocol.md`; apply it to every probe.

## Must hold

Active X dimensions are preflight coverage labels, not diagnostic prompts.

| ID | Must hold |
|----|-----------|
| `G-direction-ready` | User intent is clear enough that further probing would not materially change the candidate direction set. |
| `G-diagnosis-preflight` | Decision-critical uncertainties that could overturn a direction are surfaced; each active X dimension has a conclusion or reasoned `na`. Unjustified all-`na` does not pass. |

## Ask domain

1. Anchor every probe to the locked Q problem + constraints.
2. Decision-domain intent only. No implementation interview, WBS, or unbounded
   plan grilling.
3. Freedom is which concrete question to ask — not any domain.

## Modes

| Mode | When | Behavior |
|------|------|----------|
| `probe` | Either Must hold row not met | Apply ask-protocol, then ask only the gap. May pick next lens; order not fixed. |
| `summarize` | Both Must hold rows met | Restate key intents once; ask if ready for E. |
| `close` | User confirms | `$GATE_CONTROL gate-close --gate GL --payload '<json>'` |

If the user rejects the summary: treat the denied point as a gap → `probe`.

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout GL.

## Act

1. If `$CTX.gates.GL.status == stale`, follow
   `$SKILL_DIR/references/rs-stale-gate-update.md`, return `GATE_COMPLETE GL`,
   and skip the loop.
2. Obtain locked Q via `$GATE_CONTROL get-payload` (or fields already on `$CTX`);
   do not start probes until Q payload is available.
3. Loop Modes (Signals as above) until `close` succeeds. On S1, register
   `source` is `GL`. Persist intents only via GL `gate-close` payload — do not
   dual-write exchanges to P.

## gate-close payload

```json
{
  "exchanges": [
    {
      "lens": "<active x_dimension_id>",
      "question": "<question>",
      "answer": "<user answer>",
      "na": false
    }
  ],
  "user_confirmed": true
}
```

- `lens` ∈ active `x_dimensions`; every active dim at least once (conclusion or `na: true`)
- Row rules and coverage: CLI (`dec_gate_control` / `--help`)
- `G-direction-ready` is framework-only (no extra payload slot)

## Exit

`GATE_COMPLETE GL` · `GATE_FAILED GL reason=<brief description>`
