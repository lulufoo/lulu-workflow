---
name: product-diagnostic
---

# product-diagnostic

Domain holder for product-level diagnostic decisions. Loads the `diagnostic` kernel with product domain constraints.

---

<HARD-GATE>
Do NOT proceed until you have read `../SKILL.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Feature Context`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/product-diagnostic`

---

## Domain Constraints

These constraints override the kernel defaults for this domain. The `diagnostic/SKILL.md` kernel
**must** read and apply these constraints before executing any DDF gate.

### X Gate

Execute **only** the following dimensions (in order):

1. Acceptance Criteria
2. Impact Surface
3. Expected Outcome

Do **NOT** execute: External Dependencies, Implementation Cost.

### Decision-Doc

Omit the following sections from the written decision-doc:

- External Dependencies
- Implementation Cost

All other sections are required as defined in the kernel template.

### After DC

Tell user: "Product diagnostic is complete. The next step is `/product-plan` (alias: `pp`)."

---

## How to Run

Load `diagnostic/SKILL.md` and run the full DDF under the above constraints.

When invoking `start.py`, pass `--stage product-diagnostic`:

```bash
python3 "$SKILL_ROOT/diagnostic/scripts/start.py" \
  --project-root "$(pwd)" \
  --feature-id "<feature_id>" \
  --stage product-diagnostic
```

Session artifacts write to:
```
$CACHE_DIR/<feature_id>/product/diagnostic/
```
