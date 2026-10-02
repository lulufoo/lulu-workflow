# Evaluating

Probe the work order on every dimension in one round, then let Eval remediate task chapters in place. The round is not re-probed. `$TT_FLOW` is already defined.

## Script Macros

| Macro | Command |
|-------|---------|
| `$TT_EVAL` | `python3 "$SKILL_DIR/scripts/tt_eval_control.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$TT_APPLY` | `$TT_FLOW apply-eval-disposition --disposition-json '<route JSON>'` |

## Rules

1. Run `$TT_EVAL begin-pass`. A non-zero result is Blocking.
2. Pin `$EVAL_ADAPTER_CONFIG` to `$SKILL_DIR/eval/eval-profile.json`.
3. Load `$SKILL_ROOT/eval/SKILL.md` and execute **Begin Eval** as a full-round caller through **Remediation**. Completion returns the `remediation-complete` JSON to this unit; pin it.
4. Remediation edits task chapters only. When `apply-remediation` fails with a reason starting `tasks-scope-rejected`, pin that JSON instead and do not retry the remediation.
5. Run `$TT_EVAL route-remediation-result` with the pinned JSON, then `$TT_APPLY` with the route JSON.
6. `disposition: drafting` or `disposition: ready` returns to the entry router.
7. Any other non-zero result is Blocking.
