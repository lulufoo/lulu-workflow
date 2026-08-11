---
name: deductive-runner
description: >-
  Pre-compose deductive fact production for compose stages with
  pipeline.inductive=false. Dispatches shared fact-intake, then Pd: edge-coverage
  floor + Intent ceiling via section-kw-criteria, and clears a human confirm gate
  before handing facts to compose Writing.
---

# deductive-runner

Run this sub-skill only when dispatched from a compose stage `start` (deductive
path) — e.g. `lulu-plan`.

Produces under the active revision dir (`$DEDUCTIVE_OUT_DIR`):
- **Facts:** `_facts.json` — intake-classified / derived / human-confirmed seeds
- **Pending:** `deductive-pending.json` — confirm-gate SoT (derivation gaps,
  `kw_shortfall`, unreferenced quarantine)

Compose Writing reads **`_facts.json`** validate-only. After `deductive-complete`,
control returns to the parent for Writing.

This runner is **stage-agnostic**: lens set / Intent / derivation edges =
`section-registry`; do not hardcode stage lens names.

**Must:** dispatch `fact-intake-runner` for doc→classified facts; then Derive →
Pending Confirm → Complete.  
**Must not:** invent decisions; label off-edge obligations as `derived`; write
chapter prose; ask the user during Writing (confirm only here); re-read upstream
prose after intake for Steps 2–4; Import upstream `_facts.json` as delivery;
enter delivery Evaluating / StageGate for intake eval; edit the intake source
doc; inline cut / intake-eval / A/B/B′ / Disposition Confirm (owned by
`fact-intake-runner`).

---

## Dispatch Inputs (from parent compose stage)

| Var | Meaning |
|-----|---------|
| `$COMPOSE_PROFILE` | Compose profile id |
| `$CYCLE_ID` | Active cycle id |
| `$SCOPE_REF` | Upstream scope structure ref |
| `$SOURCE_PATH` | Absolute intake SoT doc (fact-intake SoT); format-neutral |
| `$ATOMIZE_SOURCE_PATH` | Retired alias of `$SOURCE_PATH` (same path when present) |
| `$INTENT_BASELINE_REFS` | JSON array of classified, read-only intent baseline refs; not intake input |
| `$NORM_CONSTRAINT_REFS` | JSON array of classified, read-only norm constraint refs; not intake input |
| `$DEDUCTIVE_OUT_DIR` | Active revision dir (`revision{active_doc}/`) |
| `$CODE_GROUNDING` | Optional; profile `pipeline.code_grounding` (boolean string) |

Bind `$SOURCE_PATH` from `$ATOMIZE_SOURCE_PATH` when only the alias is set.
`$REVISION_DIR` for intake = `$DEDUCTIVE_OUT_DIR`. `$PROJECT_ROOT` = `$(pwd)`.

## Script Macros

| Macro | Command |
|-------|---------|
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |
| `$DERIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/derive_control.py"` |
| `$DEDUCTIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/deductive/deductive_control.py" --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |

`$FACTS_CTL` / `$DERIVE_CTL` / `$DEDUCTIVE_CTL`: see each `--help`. Scripts never
invent derived work-item text.

Fetch before Step 2: `$FETCH_COMPOSE --role section-registry` → `SECTION_REGISTRY`.  
Also `$FETCH_COMPOSE --role section-kw-criteria` → `KW_CRITERIA` (published
per-lens KW tables; **ruler for ceiling only**).

---

## Method

Deduction projects **known** upstream substance into this stage’s required lenses
(whole → parts). **SoT = facts + pending.** Mutations land only via `$FACTS_CTL` /
`$DERIVE_CTL` / `$DEDUCTIVE_CTL` — never hand-written JSON.

Collaboration: AI projects and proposes; **user** closes Confirm gates; scripts
move state only.

**Pipeline split:** shared **fact-intake** (cut → structure validate → intake eval →
disposition → Confirm) → **Pd** (floor + ceiling×KW) → pending Confirm → Complete.

---

## Pipeline

**Step 1 Fact Intake → Step 2 Derive → Step 3 Pending Confirm → Step 4 Complete**

### Step 1 — Fact Intake

```bash
$DEDUCTIVE_CTL consume-policy-check
```

Load and follow fact-intake **inline** (interactive Confirm — not a subagent):

```text
Load {SKILL_ROOT}/compose/fact-intake-runner/SKILL.md and follow it.

## Input
REVISION_DIR: <$DEDUCTIVE_OUT_DIR>
PROJECT_ROOT: <$PROJECT_ROOT>
COMPOSE_PROFILE: <$COMPOSE_PROFILE>
CYCLE_ID: <$CYCLE_ID>
SOURCE_PATH: <$SOURCE_PATH>
```

Do not re-implement cut / eval / A/B/B′ / Disposition Confirm here.

```bash
$DEDUCTIVE_CTL pending-init
```

**Done:** fact-intake Return Summary `Status: ok`; pending store exists. Proceed to
Step 2.

### Step 2 — Derive (floor means + ceiling × KW ruler)

**Cognitive split (archive-6.0 Pd×KW):** **Floor** = edge-closure **means** (no KW).
**Ceiling** = Intent projection **means** driven by published **`KW_CRITERIA`** as
the **only thickness ruler**. Do **not** treat “edges closed” or “should-cover
ticked” as “thick enough.” Do **not** run a separate KW-first pass on the intake
pool.

Mechanical plan first (edge floor + topo). **`$DERIVE_CTL plan-edge` hard-fails**
unless intake eval `eval_status` is `done`.

```bash
$DERIVE_CTL plan-edge \
  --revision-dir "$DEDUCTIVE_OUT_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Use stdout: `order`, `edge_holes`, `true_gaps`, `materials_total` (carried-primary pool).

**Semantic work (you):**

1. **Floor (means only — no KW)** — for each hole in `edge_holes`: if projectable from decided substance → emit derived fact `{text, lens_tags:[L], origin:{type:derived, ref:[upstream F-id, …]}, source?}` with **exact** upstream `F-id` in `origin.ref` (and prefer `source`). If not projectable → `$DEDUCTIVE_CTL pending-add` (kind=`edge_hole`). KW upper/target does **not** apply here.
2. **Ceiling × KW ruler** — for each required lens in topo order (same `order`, then any remaining required):
   - Materials: **carried** (and legacy no-disposition) + Intent — **not** default `quarantined`/`not_needed` pool.
   - Ruler: that lens’s block in `KW_CRITERIA` (published table only; **no** separate target-thickness number).
   - Estimate whether current facts satisfy the table’s “can state…” rows (agent semantic judgment).
   - **If unsatisfied** → drive ceiling means: list Intent should-cover / thicken opportunities; projectable **and** on a `decompose`/`instantiate` edge **and** not past the depth the table asks for → `derived` with `F-id` refs. Gap recovery when still thin: carried → quarantined ledger → not_needed ledger → pending. Off-edge / undecided → `$DEDUCTIVE_CTL pending-add` (kind=`off_edge` \| `undecided`) — **never** `origin.type=derived` off-edge. **Forbidden:** inventing to pad KW with no edge.
   - **If satisfied** → stop thickening that lens (KW stop line).
   - **If means exhausted and still unsatisfied** → `$DEDUCTIVE_CTL pending-add` (kind=`kw_shortfall`, `--lens <L>`, summary = table gap). Do **not** silently pass.
   - **Do not** batch-retag quarantine/not_needed inside Pd. Post-intake promote/retag
     only: `$DEDUCTIVE_CTL disposition-patch-*` with an agent-chosen patch file
     (not intake Confirm). Intake Disposition Confirm stays
     `{slice}/fact-intake-disposition-review.patch` via `$FACT_INTAKE_DISPOSITION_CTL`.
3. **Cascade:** later lenses see facts appended earlier. If ceiling appends create new `edge_holes`, re-run floor for those holes (**still no KW**), then resume ceiling×KW for affected lenses.
4. **Must not** produce `origin.type=discovered`.

When you have a derived batch:

```bash
$DERIVE_CTL append \
  --revision-dir "$DEDUCTIVE_OUT_DIR" \
  --derived-file "<path to derived.json>" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

```bash
$FACTS_CTL validate --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"
```

**Done:** validate exit 0; every floor hole covered or pending; every required lens either KW-satisfied or has open `kw_shortfall` / other pending. Proceed to Step 3.

### Step 3 — Pending Confirm

Interactive in this conversation (not a subagent).

1. Refresh unreferenced quarantine list:

```bash
$DEDUCTIVE_CTL quarantine-unref
```

For each listed quarantined id: present options (promote/retag via
`$DEDUCTIVE_CTL disposition-patch-*` post-intake retag patch, or fact update
commands; mark out-of-scope; escalate upstream). Do **not** reuse
`fact-intake-disposition-review.patch` here. Record via `$DEDUCTIVE_CTL
pending-add` (kind=`quarantine_unref`) then `$DEDUCTIVE_CTL pending-resolve` as
the user chooses — or resolve immediately per `--help`. Citing a
quarantined/not_needed id settles unreferenced-quarantine accounting without
retagging; **retag/promote** requires carried + Plan tags.

2. Present open pending (derivation gaps + quarantine + **`kw_shortfall`**). For each item: options traceable to decided material, or `insufficient`. User chooses:
   - **Local seed (default):** append fact `origin.type=seed` with confirm ref → `$DERIVE_CTL append` or `$FACTS_CTL write` full array per `--help`; then `$DEDUCTIVE_CTL pending-resolve`.
   - **Escalate upstream:** resolve pending as deferred/escalated; do not invent local substance.
   - **`kw_shortfall` accept (soft gate):** user explicitly accepts “KW table not met for this lens” → `$DEDUCTIVE_CTL pending-resolve --status resolved` with note in summary/chat that accept-shortfall was chosen. **Forbidden:** resolving `kw_shortfall` without showing table gap + asking.
3. Incremental settle: resolved ids must not reappear (`pending-resolve` enforces). Full intake re-run only when upstream material is replaced.

**Hard gate:** `gate-check` fails when (a) `deductive-pending.json` is missing, (b) any pending is still open (including open `kw_shortfall`), or (c) an unreferenced quarantined fact is not settled via `quarantine_unref` pending (resolve / escalate / out_of_scope). Citing a quarantined id from a new fact also clears it from (c).

```bash
$DEDUCTIVE_CTL gate-check
```

**Done:** `gate-check` exit 0. Proceed to Step 4.

### Step 4 — Complete

```bash
$FACTS_CTL validate --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"
$DEDUCTIVE_CTL gate-check
```

Return control to the parent compose stage. Parent runs `$L_STEP deductive-complete` then `$L_STEP begin-writing`.

**Done:** both commands exit 0; `_facts.json` ready for Writing validate-only.

---

## Output Contract

**Facts:** `_facts.json` — `F-n` with `text`, `lens_tags` (empty for `quarantined` /
`not_needed`), optional `origin` / `derivation` / `source` / `anchors`. Intake
facts: `derivation.disposition` ∈ {`carried`,`quarantined`,`not_needed`};
`not_needed` requires `rule_id` ∈ role `consume_policy.rules[].id`.

**Pending:** `deductive-pending.json` — open/resolved items; schema via
`$DEDUCTIVE_CTL --help`.

**Disposition Confirm (intake):** `{slice}/fact-intake-disposition-review.patch`
(owned by `fact-intake-runner` / `$FACT_INTAKE_DISPOSITION_CTL`).

**Post-intake retag patch (optional, Steps 2–3):** agent-chosen path via
`$DEDUCTIVE_CTL disposition-patch-*` — not the intake Confirm artifact.

**Compose Writing input:** `_facts.json` only.

---

## Constraints

- No AI hand-written JSON files — control commands only (disposition patches
  drafted then applied by control).
- D1/D2 read only this stage’s facts — never re-open upstream `.md` after intake.
- Off-edge obligations → pending only (not `derived`).
- Ceiling thickness ruler = published `section-kw-criteria` only; floor ignores KW;
  no separate target-thickness field; no KW-first intake-pool pass.
- Quarantined / not_needed facts remain addressable; cite settles unref accounting;
  leftover unreferenced **quarantined** ids must go through Step 3.
- Writing / delivery Eval / FreeEdit are out of this runner’s scope.
