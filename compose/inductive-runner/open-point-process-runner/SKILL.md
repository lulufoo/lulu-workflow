---
name: open-point-process-runner
description: Validates and analyzes one registered Open against current evidence.
---

# open-point-process-runner

Analyze one registered Open against the latest facts and return the analysis package needed for disposition. Completion is one structured Return.

## Goal

Determine whether the Open still represents unresolved work. When valid, provide self-contained, evidence-based decision support for that Open only.

## Preconditions

- Read `../references/open-point-model.md`.
- Treat the supplied snapshots and digests as the complete current context.

## Inputs

Require:

- facts snapshot and facts digest;
- one Open and its digest;
- batch digest.

A project evidence scope may also be supplied. Analyze only the input Open.

## Analyze one open

1. If a required input is absent, return a blocker without assessing validity.
2. Judge validity before developing options:
   - `valid` — unresolved and materially unchanged;
   - `changed` — the concern remains, but current facts materially alter the question;
   - `resolved` — current facts answer the question;
   - `invalid` — unsupported, false, or outside the current slice.
3. For `changed`, return one replacement question with its supporting evidence.
4. For `resolved`, cite the fact IDs that answer the question as evidence.
5. For `invalid`, return the reason without replacing the question.
6. For `valid`, explain the issue without assumed context and identify the evidence that bears on it.
7. When code is relevant, locate exact symbols and inspect only the spans needed to support precise file, line, and symbol anchors.
8. Produce two to five options that differ materially in action, consequence, or trade-off.
9. State one objective leaning and its evidence-based reason.
10. If essential evidence is unavailable, identify the missing input as a blocker rather than filling gaps by inference.

## Output

- Echo the facts, Open, and batch digests exactly.
- Return validity and a concise reason.
- For a valid Open, include a zero-context explanation, relevant evidence, code anchors when applicable, distinguishable options, and one leaning with reason.
- Set `blocker` to the precise missing input or `null`.

## Boundaries

- Remain read-only; do not write facts, Opens, Batches, or workflow state.
- Do not interact with the user.
- Do not execute land, defer, skip, or reject.
- Do not select or advance queue position.
- Depend only on supplied inputs, never hidden session state.
- Substantive input changes require a fresh invocation.
- Failure has no side effects.

## Return

Return one object: echoed facts/open/batch digests, `validity`,
`validity_reason`, and `blocker`.

- `validity` is `valid`, `changed`, `resolved`, `invalid`, or `null`.
- `null` means not assessed; return only the blocker-bearing fields.
- `changed` includes `replacement_question`.
- `resolved` includes `resolved_by`.
- `valid` includes explanation, evidence, optional code anchors, two to five
  options, and one leaning.
- Other validity values leave `options` empty and `leaning` null.
