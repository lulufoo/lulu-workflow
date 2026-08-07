---
name: narrative-arc-runner
description: >-
  Compose narrative-arc tool skill. Formal Init arc (_narrative-arc.json) and
  collaboration display arc (caller-supplied path). Declared by initializing-
  runner (Formal) and optionally inductive G2/G3 (collab).
---

# narrative-arc-runner

Use when a compose caller **declares** this skill for Formal or collab
narrative arcs. Collab ≠ Formal file.

**Must:** Formal via `$NARRATIVE_ARC_CTL`; collab regenerate via
`$NARRATIVE_ARC_COLLAB_CTL` with caller `--output-path` + `--confirm`.  
**Must not:** write Formal from collab control; auto-regenerate without human confirm.

## Script Macros

| Macro | Command |
|-------|---------|
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_control.py"` |
| `$NARRATIVE_ARC_COLLAB_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_collab_control.py"` |

Formal: `--help` · `validate` · `write` · `show` · `list-chapters`.  
Collab: `--help` · `regenerate` · `validate` · `show`.

## DONE / failure

- **DONE (Formal write/validate):** exit 0; path under active slice `_narrative-arc.json`.
- **DONE (collab regenerate):** exit 0; backup + `fact_node_summary` when overwrite.
- **Failure:** non-zero (Formal path banned on collab; missing `--confirm` / `--output-path`).
