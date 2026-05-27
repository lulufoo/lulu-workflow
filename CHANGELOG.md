# Changelog

## [Unreleased]

### code-log v4 (2026-05-27)

- **Added** `code/templates/code-log.template.md` — append-only per-task execution log template.
- **Changed** `code/SKILL.md` — `code-log.md` is the sole per-task execution archive; Red/Green evidence is recorded as `test_run` events (full output). New sessions must **not** create `red-run.md` or `green-run.md`.
- **Unchanged** — `code` is **not** added to unified `scripts/hook_guard._STAGES`; `code/scripts/hook_guard.py` behavior is not enabled in this release.
- **Install** — After merge, run the repo `install.py` (or your platform sync) to update `~/.cursor/skills/lulu-dev-workflow` (or Copilot equivalent).
- **Verify** — Start a new `/code` session on a feature with Delivered work-order; confirm `tasks/t1/` only grows `code-log.md`.
