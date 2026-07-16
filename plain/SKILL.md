---
name: plain
description: >-
  On-demand plain-language explanation mode. Re-explains the current point so it
  is understandable with zero prior context, in the simplest possible language.
  MANUAL TRIGGER ONLY — never self-activate. User triggers with `/plain` (or an
  explicit request to explain plainly). The assistant MAY recommend triggering it
  when the user re-asks the same concept, signals confusion/dissatisfaction, or
  rejects a prior explanation — but must ask first and only activate after the
  user agrees. Use when: /plain, 说人话, 白话, explain plainly, zero-context explain.
---

# plain

Re-explain the current topic in the plainest language, understandable without any
conversation history.

## Activation

- **Manual:** user types `/plain` or explicitly asks for a plain/zero-context explanation.
- **Recommend-only:** when a trigger signal appears (below), the assistant may add one
  line — "Want me to switch to `/plain`?" — and MUST wait for user confirmation.
- **Never self-activate.** Absent explicit user go-ahead, this mode stays off.

### Recommend signals (suggest, do not apply)

1. Same concept re-asked ≥2 times.
2. User shows confusion/dissatisfaction ("没懂", "没说清", "在绕").
3. User rejects the assistant's prior explanation framing.

## Scope

- Applies to the **next reply only** by default.
- If the user says "keep it on" (or equivalent) → stays active until the user turns it off.

## Mandatory actions while active

1. Lead with a one-sentence conclusion / root cause, then expand.
2. No unexplained ad-hoc shorthand. Describe the behavior in plain words instead of coining terms.
3. Use one fixed wording per concept — do not rephrase the same thing across paragraphs.
4. Gloss any internal term (project name, field, identifier) in one sentence on first use; quote it exactly in backticks.
5. Assume zero prior context — the reply must stand alone.
6. End with one confirmation question (e.g. "Does this land?").

## Out of scope

- Does NOT verify the explanation's own logical consistency (separate concern).
- Does NOT change any non-conversation output (docs, code, artifacts).
