## Sub-agent Context

| Variable | copilot | cursor | claude | codex |
|----------|---------|--------|--------|-------|
| `$SUBAGENT_TOOL` | TBD | `Task` tool | TBD | TBD |
| `$SUBAGENT_AWAIT_SYNC` | TBD | `run_in_background: false`; block until return | TBD | TBD |
| `$SUBAGENT_AWAIT_ASYNC` | TBD | `run_in_background: true`; await completion notification | TBD | TBD |

### Usage

- **Dispatch** — Invoke `$SUBAGENT_TOOL` with a prompt that loads the target sub-SKILL and the input contract for that agent.
- **Serial** — Single agent: dispatch with `$SUBAGENT_AWAIT_SYNC`; block until return.
- **Parallel** — N agents in one message: each with `$SUBAGENT_AWAIT_ASYNC`; wait for all completion notifications before proceeding.

### Config Resolution

Before dispatching a sub-agent for a workflow stage, resolve the optional model slug from workflow config:

```bash
python3 "$SKILL_ROOT/scripts/resolve_subagent.py" --project-root "$(pwd)" --stage <stage>
```

- stdout is JSON: `{"model": "<slug>"}` when configured, or `{}` when absent or empty.
- **Output variable `$RESOLVED_MODEL`:** non-empty `"model"` → `$RESOLVED_MODEL = <slug>`; absent or empty → `$RESOLVED_MODEL` = (omit — platform default applies).
- Pass `$RESOLVED_MODEL` as the `model` parameter to `$SUBAGENT_TOOL` when set; omit the parameter otherwise.
- Resolve once per stage entry (not once per sub-agent dispatch); `$RESOLVED_MODEL` is stage-scoped, not session-scoped.
