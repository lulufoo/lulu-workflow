# Changelog

## [Unreleased]

### code stage (2026-05-27)

- **Added** `code/templates/code-log.template.md` — optional append-only event log template.
- **Changed** `code/SKILL.md` — **Three-file model retained:** `code-log.md` (phase summary) + `red-run.md` + `green-run.md` (full Red/Green detail). Do not replace green-run/red-run with one-line code-log entries.
- **Added** Implementation note — `code` not in `_STAGES`; legacy `code/scripts/hook_guard.py` not dispatched (do not document as "hook enforced").
- **Unchanged** — `code` is **not** added to unified `scripts/hook_guard._STAGES`.
- **Install** — Run `install.py` to sync `~/.cursor/skills/lulu-dev-workflow`.
