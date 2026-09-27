# Evaluating

Probe the work order. The probe does not edit it. `$TT_FLOW` is already defined.

## Script Macros

| Macro | Command |
|-------|---------|
| `$TT_EVAL` | `python3 "$SKILL_DIR/scripts/tt_eval_control.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$TT_APPLY` | `$TT_FLOW apply-eval-disposition --disposition-json '<route JSON>'` |

## Rules

1. Run `$TT_EVAL begin-pass`. A non-zero result is Blocking.
2. Pin `$EVAL_ADAPTER_CONFIG` to `$SKILL_DIR/eval/eval-profile.json`.
3. Load `$SKILL_ROOT/eval/SKILL.md` and execute its **Begin Eval** probe-only segment.
4. Pin the successful `complete-probe-only` JSON.
5. Run `$TT_EVAL route-probe-result` with that JSON, then `$TT_APPLY` with the route JSON.
6. `disposition: continue` returns to step 3. The next probe is `next_phase`.
7. `disposition: drafting` or `disposition: ready` returns to the entry router.
8. A non-zero result is Blocking.
