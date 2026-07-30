---
name: lulu-approach
---

# lulu-approach

Domain holder for tech-level diagnostic decisions. Delegates the full DDF execution to the `decision` kernel under tech domain constraints.

Outer flow spine: Main DDF in `main/` → optional Split → Working → PackageReady → `$APPROACH_SHELL confirm-seal`.

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

## Script Macros

| Macro | Command |
|-------|---------|
| `$RESOLVE_CONTEXT` | `python3 "$SKILL_DIR/scripts/resolve_context.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json" [--session-dir "<main_or_Dx>"]` |
| `$APPROACH_SHELL` | `python3 "$SKILL_DIR/scripts/approach_shell_control.py" --approach-root "$CACHE_DIR/<cycle_id>/lulu-approach"` |
| `$APPROACH_SPLIT` | `python3 "$SKILL_DIR/scripts/approach_split_control.py" --approach-root "$CACHE_DIR/<cycle_id>/lulu-approach"` |

Subcommand contract: module docstring / `--help`.

## start

Complete `_runtime.md` § Session Foundation before running decision start.

**Step 1: Run `$RESOLVE_CONTEXT`** (optionally `--session-dir` for `main/` or `Dx/`). Holder builds flat `context.docs` map (key→path); missing docs omit keys. Dx requires `main/decision-doc.md` or exits non-zero. Writes `{"context":{"docs":{…}}}` to a file and prints that path — capture as `$RESOLVED_CONTEXT_PATH`. Non-zero exit → stop and report stderr.

**Step 2: Init outer shell.** Run `$APPROACH_SHELL init-shell`. Creates the approach outer root and `main/` session directory under cache. Approach root = `$CACHE_DIR/<cycle_id>/lulu-approach`; Main DDF session dir = `$CACHE_DIR/<cycle_id>/lulu-approach/main`.

**Step 3: Run `$DEC_START`** from `decision/SKILL.md` § Start with:

```bash
--stage lulu-approach \
--constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json" \
--domain-constraints-file "$RESOLVED_CONTEXT_PATH" \
--session-dir "$CACHE_DIR/<cycle_id>/lulu-approach/main"
```

On success, stdout JSON includes `context_docs`. Then:

1. `$GATE_CONTROL resolve-context` — pin `$CTX` only (does **not** load docs)
2. For each key in `context_docs`: read-only load the path; tell the user what kind it is (`product_spec` / `tech_arch` / …)
3. Declare the active session before gate dialogue

Pass the same `--constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` on every `$GATE_CONTROL` / `$REGISTER_*` invocation. `--domain-constraints-file` and `--session-dir` are only for `$DEC_START` / `$DEC_SET_ACTIVE`.

> If `$DEC_START` exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.

### Working focus switch (Skill-visible)

When `$APPROACH_SHELL enter-working` / `set-focus` / `reopen-node` succeeds, stdout may list required next macros. **Always** complete:

1. `$RESOLVE_CONTEXT --session-dir …/Dx` — re-resolve map for that node (Dx hard-fails without main decision doc). Capture new `$RESOLVED_CONTEXT_PATH`.
2. If the Dx session is new: `$DEC_START --session-dir …/Dx --domain-constraints-file "$RESOLVED_CONTEXT_PATH"`.
3. Else: `$DEC_SET_ACTIVE --session-dir …/Dx --domain-constraints-file "$RESOLVED_CONTEXT_PATH"`.
4. `$GATE_CONTROL resolve-context` — pin new `$CTX` (mandatory; do not reuse prior `$CTX`).
5. Load each path in stdout/`context_docs` read-only and place them at the front of attention (do **not** load prior Dx docs).
6. Declare to the user: session switched to that node; prior session conclusions do not carry over.
7. `$APPROACH_SHELL bind-check-frozen --node-id Dx` — if `realign_required=true`, keep Frozen; run **semantic Realign** (dialogue vs loaded `context_docs` + this slice; do **not** default into RS). Then `$APPROACH_SHELL clear-frozen --node-id Dx`. If `realign_required=false`, continue.
8. Only then continue DDF / `$REGISTER_*` on Active (no `--session-dir` on those macros) — except **reopen target** path below.

**Reopen a delivered / in-progress Dx** (cascade-freeze successors):

1. `$APPROACH_SHELL reopen-node --node-id Dx` (or `freeze-cascade` then force focus). Cascade-freezes Dx + DAG successors; force-sets focus even when current focus is not Delivered.
2. Complete bind steps 1–6 above.
3. **Do not** `clear-frozen` before RS finishes. Stay session Frozen; run RS → `$RS_COMMIT` (P1.5). Then `$APPROACH_SHELL clear-frozen --node-id Dx` to clear the shell flag.
4. Successors stay Frozen until each is entered (steps 1–7) and Realign + `clear-frozen` complete.

**Same-Active restore** (new window, Active unchanged): re-run `$RESOLVE_CONTEXT --session-dir <current>` then `$DEC_SET_ACTIVE --session-dir <current> --domain-constraints-file …` → `resolve-context` → load `context_docs` once → `bind-check-frozen` (and Realign/`clear-frozen` if required) → continue.

**Do not** treat shell focus change alone as a completed session switch.  
**Do not** unfreeze inside `$DEC_SET_ACTIVE`. Frozen clear is approach-shell only (`clear-frozen` or reopen RS then `clear-frozen`).

## Outer delivery (PackageReady → seal)

Local session Delivered ≠ cycle / stage delivery.

After Active `$GATE_CONTROL deliver` succeeds on `main/` or `Dx/`:

1. Tell the user only **this node session** is Delivered (not approach export).
2. Do **not** treat cycle `delivered-refs` as the approach handoff (nested `deliver` does not register it).
3. If Working and other ready nodes remain → `$APPROACH_SHELL set-focus` then `$DEC_START` / `$DEC_SET_ACTIVE` + `resolve-context` (see Working focus switch).
4. When all nodes are Delivered → `$APPROACH_SHELL enter-package-ready`.
5. After explicit human confirm → `$APPROACH_SHELL confirm-seal --confirm --cycle-id "<cycle_id>" --project-root "$(pwd)"`.
6. Only after `confirm-seal` succeeds may you claim approach stage delivery (`path` = `decision-package.json`, `artifact=decision-package`).
