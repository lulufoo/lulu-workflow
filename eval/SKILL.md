---
name: eval-library
description: >
  Shared evaluation library for lulu-dev-workflow. Issue taxonomy, review table
  schema, and P1/P2 principles. Read by eval runners; not user-invoked.
meta-skill-version: 1.0.0
---

# eval/SKILL.md

Library SKILL — not a workflow stage. Runners Read this file; eval-rules never dispatches it.

Eval dimensions, SoT URLs, and quality frameworks are declared per workflow profile in `dimension-defs/` and resolved by the active `WorkflowAdapter` — not hardcoded here.

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
- Review output path: `{revision}/{L}/evaluate{M}/{review.output_path}` from EvalCorpus (e.g. `tech-review-e{M}1.md`). Absolute paths come from Compose EvalHandoff (`evaluate_dir` / staging); legacy revision-root sessions may still use `{revision}/evaluate{M}/` until that session ends.

Probe runners: Read template, substitute `{{DIM_LABEL}}`, `{{REV}}`, `{{M}}`, `{{DATE}}`, `{{REFS}}`; append issue rows; never alter header/separator row order.

---

## Per-issue required fields

All probe rows must fill columns per `review_schema.py` `required_at_probe`. Remediation runners read rows as fix SSOT.

| `root_cause` | `sot_ref` | `location` | `evidence` | `description` |
|--------------|-----------|------------|------------|-----------------|
| `SOT-DEFECT` | SoT passage ref (§ / file) | eval-target gap location | Exact SoT quote + gap + why it blocks | One-line summary |
| `WO-MISS` | SoT passage stating requirement | eval-target §/line missing/wrong | SoT quote + gap vs SoT | What eval-target fails to reflect |
| `WO-ERROR` | `—` | eval-target §/line | Criterion violated (dim framework ref) + excerpt | Self-quality violation |
| `UNRESOLVABLE` | search target or `—` | best-known eval-target loc | What was searched; why no evidence | Why classification pending |

Probe row defaults: `status: pending`, `decision: —`

Example (WO-MISS):

```markdown
| e1-2 | WO-MISS | product-doc §3.2 | tech-doc §2 Approach | medium | SoT: "must support offline sync" — tech-doc §2 omits sync | Offline sync not designed | pending | — |
```

---

## Remediation row usage

- **Artifact Remediation:** `WO-MISS` / `WO-ERROR` — use `location` + `description` + `evidence` to fix `REMEDIATION_TARGET_PATH`
- **SoT Remediation:** `SOT-DEFECT` / `UNRESOLVABLE` — AskQuestion from row fields; Reclassify → `WO-*` applies Artifact fix inline in same session

---

## SoT Remediation — Attribution Protocol

Used by `eval-sot-remediation-runner` to route every SOT issue interactively.

### Evidence format per root cause

```
SOT-DEFECT:
  evidence_sot_quote: "<exact passage from SoT>"
  evidence_gap:       "<what is missing/ambiguous/contradictory and why it blocks>"
  sot_source:         "<SoT file §section>"

WO-MISS:
  evidence_sot_quote: "<SoT passage stating the requirement>"
  evidence_target_loc: "<eval-target §/line>"
  description:        "<what is missing or wrong>"

WO-ERROR:
  evidence_target_loc: "<eval-target §/line>"
  criterion:          "<dimension framework ref>"
  description:        "<specific quality violation>"

UNRESOLVABLE:
  evidence_attempt:   "<what was searched and why evidence could not be located>"
```

### Interactive template (always AskQuestion)

```
Issue [{id}] — {root_cause}
{description}
SoT source: {sot_ref}
Evidence: {evidence}

Options:
  Escalate — cannot resolve; mark escalated
  Reclassify — change root_cause to WO-MISS or WO-ERROR (apply inline Artifact fix if WO-*)
  Ignore — skip this issue
```

Routing outcomes:
- `Escalate` → row `status: escalated`, `decision: escalate`
- `Reclassify → WO-*` → update `root_cause`; apply Artifact fix inline to `REMEDIATION_TARGET_PATH`; row `status: fixed`, `decision: reclassify`
- `Ignore` → row `status: ignored`, `decision: ignore`
- `UNRESOLVABLE → Reclassify → SOT-DEFECT` → treat as Escalate

---

## Mechanical command

`$EVAL_CONTROL` — eval-domain state machine. **Invoke via the generic profile-driven entry** (`eval/scripts/eval_entry.py`); do not call `eval_control.py` directly.

The entry reads `--workflow` (= compose profile id) and dynamically loads the `WorkflowAdapter`
declared by that profile's `eval.adapter_module` / `eval.adapter_class` — no stage name is
hardcoded here (mirrors `start.py`'s `StartAdapter` loading).

```bash
python3 {$SKILL_ROOT}/eval/scripts/eval_entry.py \
  --workflow <profile-id> \
  --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand> [args...]
```

| Concern | SSOT |
|---------|------|
| Step order, stdout handling, branching | `{$SKILL_ROOT}/eval/eval-rules.md` |
| Subcommand list | `eval/scripts/eval_control.py` module docstring or stage entry `--help` |
| Runner write boundaries | `eval/*-runner/SKILL.md` |
