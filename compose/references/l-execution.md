# L execution

Run the current focus L from its present state to `Completed`. Do not change focus, freeze other L, or enter ReadyForDelivery / Deliver.

## Bind

Run `$SESSION_INFO --view session` and `$L_STEP status`. Bind:

| Cite | JSON field | Use |
|------|------------|-----|
| `$INDUCTIVE` | `pipeline.inductive` | Producer route |
| `$CODE_GROUNDING` | `pipeline.code_grounding` | Writing / Deductive runner Input |
| `$POST_WRITING_OPTIONS` | `pipeline.post_writing_options` | Pause after Writing (no `deliver`) |
| `$ROLE_PROMPT` | `role.role_prompt` | Scope Constraints persona |

Follow `$L_STEP status` → `next_actions`. Subcommands: `$L_STEP --help`.

## Spine

```text
Pending
  → enter-producer → Inductive | Deductive   ($INDUCTIVE)
Inductive | Deductive
  → enter-writing → Writing
Writing
  → enter-freeedit → FreeEdit     when listed
  → enter-evaluating → Evaluating
FreeEdit
  → enter-evaluating | reverse-to-producer | reverse-to-writing
Evaluating
  → accept → Completed | fix → FreeEdit | re-evaluate
Completed
  → reopen → FreeEdit             (outer reopen-current only)
```

Evaluating is required. After `Completed`, return to the outer Working loop. Do not call `$L_SHELL advance`.

## Scope constraints

Treat `$ROLE_PROMPT` as this L's Scope Constraints.

## Producer

1. Run `$L_STEP enter-producer`. On failure → Blocking.
2. If `$INDUCTIVE` is true, load `{SKILL_ROOT}/compose/inductive-runner/SKILL.md` with stdout as `## Input`. Otherwise load `{SKILL_ROOT}/compose/deductive-runner/SKILL.md`. Run inline in this conversation.
3. Run `$L_STEP complete-producer`. On failure → Blocking.

## Writing

1. Run `$L_STEP enter-writing`. On failure → Blocking.
2. Load `{SKILL_ROOT}/compose/writing-runner/SKILL.md` with stdout as `## Input`.
3. Run `$L_STEP complete-writing`. On failure → Blocking.
4. Offer only remaining `$POST_WRITING_OPTIONS` (`freeedit` and/or `evaluate`).

## FreeEdit

User-driven edits to the generated compose document. Entry: writing pause, outer backtrack, Fix, or reopen. Document remains valid. When done, follow remaining `$POST_WRITING_OPTIONS` or Reverse.

## Reverse

- `$L_STEP reverse-to-producer` keeps `_facts.json`; producer must run again; then Writing regenerates the document.
- `$L_STEP reverse-to-writing` returns to Writing and regenerates the document from facts.

Then continue at **Producer** or **Writing**.

## Evaluating

1. Run `$L_STEP enter-evaluating`. On failure → Blocking.
2. Run `$EVAL_HANDOFF request-handoff`. On failure → Blocking.
3. Load `{$SKILL_ROOT}/eval/SKILL.md` and follow it.
4. On Eval exit:
   - Accept → `$L_STEP accept --confirm`. Return to the outer loop.
   - Fix → `$L_STEP fix --confirm`. Continue **FreeEdit**.
   - Re-evaluate → `$L_STEP re-evaluate --confirm`, then `$EVAL_HANDOFF request-handoff` again.

## Reopen

When outer `next_actions` includes `reopen-current`: `$L_STEP reopen --confirm`, then **FreeEdit**.

## Return

On `Completed`, stop this reference. Do not advance, unfreeze, or deliver.

## Reference documents

| Document | When |
|----------|------|
| `{SKILL_ROOT}/compose/inductive-runner/SKILL.md` | `$INDUCTIVE` true |
| `{SKILL_ROOT}/compose/deductive-runner/SKILL.md` | `$INDUCTIVE` false |
| `{SKILL_ROOT}/compose/fact-intake-runner/SKILL.md` | Producer fact intake |
| `{SKILL_ROOT}/compose/narrative-arc-runner/SKILL.md` | Inductive topic loop / Writing |
| `{SKILL_ROOT}/compose/chapter-write-runner/SKILL.md` | Writing assemble |
| `{SKILL_ROOT}/compose/inductive-runner/g3-shallow-grounding-runner/SKILL.md` | Optional inductive grounding |
| `{SKILL_ROOT}/compose/inductive-runner/g3-deep-grounding-runner/SKILL.md` | Optional inductive grounding |
| `{SKILL_ROOT}/compose/inductive-runner/g4-recompose-runner/SKILL.md` | Inductive runner internal |
| `{SKILL_ROOT}/compose/inductive-runner/g5-provenance-runner/SKILL.md` | Inductive runner internal |
| `{SKILL_ROOT}/compose/writing-runner/SKILL.md` | Writing |
| `{$SKILL_ROOT}/eval/SKILL.md` | Evaluating |
