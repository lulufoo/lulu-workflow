---
name: derive-runner
description: >-
  Compose deductive L1: Pd floor means + ceiling × KW ruler after fact-intake.
---

# derive-runner

Run Pd on intake-classified facts: edge-closure floor means and Intent ceiling
means under the published KW ruler. Finish when validate passes and every floor
hole / required lens is covered or pending.

## Boundaries

**Must:** bind Input; `$DERIVE_BUILD_CTL context` (requires `eval_status=done`);
`$DERIVE_CTL plan-edge` → floor / ceiling×KW (cascade in this run) →
`$DERIVE_CTL append` → `$FACTS_CTL validate`; `$DEDUCTIVE_CTL pending-add` for
gaps; load `references/pd-semantic-work.md` before semantic work.  
**Must not:** Fact Intake / cut / eval / disposition / confirm; Pending Confirm
human gate; disposition-patch / promote; `$FETCH_COMPOSE` or paste framework
templates; `$SOURCE_PATH` / re-read upstream prose; write chapter prose;
`origin.type=discovered`; invent to pad KW with no edge; reuse intake Confirm
patch.

## Input

```text
REVISION_DIR: <abs revision / focus-L; parent binds $DEDUCTIVE_OUT_DIR>
PROJECT_ROOT: <abs project root>
COMPOSE_PROFILE: <profile id>
CYCLE_ID: <cycle id>
```

## Script Macros

| Macro | Command |
|-------|---------|
| `$DERIVE_BUILD_CTL` | `python3 "$SKILL_ROOT/compose/deductive-runner/derive-runner/scripts/derive_build_control.py"` |
| `$DERIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/derive_control.py"` |
| `$DEDUCTIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/deductive/deductive_control.py" --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |

Build: `--help` · `context`.  
Derive / deductive / facts: see each `--help`. Scripts never invent derived
work-item text.

## Cognitive map

**Floor** = edge-closure **means** (no KW).  
**Ceiling** = Intent projection **means** driven by published **`KW_CRITERIA`** as
the **only thickness ruler**. Do **not** treat “edges closed” or “should-cover
ticked” as “thick enough.” Do **not** run a separate KW-first pass on the intake
pool.  
**Do not** batch-retag quarantine/not_needed inside Pd.

## Execution

1. Bind Input.  
2. `$DERIVE_BUILD_CTL context …` — bind `KW_CRITERIA` / registry from stdout
   (`--help` for fields).  
3. `$DERIVE_CTL plan-edge …` — mechanical edge floor + topo (`--help` for
   fields).  
4. Load `references/pd-semantic-work.md`; apply floor → ceiling×KW → cascade in
   this run; gaps → `$DEDUCTIVE_CTL pending-add`.  
5. Persist derived batches via `$DERIVE_CTL append` then `$FACTS_CTL validate`
   (`--help` for flags).

**Done:** validate exit 0; every floor hole covered or pending; every required
lens either KW-satisfied or has open `kw_shortfall` / other pending.

## Summary

```text
Derive complete.
  Facts: <path>
  Pending gaps: <n open>
  Status: ok
```
