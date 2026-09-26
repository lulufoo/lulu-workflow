# Ask Protocol

Required only in dialogue modes that explicitly bind this protocol. It is not
mechanically enforced and does not block the caller's close operation.

## Evidence Classes

Evidence is classified by who is authoritative for it.

1. **Intent** — what the user wants, prefers, or excludes. The user's
   statement is authoritative and settles it.
2. **Project state** — existing code, interfaces, data, or behavior. Only
   project sources (code, schemas, docs, tool output) are authoritative; a
   user restatement does not settle it.

## Before each candidate is settled

A candidate is any judgment, recommendation, or option set presented for the
user's settlement — with or without a question.

1. **Bound the candidate first** — Bound one gap or decision candidate before
   exploring.
2. **Collect-or-Ask (intent)** — If the user already stated the needed intent,
   quote + restate + confirm. Do not re-ask or Explore for theatre.
3. **Settle project-state premises** — Each project-state premise the
   candidate depends on is either verified against project sources or logged
   as an Assumption through the caller's register path. Use evidence already
   in the flow first; inspect further project sources only for premises still
   unverified. Exploration is sufficient when no depended-on premise remains
   unverified and unlogged. Do not reopen the caller's underlying judgment.
4. **Ground the candidate** — Apply the material evidence to the candidate
   and, where required, its recommendation. Present the candidate with its
   evidence anchor or Assumption reference. Include only facts needed for the
   user's judgment. Keep unsupported matters unknown; never invent project
   facts. Use no fixed template.
5. **Recommend** — Provide exactly one prefer-only recommendation with a
   one-line rationale, either as an answer to an open prompt or as the marked
   item in numbered plain-text options. The user may reject it.

## Shared rules

- **Ask Protocol G1** — One question per user-visible turn.
- **Ask Protocol G2** — Use numbered plain text when options help; no checkbox
  or selection UI.
- The caller's ask-domain and cognitive bounds prevail; this protocol does not
  widen them.
