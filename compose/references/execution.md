# execution

Run the revision's single execution from its present state to `Completed`. Do not enter ReadyForDelivery / Deliver.

## Script Macros

Macro expansion: `{SKILL_ROOT}/_runtime.md` § Script Macros → Macro expansion. Non-zero exit → Blocking: stop, report (stderr / exit code), wait for user direction.

Outer macros (`$SESSION_INFO`) remain as defined in the compose SKILL.

| Macro | Command |
|-------|---------|
| `$EXECUTION` | `python3 "$SKILL_ROOT/compose/scripts/session/execution_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$COMPOSE_EVAL_ADAPTER` | `python3 "$SKILL_ROOT/compose/scripts/eval/compose_eval_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)"` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/writing/compose_doc_control.py" <subcommand> [args...]` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_control.py"` |
| `$CHAPTER_WRITE_STATE` | `python3 "$SKILL_ROOT/compose/scripts/writing/chapter_write_state_control.py"` |
| `$WRITING_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose/scripts/writing/compose_writing_control.py" validate --revision-dir "$REVISION_DIR" --compose-doc <path> --project-root "$(pwd)"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/facts/facts_control.py"` |

Subcommands and stdout: script module docstrings or `--help`.

## Bind

Run `$SESSION_INFO --view session` and `$EXECUTION status`. Bind:

| Cite | JSON field | Use |
|------|------------|-----|
| `$INDUCTIVE` | `pipeline.inductive` | Whether to run Inductive before Deductive |
| `$CODE_GROUNDING` | `pipeline.code_grounding` | Writing / Deductive runner Input |
| `$POST_WRITING_OPTIONS` | `pipeline.post_writing_options` | Pause after Writing |
| `$ROLE_PROMPT` | `role.role_prompt` | Scope persona |

Follow `$EXECUTION status` → `next_actions`. `begin-eval-round` means go to **Evaluating** and follow eval/SKILL.md (`$EVAL_CONTROL begin-eval-round`); do not run it as `$EXECUTION`.

## Spine

```text
Pending
  → enter-fact-intake → FactIntake
FactIntake
  → complete-fact-intake
  → enter-inductive → Inductive     when $INDUCTIVE
  → enter-deductive → Deductive     when not $INDUCTIVE
Inductive
  → complete-inductive
  → enter-deductive → Deductive
Deductive
  → complete-deductive
  → enter-writing → Writing
Writing
  → enter-freeedit → FreeEdit     when listed
  → begin-eval-round → Evaluating
FreeEdit
  → begin-eval-round | reverse-to-inductive | reverse-to-deductive | reverse-to-writing
Evaluating
  → accept → Completed | fix → FreeEdit | re-evaluate
Completed
  → reopen → FreeEdit             (outer Reopen only)
```

Evaluating is required. After `Completed`, return to ## Working.

## Scope

Treat `$ROLE_PROMPT` as this execution's scope constraints.

## Fact Intake

1. Run `$EXECUTION enter-fact-intake`. On failure → Blocking.
2. Load `{SKILL_ROOT}/compose/fact-intake-runner/SKILL.md` with stdout as `## Input`. Run inline in this conversation (Confirm is interactive).
3. Run `$EXECUTION complete-fact-intake`. On failure → Blocking.

## Inductive

When `$INDUCTIVE` is true and `next_actions` lists `enter-inductive`:

1. Run `$EXECUTION enter-inductive`. On failure → Blocking.
2. Load `{SKILL_ROOT}/compose/inductive-runner/SKILL.md` with stdout as `## Input`. Run inline in this conversation.
3. Run `$EXECUTION complete-inductive`. On failure → Blocking.

Then continue at **Deductive**.

## Deductive

1. Run `$EXECUTION enter-deductive`. On failure → Blocking.
2. Load `{SKILL_ROOT}/compose/deductive-runner/SKILL.md` with stdout as `## Input`. Run inline in this conversation.
3. Run `$EXECUTION complete-deductive`. On failure → Blocking.

## Writing

1. Run `$EXECUTION enter-writing`. On failure → Blocking.
2. Load `{SKILL_ROOT}/compose/writing-runner/SKILL.md` with stdout as `## Input`.
3. Run `$EXECUTION complete-writing`. On failure → Blocking.
4. Offer only remaining `$POST_WRITING_OPTIONS` (`freeedit` and/or `evaluate`).

## FreeEdit

User-driven edits to the generated compose document. Entry: writing pause, outer Backtrack, Fix, or Reopen. Document remains valid. When done, follow remaining `$POST_WRITING_OPTIONS` or Reverse.

## Reverse

- `$EXECUTION reverse-to-inductive` (only when `$INDUCTIVE`) returns to Inductive. Derived facts are already cleared by this command. On success, the switch is done.
- `$EXECUTION reverse-to-deductive` returns to Deductive. Derived facts are already cleared by this command. On success, the switch is done.
- `$EXECUTION reverse-to-writing` returns to Writing and regenerates the document from facts.

Do not offer `reverse-to-inductive` when `$INDUCTIVE` is false.

## Evaluating

1. Run `$COMPOSE_EVAL_ADAPTER`. Pin `adapter_config_file` as `$EVAL_ADAPTER_CONFIG`.
2. Load `{SKILL_ROOT}/eval/SKILL.md` and follow it. `$EVAL_CONTROL begin-eval-round` owns prepare, Evaluating transition, and handoff. Do not run `$EXECUTION enter-evaluating` first.
3. On Eval exit, this reference owns the step transition. Eval SKILL does not run `$EXECUTION`.
   - Accept → `$EXECUTION accept --confirm`. Return to ## Working.
   - Fix → `$EXECUTION fix --confirm`. Continue **FreeEdit**.
   - Re-evaluate → `$EXECUTION re-evaluate --confirm`, then return to Eval **Begin Eval**.

## Reopen

When outer `next_actions` includes `reopen-current`: `$EXECUTION reopen --confirm`, then **FreeEdit**.

## Return

On `Completed`, stop this reference. Do not deliver.

## Reference

| Document | When |
|----------|------|
| `{SKILL_ROOT}/compose/inductive-runner/SKILL.md` | `$INDUCTIVE` true |
| `{SKILL_ROOT}/compose/deductive-runner/SKILL.md` | After Fact Intake, or after Inductive |
| `{SKILL_ROOT}/compose/fact-intake-runner/SKILL.md` | Fact Intake |
| `{SKILL_ROOT}/compose/chapter-write-runner/SKILL.md` | Writing assemble |
| `{SKILL_ROOT}/compose/inductive-runner/open-point-detect-runner/SKILL.md` | Inductive Open detection |
| `{SKILL_ROOT}/compose/inductive-runner/open-point-process-runner/SKILL.md` | Inductive Open processing |
| `{SKILL_ROOT}/compose/inductive-runner/recompose-runner/SKILL.md` | Inductive runner internal |
| `{SKILL_ROOT}/compose/writing-runner/SKILL.md` | Writing |
| `{SKILL_ROOT}/eval/SKILL.md` | Evaluating |
