> Part of open-point-detect-runner · loaded from `../SKILL.md`

# Detect means

Three AI methods run in one human-started Detect pass. Missing material
makes that method inert. Do not invent gaps to fill a method. Do not
restore a capability catalog.

AI candidates must leave the coarsest remaining KW predicate false for
their `lens`, measuring from that lens's frontier start. Finer rows are
dropped. Human-pointed gaps skip this filter.

When more than one method hits the same gap, register one Open. Stamp the
primary method. Other hits may appear in `basis`.

## `scan`

Ask whether design or facts at the coarsest remaining KW match code
reality: paths the change touches, caller assumptions, and cross-module
contracts.

Evidence is the project evidence scope (symbols and necessary lines, not
whole files). Run only when `code_grounding` is true and
`project_evidence_scope` is present. Otherwise this method is inert.

Stamp `actor=ai`, `means=scan`.

## `intent`

Ask whether classified intent-baseline items that map to this lens are
still unfulfilled by current facts or Opens.

Evidence is `intent_baseline_refs`. An empty array makes this method
inert. Do not use norm constraints.

Stamp `actor=ai`, `means=intent`.

## `probe`

Ask whether the coarsest remaining KW is silent or unresolved on
failure, boundary, assumption, or seam.

Evidence is the slice facts plus registry Intent, boundary, and facets.
No extra material. Missing facts or registry fails the whole Detect
pass, not this method alone.

A hit is silence or an unresolved question that also leaves the
coarsest remaining KW predicate false. Skip already-settled questions.
Do not judge correctness; that is G4.

Stamp `actor=ai`, `means=probe`.
