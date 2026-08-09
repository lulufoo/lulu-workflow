# Ask Protocol

Required only in dialogue modes that explicitly bind this protocol. It is not
mechanically enforced and does not block the caller's close operation.

## Before each applicable question

1. **Bound the candidate first** — Bound one gap or decision candidate before
   exploring.
2. **Collect-or-Ask first** — If the user already stated the needed
   information, quote + restate + confirm. Do not re-ask or Explore for theatre.
3. **Explore to sufficiency** — Use relevant, current evidence already available
   in the flow; inspect additional project sources only to resolve remaining
   uncertainty. Exploration is sufficient when the evidence materially
   constrains the candidate's scope, viable answers, consequences, or
   recommendation. If no relevant evidence is found, preserve the uncertainty
   and continue. Do not reopen the caller's underlying judgment.
4. **Ground the candidate** — Apply the material evidence to the candidate
   question and, where required, its recommendation. Include only facts needed
   for the user's judgment—not search logs or decorative context. If the
   evidence does not change the candidate, it is not grounded. Keep unsupported
   matters unknown; never invent project facts. Use no fixed template.
5. **Recommend** — Provide exactly one prefer-only recommendation with a
   one-line rationale, either as an answer to an open prompt or as the marked
   item in numbered plain-text options. The user may reject it.

## Shared rules

- **Ask Protocol G1** — One question per user-visible turn.
- **Ask Protocol G2** — Use numbered plain text when options help; no checkbox
  or selection UI.
- The caller's ask-domain and cognitive bounds prevail; this protocol does not
  widen them.
