# Changelog

## [Unreleased]

### code stage — state machine + git delivery (2026-05-27)

- **Added** dual state machine in `code/transition-whitelist.json` — session (`Preparing→Executing→Closing→Delivered`) + task (TDD six phases).
- **Added** `code/templates/code-log.template.md` — append-only action model (`enter`, `test_run`, `git_commit`).
- **Changed** `code/SKILL.md` — full rewrite: L1 worktree, L3 per-task commit, L4′ closing gate; SSOT whitelist; no runtime hook.
- **Changed** `code/scripts/start.py` — bootstraps `current_state: Preparing` (Path B); no git in start.py.
- **Changed** `code/scripts/init.py` — reads `config["code"]` (not `tdd`); documents `code.git`.
- **Changed** `product/templates/workflow-config.template.json` — `code.git` block (`worktree_base`, `branch_pattern`, etc.).
- **Changed** `scripts/install.py` — deploys `CODE_TEMPLATES` (`code-log.template.md`).
- **Removed** (prior) `code/scripts/hook_guard.py` — code not in unified `_STAGES`.
- **Install** — `python3 scripts/install.py --platform cursor --repo lulufoo/lulu-dev-skills --ref main`
