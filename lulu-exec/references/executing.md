# Executing

Dispatch each work-order task by `kind`. `$TC_FLOW` is already defined. Completion is `$MACRO` stdout.

<HARD-GATE>
Do NOT proceed until you have read `../../_subagent.md`
</HARD-GATE>

## Script Macros

| Macro | Command |
|-------|---------|
| `$TC_POINTER` | `$TC_FLOW get-pointer` |
| `$TC_CONFIRM` | `$TC_FLOW confirm-task-ready --task-id {task_id}` |
| `$TC_ADVANCE` | `$TC_FLOW advance-pointer --completed-task {task_id}` |

## Task loop

Inside this loop, route only from `$TC_POINTER`. After return, the entry router runs `$TC_CTX`.

1. Run `$TC_POINTER`. Pin `current_task`, `kind`, and `subagent`.
2. Dispatch `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`. Pass `subagent` as `model` when set.
   - `kind: coding` → `task-runner/SKILL.md`
   - `kind: action` → `action-runner/SKILL.md`
   Input: `task_id` and the absolute cycle dir.
3. `TASK_FAILED` → Blocking policy.
4. Feature container: on `TASK_COMPLETE`, run `$TC_CONFIRM`. Topic container: wait for confirmation, then `$TC_CONFIRM`.
5. Announce CHECKPOINT from `$TC_CONFIRM` stdout.
6. Run `$TC_ADVANCE`. `dispatch` → step 1. `closing` → return to the entry router.
