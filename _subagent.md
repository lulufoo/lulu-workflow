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
