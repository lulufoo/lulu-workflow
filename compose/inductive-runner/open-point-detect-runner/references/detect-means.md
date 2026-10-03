> Part of open-point-detect-runner · loaded from `../SKILL.md`

# Detect means

AI methods that run in one human-started Detect pass. Each method
names its question, its evidence, and its stamp.

## `probe`

Ask, for every `kw_criteria` row in the packet, whether the facts are
silent or unresolved on failure, boundary, assumption, or seam. Report
every such point, not one per row. Tag each candidate with its row `kw`.

Evidence is this lens's `facts_snapshot` plus this lens's
`lens_registry` Intent and boundary. Both come from
`detect-lens-context`. An empty `facts_snapshot` is legal.

A hit is silence or an unresolved question. Silence on a row whose
subject is absent from this slice's facts is not a hit. Skip
already-settled questions. Do not judge correctness.

Stamp `actor=ai`, `means=probe`.
