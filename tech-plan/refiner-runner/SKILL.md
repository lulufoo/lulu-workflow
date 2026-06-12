---
name: refiner-runner
description: >-
  Round Iteration refiner for tech-plan drafting. Drafts zoom content per C2
  Matrix Content Form, presents for human confirm, then applies state via
  round_control.py. Invoked by tech-plan/SKILL.md Step 3 on each accept.
---

# refiner-runner

Terminal runner subagent. Executes **one zoom** per invocation.

## Blocking policy

If the workflow cannot advance: **stop** (no retry, skip, or workaround), **report** the reason, and **wait** for user direction before continuing.

Any `round_control.py` non-zero exit → stop and report stderr.

## Parent-Provided Inputs

```
CYCLE_DIR           absolute path to $CACHE_DIR/<cycle_id>
CYCLE_TYPE          feature | topic
SECTION             NS | NG | KD | SK | T (or full section name)
CURRENT_L           current magnification level (0–4)
TARGET_L            target magnification level (CURRENT_L + 1 typically)
ROUND_N             current round number
TECH_DOC_PATH       absolute path to revision{N}/tech-doc.md
ZOOM_EVIDENCE       probe failure evidence from ProbeReport (context for drafting)
```

Self-resolved at runtime:
- `$SKILL_DIR` = `$SKILL_ROOT/tech-plan`
- `$META_KEY` = `tpt_meta_v2_url` when `CYCLE_TYPE=feature`, else `tpt_meta_url`

## Step 1 — Load C2 Content Form

```text
Use $FETCH_TEMPLATE tech-plan $META_KEY
```

Read stdout as meta markdown; locate `## C2 Matrix`.

Find the row for `(SECTION, TARGET_L)` → read **Content Form** and **Delta** columns.

Read `TECH_DOC_PATH` for the current section body and surrounding context (NS, NG for KD zooms, etc.).

## Step 2 — Draft zoom content

Draft **only the Delta** needed to reach `TARGET_L`:

- Preserve existing content; add missing constraints per Content Form.
- Ground in `ZOOM_EVIDENCE`, decision-doc context, and existing tech-doc sections.
- Do **not** auto-write to disk.

Present the draft to the human:

```markdown
## Refiner Draft — {SECTION} L{CURRENT_L}→L{TARGET_L} (Round {ROUND_N})

{proposed section body or delta block}

---
Confirm to write, or provide edits.
```

## Step 3 — Human confirm gate

Wait for explicit human confirmation ("confirm", "写入", "OK", or equivalent).

If the human provides edits, revise the draft and re-present until confirmed.

**Do not call `apply-zoom` without confirmation.**

## Step 4 — Apply zoom state

After confirmation:

```bash
python3 "$SKILL_DIR/scripts/round_control.py" \
  --cycle-dir "$CYCLE_DIR" \
  apply-zoom \
  --section {SECTION} \
  --from-l {CURRENT_L} \
  --to-l {TARGET_L} \
  --round {ROUND_N}
```

On non-zero exit → stop (Blocking policy).

## Step 5 — Write tech-doc section

Update `TECH_DOC_PATH`:

1. Replace the target section body with the confirmed content.
2. Append `[Source: Round {ROUND_N}]` at the end of the section.
3. `state-vector` and `<!-- signed: Round N, L{x}, {timestamp} -->` are updated by `apply-zoom` — do not duplicate.

## Return

```text
Refiner complete — {SECTION} L{CURRENT_L}→L{TARGET_L} (Round {ROUND_N}).
  Signed: yes
  Next: human continues from ProbeReport
```
