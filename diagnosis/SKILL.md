---
name: diagnosis
description: >-
  Make one problem's conditions, mechanism, and consequences restatable.
  Does not solve the problem. Use when: /diagnosis, 诊断这个问题, 弄清前因后果.
argument-hint: "<Question>"
---

# diagnosis

Diagnose one problem by making its situation restatable. Complete when that
picture — including any named holes — is restatable.

## Activation

Activate only on an explicit diagnosis request.

1. Activate on `/diagnosis`, `诊断这个问题`, `弄清前因后果`, or an unambiguous request
   to restate one problem's situation.
2. Never self-activate merely because a bug report, uncertainty, or incomplete
   answer is present.
3. Use relevant material already in the conversation.

## Inputs

`Question` is required; `Completion` is optional and user-given only.

1. Pin the `Question` — the problem being diagnosed. If the user frames a fix
   request, pin the underlying problem.
2. Missing or unrestatable `Question` → hand back `/grill` with Goal = make
   the Question restatable. Do not start `/grill`. Stop until the Question
   is restatable.
3. Accept `Completion` only when the user already gave one. Do not solicit or
   propose it.
4. If `/grill` is declined or does not return a restatable Question, stop.
   State is `Gap`; reason under `Unresolved`.

## Picture

The object of diagnosis is the problem's situation, not a solution.

1. Form a restatable Picture of conditions, mechanism, and consequences from
   the conversation and available evidence.
2. Omit a limb that does not apply to this `Question`.
3. A corrected `Question` replaces the pinned `Question`; reassess the Picture.

## State

Assign exactly one state. `Gap` and `Contradiction` are valid exits.

| State | When |
|-------|------|
| `Covered` | The Picture is restatable, has no contradiction, and meets `Completion` when one was given. |
| `Gap` | A needed limb is missing or not restatable, or the Picture fails a user-given `Completion`. |
| `Contradiction` | The Picture conflicts with itself or with material evidence. |

Do not keep questioning to force `Covered`.

## Result

Return a compact card. Omit `Completion` when none was given.

```text
Question:
Completion:
Picture:
State: Covered | Gap | Contradiction
Unresolved:
```

Default to chat only. Persist the result only when the user explicitly requests
a destination.

## Boundaries

Still-possible mix-ups on this path.

1. Does not solve, prescribe, or execute a fix.
2. Independent of Decision, X dimensions, gates, registers, and workflow
   payloads. Does not replace `x-full-diagnosis-runner`.
3. Does not own a cycle stage.
4. Conversation-only in v1; no persistence state or scripts.
