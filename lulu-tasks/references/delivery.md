# Delivery

Hand off the admitted work order. `$TT_FLOW` is already defined.

## Script Macros

| Macro | Command |
|-------|---------|
| `$TT_DELIVER` | `$TT_FLOW deliver` |

## Rules

1. Read `../_transitions.md`.
2. Feature runs `$TT_DELIVER`, outputs `task_paths`, and starts `lulu-code` without offering the next stage.
3. Topic waits for an explicit delivery confirmation, then runs `$TT_DELIVER` and outputs `task_paths`.
