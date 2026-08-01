# Ask Protocol

Shared question discipline for decision runners that cite this file.

**Force:** soft obligation (no script gate). Skip or shallow Explore degrades
question quality; it does not mechanically block `gate-close`.

**Apply when:** the citing runner says so — typically before each user-facing
**probe** question. Do not assume every gate mode (e.g. summarize G8) uses this
file unless that runner binds it.

## Before each applicable question

1. **G7 first** — If the user already stated the needed information, quote +
   restate + confirm. Do not re-ask; do not Explore for theatre.
2. **Minimal Explore** — Check files, docs, and recent commits **relevant to
   this question** (same spirit as brainstorming “Explore project context”).
   - Reuse claims already verified in **this gate** session; do not rescan the
     same claim.
   - Pure-intent questions with little code surface: still read bound session
     materials relevant to the ask (e.g. locked Q payload, related
     `context_docs`). If no implementation hit: note that, then ask.
3. **Project-ground** — Let Explore constrain wording and the recommendation.
   Do not invent repository facts. No fixed sentence template.
4. **Recommend** — Either:
   - open prompt + one recommended answer + one-line why, or
   - numbered plain-text options (G2; no selection UI) with exactly one marked
     recommended + one-line why.
   Prefer-only: user may reject; recommendation does not block gate-close.

## Global rules (do not redefine)

- **G1** — one question per user-visible turn.
- **G2** — numbered plain text when options help; no checkbox / selection UI.
- **G7** — Collect-or-Ask as above.
- Gate **ask-domain** / Cognitive map bounds still win: this protocol does not
  widen what the gate may ask about.
