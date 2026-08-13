---
name: lulu-plan
description: >-
  Use when: 技术方案, 技术设计, tech design, tech-doc, 技术文档, 架构设计,
  技术规格, 技术实现方案, tech-doc workflow, 技术文档流程, 技术文档状态迁移,
  lulu-dev-workflow lulu-plan, E2 E3 E4 评估, tech review, tech delivered.
disable-model-invocation: true
---

# lulu-plan

Domain holder for the tech-doc compose document. Delegates full Drafting / Evaluating / Delivery orchestration to the `compose` kernel.

> **Prerequisite:** Delivered `lulu-design` or `lulu-approach` (`decision-package`, tech mode) / `lulu-spec` (product mode). Produces **tech-doc.md**.

**Scope:** Feature cycle only.

<HARD-GATE name="Runtime bootstrap">
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-plan` (before Session Foundation)
- Feature identification logic from `## Session Foundation`

</HARD-GATE>

<HARD-GATE name="Compose engine">
Do NOT proceed until you have read `{SKILL_ROOT}/compose/SKILL.md` in full.

</HARD-GATE>

## Script Macros

| Macro | Command |
|---|---|
| `$PLAN_PROFILE` | `python3 "$SKILL_DIR/scripts/start/tech_plan_profile_control.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |

## start

Identify active cycle per `_runtime.md` § Session Foundation. Run `$PLAN_PROFILE`; stdout is the runtime profile path. Then run `$START_COMPOSE` (`compose/SKILL.md` § start) with:

```bash
--profile-path "<$PLAN_PROFILE stdout>" \
[--carry-forward-ref "<absolute-path-to-previous-tech-doc.md>"]
```

Run mode is inferred at start: `product` when cycle `delivered-refs.json` contains a valid `lulu-spec` entry; otherwise `tech`. Do not pass `--run-mode`. `--carry-forward-ref`: re-entry only (new iteration; never continue in the old directory).

To resume an in-progress document, do not run start again — run `$SESSION_INFO --view session`.
