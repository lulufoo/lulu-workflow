---
name: lulu-blueprint
description: >-
  Topic-cycle product architecture shaping stage. Use when cycle_type is topic and
  lulu-bet is Delivered.
disable-model-invocation: true
---

# lulu-blueprint

Domain holder for the product-doc compose document. Delegates full Drafting / Evaluating / Delivery orchestration to the `compose` kernel.

> **Prerequisite:** Delivered `decision-doc` from `lulu-bet`. Produces **product-doc.md** — topic-level product architecture for human sign-off before opening a feature cycle.

**Scope:** Topic cycles only. Feature PRD cycles use `lulu-spec`.

<HARD-GATE name="Runtime bootstrap">
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-blueprint`

</HARD-GATE>

<HARD-GATE name="Compose engine">
Do NOT proceed until you have read `{SKILL_ROOT}/compose/SKILL.md` in full.
All Drafting / Evaluating / Delivery rules, gates, and macros defined there apply to this session, with `<profile_id>` = `lulu-blueprint`.
</HARD-GATE>

## start

Identify active cycle per `_runtime.md` § Session Foundation, then run `$START_COMPOSE` (`compose/SKILL.md` § start) with:

```bash
--profile lulu-blueprint \
--profile-path "$SKILL_DIR/compose-profile.json"
```

Run mode is always `product` for topic product architecture shaping. Do not pass `--run-mode`.

To resume an in-progress document, do not run start again — run `$SESSION_INFO --view session`.

---

## Reference documents

Template SSOT (staged locally): `lulu-blueprint/templates/` — sync target: [blueprint templates on GitHub](https://github.com/lulufoo/lulu-workflow-framework/tree/main/lulu-dev-workflow/template/blueprint)
