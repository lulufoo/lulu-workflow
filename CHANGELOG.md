# Changelog

## [Unreleased]

### code stage (2026-05-27)

- **Added** `code/templates/code-log.template.md` — optional append-only event log template.
- **Changed** `code/SKILL.md` — governance section: no runtime code hook; `transition-whitelist.json` normative only; Red/Green via `code-log` `test_run` events.
- **Removed** `code/scripts/hook_guard.py` and hook-only helpers from `code/scripts/workflow_common.py` (phantom enforcement; never dispatched).
- **Changed** `scripts/install.py` — code stage no longer installs `hook_guard.py`.
- **Breaking** — External integrations that imported `code.scripts.hook_guard` must migrate; reinstall skill after merge (`install.py`).
- **Unchanged** — `code` is **not** added to unified `scripts/hook_guard._STAGES`.
- **Install** — Run `install.py` to sync `~/.cursor/skills/lulu-dev-workflow`.
