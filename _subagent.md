## Sub-agent Context

| Variable | copilot | cursor | claude | codex |
|----------|---------|--------|--------|-------|
| `$SUBAGENT_TOOL` | `task` tool | `Task` tool | `Task` tool | `spawn_agent` |
| `$SUBAGENT_AWAIT_SYNC` | `task` (foreground); block until return | `run_in_background: false`; block until return | `Task` with `run_in_background: false`; block until return | `spawn_agent` then `wait`; block until return |
| `$SUBAGENT_AWAIT_ASYNC` | `task` with `mode: "background"`; pin agent id; await completion notification | `run_in_background: true`; await completion notification | `Task` with `run_in_background: true`; await completion notification | `spawn_agent` without immediate `wait`; pin handle; `wait` all handles before downstream checks |

### Usage

- **Dispatch** — Invoke `$SUBAGENT_TOOL` with a prompt that loads the target sub-SKILL and the input contract for that agent.
- **Serial** — Single agent: dispatch with `$SUBAGENT_AWAIT_SYNC`; block until return.
- **Parallel** — N agents in one message: each with `$SUBAGENT_AWAIT_ASYNC`; wait for all completion notifications before proceeding.
- **Codex prerequisite** — `[features] multi_agent = true` in `~/.codex/config.toml` (enables `spawn_agent`, `wait`, `close_agent`).
- **Copilot parallel caveat** — Background agents require `read_agent` / `list_agents`; these tools are unavailable in plan mode.

### Async handle

- On `$SUBAGENT_AWAIT_ASYNC` dispatch, pin the returned agent id as `{scope}_handle`.
- **cursor / claude** — pin returned agent id; optional `resume` to continue a prior agent.
- **copilot** — pin agent id from `task`; await via completion notification (use `read_agent` if needed).
- **codex** — pin handle from `spawn_agent`; await each handle with `wait`; call `close_agent` when done.
- Before any downstream mechanical check (`check-dimension`, etc.), await **all** pinned handles for that batch.
