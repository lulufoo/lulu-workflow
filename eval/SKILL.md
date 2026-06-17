---
name: eval-library
description: >
  Shared evaluation library for lulu-dev-workflow. Issue taxonomy, review table
  schema, and P1/P2 principles. Read by eval runners; not user-invoked.
meta-skill-version: 1.0.0
---

# eval/SKILL.md

Library SKILL — not a workflow stage. Runners Read this file; eval-rules never dispatches it.

**WO (tech-plan v2):** `tech-doc.md` — EvalCorpus v4; e3 uses `41-tech-plan-intent-evaluation-framework.md` (A, `tpt_intent_eval_framework_url`) + builtin `intent_gap_probes` procedure.

---

## P1 · Evaluation Evidence First

Any evaluation finding must be backed by citable evidence before a conclusion is drawn. No evidence = invalid finding.

If evidence cannot be located → label `UNRESOLVABLE` and surface via AskQuestion during SoT Remediation. Do not guess.

---

## P2 · SOT Auditability

Every issue must be classified: is the SoT defective, or did the work artifact fail to reflect a valid SoT?

- SOT defective → escalate (never fix silently)
- SOT valid, artifact wrong → Artifact Remediation
- SOT issues always require AskQuestion

P1 is a prerequisite for P2.

---

## Root cause taxonomy

SSOT: `{$SKILL_ROOT}/eval/issue-taxonomy.json`. `root_cause` must be one of four labels:

| Label | Fix mode | Remediation phase |
|-------|----------|-------------------|
| `WO-MISS` | auto | Artifact Remediation |
| `WO-ERROR` | auto | Artifact Remediation |
| `SOT-DEFECT` | interactive | SoT Remediation |
| `UNRESOLVABLE` | interactive | SoT Remediation |

---

## Review table contract

- Header SSOT: `{$SKILL_ROOT}/eval/review.template.md`
- Validate via: `python3 {$SKILL_ROOT}/eval/scripts/review_schema.py --schema`
- **tech-plan output path:** `{revision}/evaluate{M}/{review.output_path}` from EvalCorpus (e.g. `tech-review-e{M}1.md`)

Probe runners: Read template, substitute `{{DIM_LABEL}}`, `{{REV}}`, `{{M}}`, `{{DATE}}`, `{{REFS}}`; append issue rows; never alter header/separator row order.

---

## Per-issue required fields

All probe rows must fill columns per `review_schema.py` `required_at_probe`. Remediation runners read rows as fix SSOT.

| `root_cause` | `sot_ref` | `location` | `evidence` | `description` |
|--------------|-----------|------------|------------|-----------------|
| `SOT-DEFECT` | SoT passage ref (§ / file) | tech-doc gap location | Exact SoT quote + gap + why it blocks | One-line summary |
| `WO-MISS` | SoT passage stating requirement | tech-doc §/line missing/wrong | SoT quote + gap vs SoT | What tech-doc fails to reflect |
| `WO-ERROR` | `—` | tech-doc §/line | Criterion violated (dim framework ref) + excerpt | Self-quality violation |
| `UNRESOLVABLE` | search target or `—` | best-known tech-doc loc | What was searched; why no evidence | Why classification pending |

Probe row defaults: `status: pending`, `decision: —`

Example (WO-MISS):

```markdown
| e1-2 | WO-MISS | product-doc §3.2 | tech-doc §2 Approach | medium | SoT: "must support offline sync" — tech-doc §2 omits sync | Offline sync not designed | pending | — |
```

---

## Remediation row usage

- **Artifact Remediation:** `WO-MISS` / `WO-ERROR` — use `location` + `description` + `evidence` to fix `tech-doc.md`
- **SoT Remediation:** `SOT-DEFECT` / `UNRESOLVABLE` — AskQuestion from row fields; Reclassify → `WO-*` applies Artifact fix inline in same session

---

## Mechanical command

`$EVAL_CONTROL` — eval-domain state machine. Pass parent workflow id via `--workflow`.

```bash
python3 {$SKILL_ROOT}/eval/scripts/eval_control.py \
  --workflow <workflow> \
  --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand> [args...]
```

**tech-plan:** `--workflow tech-plan`

| Concern | SSOT |
|---------|------|
| Step order, stdout handling, branching | `{$SKILL_ROOT}/eval/eval-rules.md` |
| Subcommand list | `eval/scripts/eval_control.py` module docstring or `--help` |
| Runner write boundaries | `eval/*-runner/SKILL.md` |

Do not infer `$EVAL_CONTROL` contracts from workflow parent SKILL Script Macros sections.
