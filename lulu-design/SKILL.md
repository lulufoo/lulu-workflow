---
name: lulu-design
description: >-
  Use when: 技术方案设计, tech design stage, design-doc,
  lulu-dev-workflow lulu-design, design delivered, 设计文档.
disable-model-invocation: true
---

# lulu-design

Domain holder for the design-doc compose document. Delegates full Drafting / Evaluating / Delivery orchestration to the `compose` kernel.

> **Prerequisite:** Delivered `decision-doc` from `lulu-approach`. Produces **design-doc.md** — technical solution design for human sign-off before `lulu-plan`.

**Scope:** Feature cycle only.

<HARD-GATE name="Runtime bootstrap">
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-design` (before Session Foundation)
- Feature identification logic from `## Session Foundation`

</HARD-GATE>

<HARD-GATE name="Compose engine">
Do NOT proceed until you have read `{SKILL_ROOT}/compose/SKILL.md` in full.
</HARD-GATE>

## start

Identify active cycle per `_runtime.md` § Session Foundation, then run `$START_COMPOSE` (`compose/SKILL.md` § start) with:

```bash
--profile-path "$SKILL_DIR/compose-profile.json"
```

Run mode is inferred at start: `product` when cycle `delivered-refs.json` contains a valid `lulu-spec` entry; otherwise `tech`. Do not pass `--run-mode`.

To resume an in-progress document, do not run start again — run `$SESSION_INFO --view session`.

---

## Reference documents

Template SSOT: [design templates on GitHub](https://github.com/lulufoo/lulu-workflow-framework/tree/main/lulu-dev-workflow/template/design)
