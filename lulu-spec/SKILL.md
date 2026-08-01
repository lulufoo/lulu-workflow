---
name: lulu-spec
description: >-
  Use when: 产品规格, feature PRD, product spec, product-doc,
  lulu-dev-workflow lulu-spec, product delivered, 产品文档.
disable-model-invocation: true
---

# lulu-spec

Domain holder for the product-doc compose document. Delegates full Drafting / Evaluating / Delivery orchestration to the `compose` kernel.

> **Prerequisite:** Committed `source-package` from `lulu-bet`, projected to this revision's `scope-package`. Produces **product-doc.md** — feature product specification for human sign-off before `lulu-approach`.

**Scope:** Feature cycle only. Topic/shaping cycles are out of scope (future `lulu-blueprint`).

<HARD-GATE name="Runtime bootstrap">
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-spec`

</HARD-GATE>

<HARD-GATE name="Compose engine">
Do NOT proceed until you have read `{SKILL_ROOT}/compose/SKILL.md` in full.
All Drafting / Evaluating / Delivery rules, gates, and macros defined there apply to this session, with `<profile_id>` = `lulu-spec`.
</HARD-GATE>

## start

Identify active cycle per `_runtime.md` § Session Foundation, then run `$START_COMPOSE` (`compose/SKILL.md` § start) with:

```bash
--profile lulu-spec \
--profile-path "$SKILL_DIR/compose-profile.json"
```

Requires `lulu-bet` in delivered-refs for this feature cycle. Run mode is always `product` (inferred). Do not pass `--run-mode`.

To resume an in-progress document, do not run start again — run `$SESSION_INFO --view session`.

---

## Reference documents

Template SSOT: [spec templates on GitHub](https://github.com/lulufoo/lulu-workflow-framework/tree/main/lulu-dev-workflow/template/spec)
