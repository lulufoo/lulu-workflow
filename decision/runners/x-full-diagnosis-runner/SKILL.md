---
name: decision/x-full-diagnosis-runner
description: Internal runner for the Decision X gate.
meta-skill-version: 1.0.0
---

# x-full-diagnosis-runner

Diagnose the active X dimensions at decision granularity. Complete when the user
confirms each active dimension's result.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
1. Do NOT proceed until you have read `../../../_runtime.md`.
2. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as `$CTX`.
</HARD-GATE>

- `$CTX.active_gate` must be `X` (from resolve-context)

## Cognitive map

### Active-dimension rules

- Execute only `$CTX.domain_constraints.x_dimensions`; do not infer dimensions
  from holder prose.
- For each active dimension, use
  `$CTX.domain_constraints.domain.dimension_profile[<dimension>].question` as
  its Core question when present; otherwise use the table default.
- A configured `depth` is the depth ceiling. Before confirmation, self-check
  the draft against that ceiling.
- Without a configured `depth`, stop when one deeper level would change who
  decides or require implementation detail. Do not name concrete file paths,
  individual tests, or UI element IDs.

### Dimension goals

| Key | Core question | Complete when |
|-----|---------------|---------------|
| `acceptance_criteria` | How do we know it is done? Which observable, verifiable indicators show that? | Criteria are observable and verifiable, not subjective. |
| `impact_surface` | What does this decision affect, including outside-system parties? | Impact domains, including external ones, are enumerated. |
| `external_dependencies` | Who owns what this depends on? What are the contract, authoritative source, and confirmation mechanism? | Every dependency has a contract, source, and confirmation mechanism; unknowns are logged as Assumptions. |
| `implementation_sketch` | What are the key changes, critical constraints or complexity, and reversibility? | Key changes, critical constraints, and reversibility are all established; unknown constraints are logged as Assumptions. |
| `gap_check` | Does the expected implementation output meet the Acceptance Criteria? Where does it fall short? | The gap is recorded, or explicitly confirmed as none. |

### Dialogue model

For each active dimension, ask its Core question one question at a time (G1/G7),
present the result, then obtain user confirmation before starting the next
dimension. An adjustment revises the current dimension before progression.

### Output rule

Gap Check does not create a separate document section. Record its result in the
`gap` field for the decision document's Acceptance Criteria → Gap (if any).

### Side routes

- Identification hit → load G0 runner immediately → `G0_COMPLETE` → resume the
  current dimension.
- G9 hit → load RS runner.
- A non-empty Gap Check → explicitly flag the gap and load RS to realign E or D.
  Do not close X by force.

## Pipeline

**Entry:**

1. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.
2. If `$CTX.gates.X.status == stale`, follow
   `$SKILL_DIR/references/rs-stale-gate-update.md`, return `GATE_COMPLETE X`,
   and skip Act.

**Act:**

1. Run every Cognitive map active dimension. For each one, apply its configured
   question and depth before asking, then complete its dialogue model and side
   routes, including its pre-confirmation depth self-check.
2. After all active dimensions are confirmed and no Gap Check routes to RS, run
   `$GATE_CONTROL gate-close --gate X --payload '<json>'` (only active-dimension
   fields are required).

**Done:** Return `GATE_COMPLETE X`.

**Stop:** Non-zero CLI, an unconfirmed active dimension, or a gap that requires
realignment stops X.

## gate-close payload

```json
{
  "acceptance_criteria": "...",
  "gap": "None",
  "impact_surface": [
    {"layer": "...", "area": "...", "change_type": "modify", "notes": "..."}
  ],
  "external_dependencies": [
    {"dependency": "...", "contract": "...", "source": "...", "confirmation": "..."}
  ],
  "key_changes": "...",
  "critical_constraints": "...",
  "reversibility": "easy | partial | hard — why"
}
```

## Exit

`GATE_COMPLETE X` or `GATE_FAILED X reason=...`
