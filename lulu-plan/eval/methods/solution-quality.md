# Plan Solution Quality Method

**Role:** EvalMethod (M) for `lulu-plan` dimension `solution-quality`.
**Status:** ⚠️ Proposed runtime template.

## Boundary

This Method defines how to evaluate EvalTarget **B** using the loaded EvalSoT
**A**. It does not define the P1–P5 quality criteria.

## Procedure

1. Evaluate **B** only. Do not read compose sidecars, fact files, body files,
   state vectors, layer standards, diagnostic criteria, or section registries.
2. Run `$READ_UNIT_VIEW`. Treat the returned `shape`, `containers`, and
   `empty` as the unit view.
3. Branch on the view shape:
   - `unknown`: emit one `UNRESOLVABLE` finding because B has no chapter
     anchors; stop.
   - `empty: true`: apply only criteria in A that explicitly apply to empty
     content.
   - `chapter`: continue with the chapter procedure.
4. Traverse chapters and their units in document order. Run every applicable
   P1–P5 criterion from A for each unit.
5. For P3, use units from containers strictly before the current chapter
   (document order) as the complete upstream set. If no prior chapters exist,
   skip P3 when its criterion requires upstream content.
6. For P5, inspect B only. Do not read upstream documents, original dialogue,
   or any source that could attribute the ambiguity. Derive competing
   interpretations only from B's explicit wording. Report only alternatives
   that differ on external contract, acceptance, or implementation boundary.
7. Use chapter position among `containers`:
   - P1 failure on the first chapter or a chapter with prior content:
     `critical`.
   - P2 failure before the last chapter: `critical`.
   - P3 failure when prior content exists: `critical`.
   - P4 failure on the last chapter: `critical`.
   - Every P5 failure: `critical`.
   - Remaining applicable P1/P2/P4 failures: `medium`.
8. For P1–P4 findings, set `root_cause: WO-ERROR`, use the SoT criterion as
   `sot_ref`, use the unit id as `location`, and write the criterion's Gap
   output as `description`. Set `status: pending` and `decision: —`.
9. For every P5 finding, set `root_cause: DECISION-REQUIRED`,
   `severity: critical`, `sot_ref: solution-quality.md#p5`, and the unit id as
   `location`. Include both candidates, their material difference, and the
   missing decision or multi-option rule in `description`. Set `status:
   pending`, `decision: —`, and an empty `resolution`. Do not choose or write either
   candidate into B.

## Output Contract

Each finding must contain `id`, `root_cause`, `sot_ref`, `location`,
`severity`, `evidence`, `description`, `status`, `decision`, and `resolution`.
Prefix `id` with the dispatched `DIMENSION` value.
