> Part of chapter-write-runner · loaded from `write-protocol.md`.

# Chapter body contract

What a written chapter body must and must not do. Only what the scripts do
not check lives here. Cognition: `../../references/cognition/writing/chapter.md`.

## Must

1. Operationalize fact substance into readable prose; every listed chapter
   gets a non-empty body.
2. Mark missing substance with `> **待决：** …`; never fill it.
3. Carry every placed fact's anchors as concrete tokens (L6).

## Must not

1. Paste decision text verbatim or write `[Source:` markers.
2. Speculate outside the slice, or restate another chapter's propositions.
3. Emit `decision-doc-mapping` or `<!-- section-key:… -->` anchors.

## L6 — keep these apart

1. "No verbatim" forbids whole-decision paste; it does not forbid a path or
   symbol appearing in prose.
2. A lens's "no path pile-up in the opening" stays scoped to the opening;
   it is not a body-wide ban on paths.
3. Never replace a registered anchor with a hypernym; the concrete token
   must appear.

## Boundary

Detect owns KW gaps; Eval owns intent fidelity and scope continuity.
Writing closes neither.
