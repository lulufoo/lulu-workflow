---
name: decision/hd-human-decision-runner
description: Internal runner for the Decision Human Decision subroutine.
meta-skill-version: 1.0.0
---

# hd-human-decision-runner

Resolve an R suspension caused by unresolved risks. Complete by routing an
upstream error to RS or reporting an Unable to Decide outcome.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (R exit `human_decision`).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.

## Cognitive map

### Decision model

Use this subroutine only when open risks remain unresolved, an upstream
conclusion may be wrong, or available information cannot support a decision.

| User finding | Required outcome |
|--------------|------------------|
| An upstream conclusion is wrong | Identify the affected align gate and load RS. RS routes LoopA from that gate. |
| No decision is possible with available information | Report `Unable to Decide`: at least two directions explored, the stuck gate and reason, and the unlock condition. Keep the session incomplete. |

### Bounds

- Present the R failure context before asking for a disposition.
- This subroutine does not close a spine gate or change the active gate.

## Pipeline

**Act:**

1. Present the R failure context and ask the user to choose a Cognitive map
   outcome.
2. Upstream wrong → identify the align gate, then load
   `$SKILL_DIR/runners/rs-realign-runner/SKILL.md`.
3. No decision possible → report `Unable to Decide` with the required contents.

**Done:** Return `HD_COMPLETE exit=rs|unable` or hand off to RS runner.

## Exit

`HD_COMPLETE exit=rs reenter=<G>` · `HD_COMPLETE exit=unable`
