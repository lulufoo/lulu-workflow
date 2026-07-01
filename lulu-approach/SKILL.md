---
name: lulu-approach
---

# lulu-approach

Domain holder for tech-level diagnostic decisions. Delegates the full DDF execution to the `decision` kernel under tech domain constraints.

---

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

<HARD-GATE>
Do NOT proceed until you have read `../decision/SKILL.md` in full.
All DDF rules, gates, and registers defined there apply to this session.
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/lulu-approach`

Machine constraints SSOT: `$SKILL_DIR/constraints-$CYCLE_TYPE.json` (resolve `$CYCLE_TYPE` from `_runtime.md` § Session Foundation; passed to decision CLI via `--constraints`).

## start

Complete `_runtime.md` § Session Foundation before running decision start.

Execute `$DEC_START` from `decision/SKILL.md` § Start with:

```bash
--stage lulu-approach \
--constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"
```

Pass the same `--constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` on every `$GATE_CONTROL` / `$REGISTER_*` invocation.

> If `$DEC_START` exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.
