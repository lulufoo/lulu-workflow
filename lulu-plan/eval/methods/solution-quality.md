# Plan Solution Quality Method

**Role:** EvalMethod (M) for `lulu-plan` dimension `solution-quality`.
**Status:** ⚠️ Proposed runtime template.

## Boundary

This Method defines how to evaluate EvalTarget **B** using the loaded EvalSoT
**A**. It does not define the P1–P4 quality criteria.

## Procedure

1. Evaluate **B** only. Do not read compose sidecars, fact files, body files,
   state vectors, layer standards, diagnostic criteria, or section registries.
2. Read `eval/scripts/eval_target_units.py` and build the unit view with
   `eval_target_units.units_from_eval_target(B_text)`.
3. Branch on the view shape:
   - `unknown`: emit one `UNRESOLVABLE` finding because B has no chapter
     anchors; stop.
   - `empty: true`: apply only criteria in A that explicitly apply to empty
     content.
   - `chapter`: continue with the chapter procedure.
4. Traverse chapters and their units in document order. Run every applicable
   P1–P4 criterion from A for each unit.
5. For P3, use `prior_container_units(view, container_id)` as the complete
   upstream set. If no prior chapters exist, skip P3 when its criterion
   requires upstream content.
6. Use `severity_hints_chapter(view, container_id)`:
   - P1 failure on the first chapter or a chapter with prior content:
     `critical`.
   - P2 failure before the last chapter: `critical`.
   - P3 failure when prior content exists: `critical`.
   - P4 failure on the last chapter: `critical`.
   - Remaining applicable P1/P2/P4 failures: `medium`.
7. For each finding, set `root_cause: WO-ERROR`, use the SoT criterion as
   `sot_ref`, use the unit id as `location`, and write the criterion's Gap
   output as `description`. Set `status: pending` and `decision: —`.

## Output Contract

Each finding must contain `id`, `root_cause`, `sot_ref`, `location`,
`severity`, `evidence`, `description`, `status`, and `decision`. Prefix `id`
with the dispatched `DIMENSION` value.
