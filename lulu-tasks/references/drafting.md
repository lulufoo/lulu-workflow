# Drafting

Compose the task-dependency list and each task. `$TT_FLOW` is already defined.

## Script Macros

| Macro | Command |
|-------|---------|
| `$TT_PUT_LIST` | `$TT_FLOW put-task-list` |
| `$TT_PUT_TASK` | `$TT_FLOW put-task` |
| `$TT_ENTER_EVAL` | `$TT_FLOW enter-evaluating` |

Pass each body on stdin.

## Rules

1. Read `$SKILL_DIR/templates/31-work-order-tasklist-template.md`, `$SKILL_DIR/templates/30-work-order-task-template.md`, and the plan at `$CTX.tech_ref`.
2. When `$CTX.evaluate_round` is 0, compose the task-list and pass it to `$TT_PUT_LIST`. Feature continues. Topic waits until the user confirms the split.
3. On that first pass, compose each task and pass it to `$TT_PUT_TASK`. `kind: coding`: acceptance criteria come before function specs. `tdd_exempt: true` may set acceptance criteria to `N/A`. Read code only for the signature being specified. `kind: action`: state the goal in `title`, declare `effects` (and `mutates` when it writes to a system), and write acceptance criteria as observable conditions that evidence can answer one by one. Add `execution_worktree` and `target_repo` only when the action must run inside a worktree. Word the goal so re-running it is safe. Do not write function specs. Do not read code for a signature.
4. When `$CTX.evaluate_round` is greater than 0, repair the passages cited by `$CTX.last_issues` (`location`, `description`). Pass a revised task-list to `$TT_PUT_LIST`, and each revised task to `$TT_PUT_TASK`.
5. Feature runs `$TT_ENTER_EVAL` immediately. Topic asks, then runs `$TT_ENTER_EVAL` after the user confirms.
6. Return to the entry router.
