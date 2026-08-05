---
name: lulu-bet
---

# lulu-bet

Domain holder for product-level diagnostic decisions. Delegates the full DDF execution to the `decision` kernel under product domain constraints.

---

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-bet` (before Session Foundation)
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

<HARD-GATE>
Do NOT proceed until you have read `../decision/SKILL.md` in full.
All DDF rules, gates, and registers defined there apply to this session.
</HARD-GATE>

Machine constraints SSOT: `$SKILL_DIR/constraints-$CYCLE_TYPE.json` (resolve `$CYCLE_TYPE` from `_runtime.md` § Session Foundation; passed to decision CLI via `--constraints`).

## Script Macros

| Macro | Command |
|-------|---------|
| `$RESOLVE_CONTEXT` | `python3 "$SKILL_DIR/scripts/resolve_context.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` |
| `$BET_DELIVER` | `python3 "$SKILL_DIR/scripts/decision_package_control.py" --holder-root "$CACHE_DIR/<cycle_id>/lulu-bet" --cycle-id "<cycle_id>" --project-root "$(pwd)"` |

Subcommand contract: module docstring / `--help`.

## start

Complete `_runtime.md` § Session Foundation before running decision start.

**Step 1: Run `$RESOLVE_CONTEXT`.** Holder builds flat `context.docs` map (key→path); missing docs omit keys. Writes to a file and prints that path — capture as `$RESOLVED_CONTEXT_PATH`. Non-zero exit → stop and report stderr.

**Step 2: Run `$DEC_START`** from `decision/SKILL.md` § Start with:

```bash
--stage lulu-bet \
--constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json" \
--domain-constraints-file "$RESOLVED_CONTEXT_PATH"
```

Pass the same `--constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` on every `$GATE_CONTROL` / `$REGISTER_*` invocation. `--domain-constraints-file` is only needed on `$DEC_START`.

> If `$DEC_START` exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.

## Deliver

After DDF reaches DC completion, run `$GATE_CONTROL prepare`, then
`$BET_DELIVER`. The holder control commits `decision-package` and its delivered
reference; only then is lulu-bet Delivered.
