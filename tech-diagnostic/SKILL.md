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

Before gate **O** (while `active_gate` is `O`), read `$CYCLE_TYPE` and check for a Delivered upstream product document on this cycle:

| `$CYCLE_TYPE` | Cache path | Document |
|---------------|------------|----------|
| `feature` | `$CACHE_DIR/<cycle_id>/product/spec/` | Latest Delivered revision → `product-doc.md` |
| `topic` | `$CACHE_DIR/<cycle_id>/product/arch/` | Latest Delivered revision → `arch-doc.md` |

If a Delivered document is found, load it as read-only context and tell the user:
"I've loaded the product context document for this tech diagnostic."

If not found, proceed without it.

### After DC

Read `$CYCLE_TYPE` from `_runtime.md` § Session Foundation.

- **feature:** Tell user: "Tech diagnostic is complete. The next step is `/tech-design` (alias: `ds`) or `/tech-plan` (alias: `t`)."
- **topic:** Tell user: "Tech diagnostic is complete. The next step is `/tech-arch` (alias: `ta`)."

If `$CYCLE_TYPE` is unset, read `_transitions.md`, list allowed next stages for `tech-diagnostic` under the matching `cycle_type` key, and wait for explicit user selection.

## start

Complete `_runtime.md` § Session Foundation before running diagnostic start.

Execute `$DX_START` from `diagnostic/SKILL.md` § Start, passing `tech-diagnostic` as `--stage`:

- Stage: `tech-diagnostic`
- Cache subdir: `tech/diagnostic`
- Apply holder prose from `## Domain Constraints` above throughout the session.
> If `$DX_START` exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.
