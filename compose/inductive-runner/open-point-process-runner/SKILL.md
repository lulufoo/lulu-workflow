---
name: open-point-process-runner
description: Validates and analyzes one registered Open against current evidence.
---

# open-point-process-runner

## Goal

Decide whether the Open is still unresolved work. If `open`, give decision support for that Open only. Investigate until the Return is complete; do not over-search.

## Preconditions

- Read `../references/open-point-model.md`.

## Inputs

Require: facts path; one Open. A project evidence scope may also be supplied.
Analyze only the input Open.

## Analyze

1. Decision support possible → `open`; else `blocked`. Stop if `blocked`.
   Do not infer.
2. If `open`: explain without assumed context. Options must differ in
   action, consequence, or trade-off. Reword, already-answered, and
   out-of-slice are options.

## Return

- `blocked`: exception. Cases: missing input; missing evidence.
  `reason` is free text.
- `open`: still unresolved; `issue`, `evidence`, 2–5 `options`, `lean`.
- Use one of the two shapes below.

```json
{
  "status": "blocked",
  "reason": "facts path is missing"
}
```

```json
{
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
- Depend only on supplied inputs.
- Substantive input changes require a fresh invocation.
- Failure has no side effects.

