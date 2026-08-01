---
name: lulu-arch
description: >-
  Topic-cycle technical architecture shaping stage. Use when cycle_type is topic and
  lulu-approach is Delivered.
disable-model-invocation: true
---

# lulu-arch

Domain holder for the arch-doc compose document. Delegates full Drafting / Evaluating / Delivery orchestration to the `compose` kernel.

> **Prerequisite:** Delivered `decision-package` from `lulu-approach`, projected to this revision's `scope-package`. Produces **arch-doc.md** — topic-level technical architecture for human sign-off before opening a feature cycle.

**Scope:** Topic cycles only. Feature technical planning uses `lulu-plan` / `lulu-design`.

<HARD-GATE name="Runtime bootstrap">
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-arch`

</HARD-GATE>

<HARD-GATE name="Compose engine">
Do NOT proceed until you have read `{SKILL_ROOT}/compose/SKILL.md` in full.
All Drafting / Evaluating / Delivery rules, gates, and macros defined there apply to this session, with `<profile_id>` = `lulu-arch`.
</HARD-GATE>

## start

Identify active cycle per `_runtime.md` § Session Foundation, then run `$START_COMPOSE` (`compose/SKILL.md` § start) with:

```bash
--profile lulu-arch \
--profile-path "$SKILL_DIR/compose-profile.json"
```

Run mode is always `tech` for topic architecture shaping. Do not pass `--run-mode`.

To resume an in-progress document, do not run start again — run `$SESSION_INFO --view session`.

---

## Reference documents

Template SSOT: [arch templates on GitHub](https://github.com/lulufoo/lulu-workflow-framework/tree/main/lulu-dev-workflow/template/arch) (`skill-config` → `tat_*_url`)
