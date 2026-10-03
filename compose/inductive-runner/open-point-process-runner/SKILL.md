---
name: open-point-process-runner
description: Validates and analyzes one registered Open group (one lens) against current evidence.
---

# open-point-process-runner

## Goal

Give decision support for each Open of one group. Investigate until the Return is complete; do not over-search.

## Preconditions

- An Open is one unresolved question that matters to the current slice.
- It belongs to one registry lens. Blocking says whether unresolved work
  prevents closure.
- A group is the open Opens of one batch that share one lens.

## Inputs

Require: facts path; one `group` of Opens. A project evidence scope may
also be supplied. Analyze only the Opens in the input group, each on its
own merits.

## Cognition

Input terms carry the meanings defined in these units.

| Term | Unit |
|---|---|
| facts | `../../references/cognition/fact.md` |
| Open `lens`, registry lens | `../../references/cognition/lens.md` |
| KW row the Open's `basis` names | `../../references/cognition/kw-ruler.md` |
| Open, decision support, the human decides | `../../references/cognition/producer/induce.md` |

Two options rest on them: `already-answered` holds when the fact set
states the question; `out-of-slice` holds when the substance belongs to
another lens or to no lens of this slice.

## Analyze

For each Open in the group:

1. Decision support possible → `open`; else `blocked`. Stop that Open if
   `blocked`. Do not infer. `blocked` stops only that Open.
2. If `open`: explain without assumed context. Options must differ in
   action, consequence, or trade-off. Reword, already-answered, and
   out-of-slice are options.
3. If an answer to this Open would constrain or contradict another Open of
   the group, say so in `issue` and name the other Open in `evidence`.

## Return

One object `{"results": [...]}`: one entry per input Open, same order,
each carrying its `open_id`. An entry is one of two shapes.

- `blocked`: exception. Cases: missing input; missing evidence.
  `reason` is free text.
- `open`: `issue`, `evidence`, 2–5 `options`, `lean`.

Entry shapes:

```json
{
  "open_id": "O-1",
  "status": "blocked",
  "reason": "facts path is missing"
}
```

```json
{
  "open_id": "O-2",
  "status": "open",
  "reason": "still unresolved",
  "issue": "Acceptance for this open is still unspecified.",
  "evidence": ["F-1"],
  "options": [
    {"id": "A", "action": "Land a close"},
    {"id": "B", "action": "Reword the question"},
    {"id": "C", "action": "Treat facts as already answering it"}
  ],
  "lean": "A"
}
```

## Boundaries

- Read-only; do not write facts, Opens, Batches, or workflow state.
- No user interaction, disposition, or queue movement.
- An entry never depends on the order of the others, except through step 3.
- Depend only on supplied inputs and the Cognition units.
- Substantive input changes require a fresh invocation.
- Failure has no side effects.

