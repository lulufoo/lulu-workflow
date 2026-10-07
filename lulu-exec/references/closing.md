# Closing

Deliver the session. `$TC_FLOW` is already defined.

## Script Macros

| Macro | Command |
|-------|---------|
| `$TC_DELIVER` | `$TC_FLOW deliver` |

## Rules

1. Feature container (`$CYCLE_TYPE == feature`): run `$TC_DELIVER` without asking.
2. Topic container (`$CYCLE_TYPE == topic`): wait for explicit confirmation, then `$TC_DELIVER`.
3. Non-zero `$TC_DELIVER` is Blocking.
4. Return to the entry router.
