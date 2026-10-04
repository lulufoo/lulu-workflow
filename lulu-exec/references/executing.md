# Executing

Dispatch each work-order task by `kind`. Completion is `$MACRO` stdout, not model judgment.

## Script Macros

| Macro | Command |
|-------|---------|
| `$TC_POINTER` | `python3 "$SKILL_DIR/scripts/tc_session_control.py" --cycle-dir "$CACHE_DIR/$CYCLE_ID" get-pointer` |
| `$TC_CONFIRM` | `python3 "$SKILL_DIR/scripts/tc_session_control.py" --cycle-dir "$CACHE_DIR/$CYCLE_ID" confirm-task-ready --task-id {task_id}` |
| `$TC_ADVANCE` | `python3 "$SKILL_DIR/scripts/tc_session_control.py" --cycle-dir "$CACHE_DIR/$CYCLE_ID" advance-pointer --completed-task {task_id}` |

## Entry

Run `$TC_POINTER`. Follow `next_action`:

- `starting` → Blocking policy
- `prepare` → ## Preparing
- `dispatch` → task loop with `current_task` and `kind`
- `closing` → § Closing
- `done` → session already Delivered

## Task loop

1. Run `$TC_POINTER`. Pin `current_task` and `kind`.
2. Dispatch `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`.
   If pointer `subagent` is non-empty, pass it as `model`.
   - `kind: coding` → load `task-runner/SKILL.md`
   - `kind: action` → load `action-runner/SKILL.md`
   Prompt `## Input` must be this JSON (no other launch payload):

   ```
   {
     "task_id": "{task_id}",
     "cycle_dir": "{absolute $CACHE_DIR/$CYCLE_ID}"
   }
   ```
3. `TASK_FAILED` → Blocking policy.
4. **Feature container** (`$CYCLE_TYPE == feature`): On `TASK_COMPLETE`, auto-confirm — proceed to `confirm-task-ready` and Step 5 without waiting for user approval.

   **Topic container** (`$CYCLE_TYPE == topic`): Wait for explicit user confirmation before running `confirm-task-ready`.
5. Run `$TC_CONFIRM`. Non-zero → Blocking policy.
6. Output CHECKPOINT immediately:
   - `coding` and `next_task_id` set → `CHECKPOINT t{X}: commit SHA <initial_commit>, task commit recorded, advancing to <next_task_id>.`
   - `coding` and `next_task_id` null → `CHECKPOINT t{X}: commit SHA <initial_commit>, task commit recorded, advancing to Closing.`
   - `action` and `next_task_id` set → `CHECKPOINT t{X}: receipt recorded, advancing to <next_task_id>.`
   - `action` and `next_task_id` null → `CHECKPOINT t{X}: receipt recorded, advancing to Closing.`
7. Run `$TC_ADVANCE`. `dispatch` → Step 1 with the new `current_task`. `closing` → § Closing.
