# l-execution

Run the current focus L from its present state to `Completed`. Do not change focus, freeze other L, or enter ReadyForDelivery / Deliver.

## Script Macros

Macro expansion: `{SKILL_ROOT}/_runtime.md` § Script Macros → Macro expansion. Non-zero exit → Blocking: stop, report (stderr / exit code), wait for user direction.

Outer macros (`$SESSION_INFO`, `$L_SHELL`) remain as defined in the compose SKILL.

Fetch compose framework templates on demand. Scheme roles: `schemes/compose-template-scheme.json` (mapped per profile in `compose-profile.json` → `framework_templates`).

| Macro | Command |
|-------|---------|
| `$L_STEP` | `python3 "$SKILL_ROOT/compose/scripts/section/l_step_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$INDUCTIVE_FACTS_PROJ` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_facts_projection.py"` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$EVAL_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/core/compose_eval_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" -- <subcommand>` |
| `$FACT_INTAKE_EVAL_CTL` | `python3 "$SKILL_ROOT/compose/fact-intake-runner/fact-intake-eval/scripts/fact_intake_eval_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" -- <subcommand>` |
| `$ATOMIZE_EVAL_CONTROL` | Same command as `$FACT_INTAKE_EVAL_CTL` (retired name; prefer `$FACT_INTAKE_EVAL_CTL`) |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/section/compose_doc_control.py" <subcommand> [args...]` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_control.py"` |
| `$CHAPTER_WRITE_STATE` | `python3 "$SKILL_ROOT/compose/scripts/section/chapter_write_state_control.py"` |
| `$WRITING_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose/scripts/section/writing_compose_validation.py" validate --revision-dir "$REVISION_DIR" --compose-doc <path> --project-root "$(pwd)"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |

Subcommands and stdout: script module docstrings or `--help`.

## Bind

Run `$SESSION_INFO --view session` and `$L_STEP status`. Bind:

| Cite | JSON field | Use |
|------|------------|-----|
| `$INDUCTIVE` | `pipeline.inductive` | Producer route |
| `$CODE_GROUNDING` | `pipeline.code_grounding` | Writing / Deductive runner Input |
| `$POST_WRITING_OPTIONS` | `pipeline.post_writing_options` | Pause after Writing |
| `$ROLE_PROMPT` | `role.role_prompt` | Scope persona |

Follow `$L_STEP status` → `next_actions`. `begin-eval-round` means go to **Evaluating** and run `$EVAL_CONTROL begin-eval-round`; do not run it as `$L_STEP`.

## Spine

```text
Pending
  → enter-producer → Inductive | Deductive   ($INDUCTIVE)
Inductive | Deductive
  → enter-writing → Writing
Writing
  → enter-freeedit → FreeEdit     when listed
  → begin-eval-round → Evaluating
FreeEdit
  → begin-eval-round | reverse-to-producer | reverse-to-writing
Evaluating
  → accept → Completed | fix → FreeEdit | re-evaluate
Completed
  → reopen → FreeEdit             (outer Reopen only)
```

Evaluating is required. After `Completed`, return to ## Working. Do not call `$L_SHELL advance`.

## Scope

Treat `$ROLE_PROMPT` as this L's scope constraints.

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

User-driven edits to the generated compose document. Entry: writing pause, outer Backtrack, Fix, or Reopen. Document remains valid. When done, follow remaining `$POST_WRITING_OPTIONS` or Reverse.

## Reverse

- `$L_STEP reverse-to-producer` keeps existing facts; producer must run again; then Writing regenerates the document.
- `$L_STEP reverse-to-writing` returns to Writing and regenerates the document from facts.

Then continue at **Producer** or **Writing**.

## Evaluating

1. Load `{SKILL_ROOT}/eval/SKILL.md` and follow it. `$EVAL_CONTROL begin-eval-round` owns prepare, Evaluating transition, and handoff. Do not run `$L_STEP enter-evaluating` first.
2. On Eval exit, this reference owns the L transition. Eval SKILL does not run `$L_STEP`.
   - Accept → `$L_STEP accept --confirm`. Return to ## Working.
   - Fix → `$L_STEP fix --confirm`. Continue **FreeEdit**.
   - Re-evaluate → `$L_STEP re-evaluate --confirm`, then return to Eval **Begin Eval**.

## Reopen

When outer `next_actions` includes `reopen-current`: `$L_STEP reopen --confirm`, then **FreeEdit**.

## Return

On `Completed`, stop this reference. Do not advance, unfreeze, or deliver.

## Reference

| Document | When |
|----------|------|
| `{SKILL_ROOT}/compose/inductive-runner/SKILL.md` | `$INDUCTIVE` true |
| `{SKILL_ROOT}/compose/deductive-runner/SKILL.md` | `$INDUCTIVE` false |
| `{SKILL_ROOT}/compose/fact-intake-runner/SKILL.md` | Producer fact intake |
| `{SKILL_ROOT}/compose/narrative-arc-runner/SKILL.md` | Inductive topic loop / Writing |
| `{SKILL_ROOT}/compose/chapter-write-runner/SKILL.md` | Writing assemble |
| `{SKILL_ROOT}/compose/inductive-runner/open-point-detect-runner/SKILL.md` | Inductive Open detection |
| `{SKILL_ROOT}/compose/inductive-runner/open-point-process-runner/SKILL.md` | Inductive Open processing |
| `{SKILL_ROOT}/compose/inductive-runner/g4-recompose-runner/SKILL.md` | Inductive runner internal |
| `{SKILL_ROOT}/compose/writing-runner/SKILL.md` | Writing |
| `{SKILL_ROOT}/eval/SKILL.md` | Evaluating |
