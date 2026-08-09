# Ask Protocol

Shared question discipline for flows that cite this file.

**Force:** Application is required where a caller binds this protocol. It has no
mechanical gate; shallow or skipped grounding degrades question quality but does
not itself block a caller's close operation.

**Apply when:** The citing flow says so. Do not assume every dialogue mode uses
this protocol.

## Before each applicable question

1. **Bound the candidate first** — Establish the one gap or decision candidate
   the question will address. Do not explore without a bounded ask.
2. **Collect-or-Ask first** — If the user already stated the needed
   information, quote + restate + confirm. Do not re-ask or Explore for theatre.
3. **Minimal Explore** — Check files, docs, and recent commits relevant to this
   question.
   - Reuse claims already verified in the current flow; do not rescan the same
     claim.
   - Pure-intent questions with little code surface still read the caller's
     bound session materials. If no implementation hit exists, note that and
     continue; absence of a hit is not by itself a blocker.
4. **Project-ground** — Let Explore constrain wording and the recommendation.
   Do not invent repository facts. Use no fixed sentence template.
5. **Recommend** — Either:
   - open prompt + one recommended answer + one-line why, or
   - numbered plain-text options with exactly one marked recommended + one-line
     why.
   The recommendation is prefer-only: the user may reject it.

## Shared rules

- **Ask Protocol G1** — One question per user-visible turn.
- **Ask Protocol G2** — Use numbered plain text when options help; no checkbox
  or selection UI.
- **Ask Protocol G7** — Collect-or-Ask as defined above.
- The caller's ask-domain and cognitive bounds still win. This protocol does
  not widen what a flow may ask about.
