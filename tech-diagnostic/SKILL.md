---
name: tech-diagnostic
---

# tech-diagnostic

Domain holder for tech-level diagnostic decisions. Delegates the full DDF execution to the `diagnostic` kernel under tech domain constraints.

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

`$SKILL_DIR` = `$SKILL_ROOT/tech-diagnostic`

---

## Domain Constraints

Prose for the kernel `Domain Constraints HARD-GATE`. Machine constraints: holder defaults loaded at `$DX_START`; runtime via `$GATE_CONTROL resolve-context` → `domain_constraints`.

### Context Loading

Before gate **O** (while `active_gate` is `O`), check whether a Delivered product-doc exists for this feature:

```
$CACHE_DIR/<cycle_id>/product/plan/   (look for the latest revision with Delivered state)
```

If a Delivered product-doc is found, load it as read-only context and tell the user:
"I've loaded the product-doc as context for this tech diagnostic."

If not found, proceed without it.

### After DC

Tell user: "Tech diagnostic is complete. The next step is `/tech-design` (alias: `ds`). You may also go directly to `/tech-plan` (alias: `tp`)."

## start

Complete `_runtime.md` § Session Foundation before running diagnostic start.

Execute `$DX_START` from `diagnostic/SKILL.md` § Start, passing `tech-diagnostic` as `--stage`:

- Stage: `tech-diagnostic`
- Cache subdir: `tech/diagnostic`
- Apply holder prose from `## Domain Constraints` above throughout the session.
> If `$DX_START` exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.
