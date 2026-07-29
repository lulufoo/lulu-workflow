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
| `$RESOLVE_CONTEXT` | `python3 "$SKILL_DIR/scripts/resolve_context.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` |
| `$APPROACH_SHELL` | `python3 "$SKILL_DIR/scripts/approach_shell_control.py" --approach-root "$CACHE_DIR/<cycle_id>/lulu-approach"` |
| `$APPROACH_SPLIT` | `python3 "$SKILL_DIR/scripts/approach_split_control.py" --approach-root "$CACHE_DIR/<cycle_id>/lulu-approach"` |

Subcommand contract: module docstring / `--help`.

## start

Complete `_runtime.md` § Session Foundation before running decision start.

**Step 1: Run `$RESOLVE_CONTEXT`.** `sources[]` fully auto-derived from `(cycle_id, stage)` (upstream via the transition graph, topic doc via `topic_id`), each with `status` / `resolved_doc_path` already filled in. This holder resolves its own context, `decision` never does. It writes `{"context": {...}}` to a file and prints *that file's path* to stdout (never JSON content on the command line) — capture stdout as `$RESOLVED_CONTEXT_PATH`. Non-zero exit → stop and report stderr.

**Step 2: Init outer shell.** Run `$APPROACH_SHELL init-shell`. Creates the approach outer root and `main/` session directory under cache. Approach root = `$CACHE_DIR/<cycle_id>/lulu-approach`; Main DDF session dir = `$CACHE_DIR/<cycle_id>/lulu-approach/main`.

**Step 3: Run `$DEC_START`** from `decision/SKILL.md` § Start with:

```bash
--stage lulu-approach \
--constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json" \
--domain-constraints-file "$RESOLVED_CONTEXT_PATH" \
--session-dir "$CACHE_DIR/<cycle_id>/lulu-approach/main"
```

Pass the same `--constraints "$SKILL_DIR/constraints-$CYCLE_TYPE.json"` on every `$GATE_CONTROL` / `$REGISTER_*` invocation. `--domain-constraints-file` and `--session-dir` are only for `$DEC_START` / `$DEC_SET_ACTIVE` (see `decision/SKILL.md` § Active Session). After start, run `$GATE_CONTROL resolve-context` and declare the active session before gate dialogue.

> If `$DEC_START` exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.

### Working focus switch (Skill-visible)

When `$APPROACH_SHELL enter-working` / `set-focus` succeeds, stdout may list required next macros. **Always** complete:

1. If the Dx session is new: `$DEC_START --session-dir …/Dx` (sets Active).
2. Else: `$DEC_SET_ACTIVE --session-dir …/Dx`.
3. `$GATE_CONTROL resolve-context` — pin new `$CTX` (mandatory; do not reuse prior `$CTX`).
4. Declare to the user: session switched to that node; prior session conclusions do not carry over.
5. Only then continue DDF / `$REGISTER_*` on Active (no `--session-dir` on those macros).

**Do not** treat shell focus change alone as a completed session switch.

## Outer delivery (PackageReady → seal)

Local session Delivered ≠ cycle / stage delivery.

After Active `$GATE_CONTROL deliver` succeeds on `main/` or `Dx/`:

1. Tell the user only **this node session** is Delivered (not approach export).
2. Do **not** treat cycle `delivered-refs` as the approach handoff (nested `deliver` does not register it).
3. If Working and other ready nodes remain → `$APPROACH_SHELL set-focus` then `$DEC_START` / `$DEC_SET_ACTIVE` + `resolve-context` (see Working focus switch).
4. When all nodes are Delivered → `$APPROACH_SHELL enter-package-ready`.
5. After explicit human confirm → `$APPROACH_SHELL confirm-seal --confirm --cycle-id "<cycle_id>" --project-root "$(pwd)"`.
6. Only after `confirm-seal` succeeds may you claim approach stage delivery (`path` = `decision-package.json`, `artifact=decision-package`).
