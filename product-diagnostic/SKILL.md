---
name: product-diagnostic
---

# product-diagnostic

Domain holder for product-level diagnostic decisions. Delegates the full DDF execution to the `diagnostic` kernel under product domain constraints.

---

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

<HARD-GATE>
Do NOT proceed until you have read `../diagnostic/SKILL.md` in full.
All DDF rules, gates, and registers defined there apply to this session.
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/product-diagnostic`

---

## Domain Constraints

Prose for the kernel `Domain Constraints HARD-GATE`. Machine constraints: holder defaults loaded at `$DX_START`; runtime via `$GATE_CONTROL resolve-context` → `domain_constraints`.

### After DC

Tell user: "Product diagnostic is complete. The next step is `/product-plan` (alias: `pp`)."

## start

Complete `_runtime.md` § Session Foundation before running diagnostic start.

Execute `$DX_START` from `diagnostic/SKILL.md` § Start, passing `product-diagnostic` as `--stage`:

- Stage: `product-diagnostic`
- Cache subdir: `product/diagnostic`
- Apply holder prose from `## Domain Constraints` above throughout the session.
> If `$DX_START` exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.
