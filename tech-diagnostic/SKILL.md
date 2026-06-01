---
name: tech-diagnostic
---

# tech-diagnostic

Domain holder for tech-level diagnostic decisions. Loads the `diagnostic` kernel with tech domain constraints.

---

<HARD-GATE>
Do NOT proceed until you have read `../SKILL.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Feature Context`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/tech-diagnostic`

---

## Domain Constraints

These constraints override the kernel defaults for this domain. The `diagnostic/SKILL.md` kernel
**must** read and apply these constraints before executing any DDF gate.

### X Gate

Execute **all five** dimensions (in order):

1. Acceptance Criteria
2. Impact Surface
3. External Dependencies
4. Implementation Cost
5. Expected Outcome

No dimensions are skipped.

### Decision-Doc

Write **all sections** as defined in the kernel template. No sections are omitted.

### Context Loading

Before starting the DDF (before Open Channel / Q), check whether a Delivered `product-doc` exists
for this feature:

```
$CACHE_DIR/<feature_id>/product/plan/   (look for the latest revision with Delivered state)
```

If a Delivered product-doc is found, load it as **read-only context** and note to the user:
"I've loaded the product-doc as context for this tech diagnostic."

If not found, proceed without it (do not block or error).

### After DC

Tell user: "Tech diagnostic is complete. The next step is `/tech-plan` (alias: `tp`)."

---

## How to Run

Load `diagnostic/SKILL.md` and run the full DDF under the above constraints.

When invoking `start.py`, pass `--stage tech-diagnostic`:

```bash
python3 "$SKILL_ROOT/diagnostic/scripts/start.py" \
  --project-root "$(pwd)" \
  --feature-id "<feature_id>" \
  --stage tech-diagnostic
```

Session artifacts write to:
```
$CACHE_DIR/<feature_id>/tech/diagnostic/
```
