---
name: fact-intake-eval
description: >-
  Compose fact-intake L1: E1∩E2 doc→facts fidelity eval with return_to_caller.
---

# fact-intake-eval

Run shared Eval (E1∩E2) on focus-slice `_facts.json` against `$SOURCE_PATH`.
Remediate by editing `_facts.json` only; do not re-enter Cut.

**Must:** full Eval round via `$EVAL_CONTROL` after pinning `$EVAL_ADAPTER_CONFIG`;
`completion_mode=return_to_caller`; stop at `eval_status=done`.  
**Must not:** delivery Evaluating / Accept L; write disposition; edit SoT doc;
kick back to `fact-cut-runner`.

## Input

```text
REVISION_DIR: <abs revision root>
PROJECT_ROOT: <abs project root>
CYCLE_ID: <cycle id>
SOURCE_PATH: <abs intake SoT>
```

## Cognition

Eval terms carry the meanings defined in these units.

| Term | Unit |
|---|---|
| fact, one unit per `F-n`, weakening | `../../references/cognition/fact.md` |
| `derivation.disposition`, `upstream_ref`, source span | `../../references/cognition/producer/provenance.md` |

E1 asks whether every doc obligation reached one disposition without
weakening; E2 asks whether every fact can be traced back to a doc span.
Neither asks whether the doc is right.

## Script Macros

| Macro | Command |
|-------|---------|
| `$FACT_INTAKE_EVAL_CTL` | `python3 "$SKILL_ROOT/compose/fact-intake-runner/fact-intake-eval/scripts/fact_intake_eval_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)"` |

## Execution

1. Bind Input.  
2. Run `$FACT_INTAKE_EVAL_CTL`. Pin `adapter_config_file` as `$EVAL_ADAPTER_CONFIG`.  
3. Load `$SKILL_ROOT/eval/SKILL.md` and follow it.  
4. Corpus: this package `dimension-defs/` (`e1-doc-coverage`, `e2-fact-provenance`).  
5. SoT = `$SOURCE_PATH`; remediation target = `_facts.json`.  
6. State under `{slice}/fact-intake-eval/`. Max 3 rounds; hard-block when exhausted.

**Done:** `eval_status=done` → return to `fact-intake-runner`.

## Summary

```text
Fact-intake-eval complete.
  Eval status: done
  State: <slice>/fact-intake-eval/
  Status: ok
```
