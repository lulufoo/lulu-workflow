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

Pass the same `--constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` on every `$GATE_CONTROL` / `$REGISTER_*` invocation. `--domain-constraints-file` and `--session-dir` are only for `$DEC_START` (Main bootstrap). Working／reopen entry uses `$APPROACH_SHELL enter-node`／`reopen-node` (no `$DEC_SET_ACTIVE`).

> If `$DEC_START` exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.

### Working node entry (Skill-visible)

Public Working entry is `$APPROACH_SHELL enter-node` (not `set-focus`). It mechanically binds shell focus, Active Session, and a per-binding `context_docs` snapshot.

```bash
$APPROACH_SHELL enter-node --node-id "<Dx>" \
  --project-root "$(pwd)" --cycle-id "<cycle_id>" \
  --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"
```

When `enter-node` succeeds, stdout may list required next macros. **Always** complete:

1. `$GATE_CONTROL resolve-context` — pin new `$CTX` (mandatory; do not reuse prior `$CTX`).
2. Load each path in stdout/`context_docs` read-only and place them at the front of attention (do **not** load prior Dx docs).
3. Declare to the user: session switched to that node; prior session conclusions do not carry over.
4. `$APPROACH_SHELL bind-check-frozen --node-id Dx` — if `realign_required=true`, keep Frozen; run **semantic Realign** (dialogue vs loaded `context_docs` + this slice; do **not** default into RS). Then `$APPROACH_SHELL clear-frozen --node-id Dx`. If `realign_required=false`, continue.
5. Only then continue DDF / `$REGISTER_*` on Active (no `--session-dir` on those macros) — except **reopen target** path below.

After `$APPROACH_SHELL enter-working`, immediately run `enter-node` for the focused Dx (stdout next_steps only require that macro); then complete the semantic entry steps above from `enter-node` stdout.

**Reopen a delivered / in-progress Dx** (global prepare → permit → `$DEC_REOPEN`):

1. `$APPROACH_SHELL reopen-node --node-id Dx --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"`. Freezes shell for Dx + DAG successors; freezes **successor sessions only**; binds focus+Active to Dx; issues a one-shot permit.
2. Complete semantic entry steps 1–3 above from reopen stdout (`context_docs`).
3. `$DEC_REOPEN --permit "<permit_path>"` with the same `--constraints` (required under `reopen_authorization=holder_required`). This freezes the **target** session only.
4. Stay session Frozen; run RS → `$RS_COMMIT` (P1.5). Then `$APPROACH_SHELL complete-reopen --binding-id "<binding_id>" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"`.
5. Successors stay Frozen until each is entered via `enter-node` and Realign + `clear-frozen` complete.

**Same-Active restore** (new window, Active unchanged): `$APPROACH_SHELL enter-node --node-id <current>` (idempotent rebind) → `resolve-context` → load `context_docs` → `bind-check-frozen` (and Realign/`clear-frozen` if required) → continue.

**Do not** use `$APPROACH_SHELL set-focus` (retired; hard-fails).  
**Do not** treat shell focus change alone as a completed session switch.  
**Do not** invent a decision-only Active switch macro. Successor Realign uses `clear-frozen`; reopen target shell clear uses `complete-reopen` only.

## Outer delivery (PackageReady → seal)

Local session Delivered ≠ cycle / stage delivery.

After Active `$GATE_CONTROL deliver` succeeds on `main/` or `Dx/`:

1. Tell the user only **this node session** is Delivered (not approach export).
2. Do **not** treat cycle `delivered-refs` as the approach handoff (nested `deliver` does not register it).
3. If Working and other ready nodes remain → `$APPROACH_SHELL enter-node` then `resolve-context` / load docs (see Working node entry).
4. When all nodes are Delivered → `$APPROACH_SHELL enter-package-ready`.
5. After explicit human confirm → `$APPROACH_SHELL confirm-seal --confirm --cycle-id "<cycle_id>" --project-root "$(pwd)"`.
6. Only after `confirm-seal` succeeds may you claim approach stage delivery (`path` = `decision-package.json`, `artifact=decision-package`).
