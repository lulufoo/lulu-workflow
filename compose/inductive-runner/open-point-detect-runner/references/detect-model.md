> Part of open-point-detect-runner · loaded from `../SKILL.md`

# Detect model

Object semantics for one Detect pass. Methods live in `detect-means.md`.

## Open (candidate)

A candidate is one unresolved question that matters to the current slice.
Subtract questions already settled by facts or already represented by
existing Opens.

## Detect receipt

Immutable evidence of one complete lens inspection.

- Binds the inspected facts, lenses, existing Opens, and the
  lens-frontier digest.
- Per lens: start KW and found gap KW, or no gap.
- Keeps the raw outcome and the registered Open identities.
- Zero result: raw detection produced no candidates. Dropping candidates
  after detection is not a zero result.
- Supports closure only while bound inputs remain current.
