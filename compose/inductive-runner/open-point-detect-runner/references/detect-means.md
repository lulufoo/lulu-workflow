> Part of open-point-detect-runner · loaded from `../SKILL.md`

# Detect means

AI methods that run in one human-started Detect pass. Each method
names its question, its evidence, and its stamp.

## `probe`

Ask whether the `gap_kw` row is silent or unresolved on failure,
boundary, assumption, or seam.

Evidence is this lens's `facts_snapshot` plus this lens's
`lens_registry` Intent and boundary. Both come from
`detect-lens-context`. An empty `facts_snapshot` is legal.

A hit is silence or an unresolved question. Skip already-settled
questions. Do not judge correctness; that is G4.

Stamp `actor=ai`, `means=probe`.
