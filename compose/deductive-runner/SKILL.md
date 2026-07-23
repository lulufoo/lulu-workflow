---
name: deductive-runner
description: >-
  Pre-compose deductive fact production for compose stages with
  drafting.inductive=false. Materializes upstream scope into _facts.json (P0),
  completes required lenses via intent-ceiling + edge-coverage floor (Pd), and
  clears a human confirm gate before handing facts to compose Initializing.
---

# deductive-runner

Run this sub-skill only when dispatched from a compose stage `start` (deductive path) — e.g. `lulu-plan`.

Produces under the active revision dir (`$DEDUCTIVE_OUT_DIR`):
- **Facts:** `_facts.json` — Intake + derived / human-confirmed seeds
- **Pending:** `deductive-pending.json` — confirm-gate SoT (derivation gaps + unreferenced quarantine)

Compose Initializing reads **`_facts.json`** validate-only. After `deductive-complete`, control returns to the parent for Initializing.

This runner is **stage-agnostic**: lens set / Intent / derivation edges = `section-registry`; do not hardcode stage lens names.

**Must not:** invent decisions; label off-edge obligations as `derived`; write chapter prose; ask the user during Initializing (confirm only here); read upstream prose during Steps 2–3 (Intake only); Import upstream `_facts.json` as delivery; enter workflow `Evaluating` for fidelity; edit the input delivery doc during fidelity remediation.

---

## Dispatch Inputs (from parent compose stage)

| Var | Meaning |
|-----|---------|
| `$COMPOSE_PROFILE` | Compose profile id |
| `$CYCLE_ID` | Active cycle id |
| `$SCOPE_REF` | Upstream scope SSOT path (prose or `decision-fact.json`) |
| `$DEDUCTIVE_OUT_DIR` | Active revision dir (`revision{active_doc}/`) |
| `$CODE_GROUNDING` | Optional; profile `drafting.code_grounding` (boolean string) |

## Script Macros

| Macro | Command |
|-------|---------|
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |
| `$DERIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/derive_control.py"` |
| `$DEDUCTIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/deductive/deductive_control.py" --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |
| `$DECISION_FACT_CLAIM_CTL` | `python3 "$SKILL_ROOT/compose/scripts/core/decision_fact_claim_control.py" --revision-dir "$DEDUCTIVE_OUT_DIR"` |
| `$FIDELITY_EVAL_CONTROL` | `python3 "$SKILL_ROOT/compose/fidelity/scripts/fidelity_control.py" --revision-dir "$DEDUCTIVE_OUT_DIR"` |

`$FACTS_CTL` / `$DERIVE_CTL` / `$DEDUCTIVE_CTL`: see each `--help`. Scripts never invent derived work-item text.

Fetch before Step 1: `$FETCH_COMPOSE --role section-registry` → `SECTION_REGISTRY` (`section_order`, per-lens `intent`/`desc`/`intent_boundary`/`relations`/`presence`).

---

## Method

Deduction projects **known** upstream substance into this stage’s required lenses (whole → parts). **SoT = facts + pending.** Mutations land only via `$FACTS_CTL` / `$DERIVE_CTL` / `$DEDUCTIVE_CTL` / `$DECISION_FACT_CLAIM_CTL` — never hand-written JSON.

Collaboration: AI projects and proposes; **user** closes the confirm gate; scripts move state only.

---

## Pipeline

**Step 1 Intake → Step 2 Derive (floor + ceiling) → Step 3 Confirm → Step 4 Complete**

### Step 1 — Intake

Materialize upstream into this stage’s `_facts.json`. Exactly one branch:

1. **Unit-import** — when `$SCOPE_REF` is `decision-fact.json`: `$DECISION_FACT_CLAIM_CTL ensure`; claim→emit local seed facts→settled for units pulled into this stage’s lenses; leave unclaimed on the ledger (do not drop). Then:
   ```bash
   $FIDELITY_EVAL_CONTROL mark-skipped --reason unit-import
   ```
2. **Atomize** — else: atomize `$SCOPE_REF` prose once (whole doc); tag `lens_tags` from Intent SSOT (N:M; zero tags ⇒ quarantine candidate). Persist via `$FACTS_CTL write`. **Do not** Import upstream `_facts.json` (delivery SSOT = doc). Default: **omit** fact `origin` (optional); if present, `origin.ref` must be a non-empty string array.

Then:

```bash
$FACTS_CTL validate --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"
$DEDUCTIVE_CTL pending-init
```

**After Atomize only — fidelity gate (E1∥E2, required before Derive):**

```bash
$FIDELITY_EVAL_CONTROL init --intake atomize
$FIDELITY_EVAL_CONTROL paths
```

Run **E1** and **E2** in parallel (subagents OK) using defs under `$SKILL_ROOT/compose/fidelity/dimension-defs/` (`e1-doc-coverage`, `e2-fact-provenance`). SoT = input delivery doc (`scope_doc` from `paths`); EvalTarget + remediation = this revision `_facts.json`. Remediate **only** `_facts.json`. Max **3** rounds; same round must clear both dimensions. On round-cap with remaining blocking issues: ask the user in **plain text with multiple options and a stated lean** (do not use AskQuestion tool).

When E1∩E2 clear:

```bash
$FIDELITY_EVAL_CONTROL mark-passed
```

**Done:** validate exit 0; pending store ready; fidelity `passed` or `skipped`. Proceed to Step 2.

### Step 2 — Derive (floor + ceiling)

Mechanical plan first (edge floor + topo). **`$DERIVE_CTL plan-edge` hard-fails** unless fidelity status is `passed`|`skipped`.

```bash
$DERIVE_CTL plan-edge \
  --revision-dir "$DEDUCTIVE_OUT_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Use stdout: `order` (upstream-first lenses with holes or ceiling pass needed), `edge_holes` (per lens, uncovered upstream `F-id`s), `true_gaps` (required + zero facts + no derivation edge — do **not** invent; add pending).

**Semantic work (you):**

1. **Floor** — for each hole in `edge_holes`: if projectable from decided substance → emit derived fact `{text, lens_tags:[L], origin:{type:derived, ref:[upstream F-id, …]}, source?}` with **exact** upstream `F-id` in `origin.ref` (and prefer `source`). If not projectable → `$DEDUCTIVE_CTL pending-add` (kind=`edge_hole`).
2. **Ceiling** — for each required lens in topo order (same `order`, then any remaining required): using **all** stage facts (including quarantined) + Intent, list should-cover items. Already covered → skip. Projectable **and** on a `decompose`/`instantiate` edge → derived with `F-id` refs (may cite quarantined ids as material). Off-edge should-cover or undecided → `$DEDUCTIVE_CTL pending-add` (kind=`off_edge` \| `undecided`) — **never** `origin.type=derived` for off-edge.
3. **Must not** produce `origin.type=discovered`.
4. Same-pass cascade: later lenses see facts already appended earlier in `order`.

When you have a derived batch:

```bash
$DERIVE_CTL append \
  --revision-dir "$DEDUCTIVE_OUT_DIR" \
  --derived-file "<path to derived.json>" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Optional self-audit when `order` was non-empty (same contract as derive `--help`).

```bash
$FACTS_CTL validate --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"
```

**Done:** validate exit 0; every floor hole is either covered by a derived/seed ref or has a pending item. Proceed to Step 3.

### Step 3 — Confirm

Interactive in this conversation (not a subagent).

1. Refresh unreferenced quarantine list:

```bash
$DEDUCTIVE_CTL quarantine-unref
```

For each listed quarantined id: present options (promote/retag via new seed or fact update commands allowed by `$DEDUCTIVE_CTL` / `$FACTS_CTL`; mark out-of-scope; escalate upstream). Record via `$DEDUCTIVE_CTL pending-add` (kind=`quarantine_unref`) then `$DEDUCTIVE_CTL pending-resolve` as the user chooses — or resolve immediately per `--help`.

2. Present open pending (derivation gaps + quarantine). For each item: options traceable to decided material, or `insufficient`. User chooses:
   - **Local seed (default):** append fact `origin.type=seed` with confirm ref → `$DERIVE_CTL append` or `$FACTS_CTL write` full array per `--help`; then `$DEDUCTIVE_CTL pending-resolve`.
   - **Escalate upstream:** resolve pending as deferred/escalated; do not invent local substance.
3. Incremental settle: resolved ids must not reappear (`pending-resolve` enforces). Full Intake re-run only when upstream material is replaced.

**Hard gate:** `gate-check` fails when (a) `deductive-pending.json` is missing, (b) any pending is still open, or (c) an unreferenced quarantined fact is not settled via `quarantine_unref` pending (resolve / escalate / out_of_scope). Citing a quarantined id from a new fact also clears it from (c).

```bash
$DEDUCTIVE_CTL gate-check
```

**Done:** `gate-check` exit 0. Proceed to Step 4.

### Step 4 — Complete

```bash
$FACTS_CTL validate --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"
$DEDUCTIVE_CTL gate-check
```

Return control to the parent compose stage. Parent runs `$DRAFT_CONTROL deductive-complete` then `begin-init`.

**Done:** both commands exit 0; `_facts.json` ready for Init validate-only.

---

## Output Contract

**Facts:** `_facts.json` — `F-n` with `text`, `lens_tags` (empty only when quarantined), optional `origin` / `derivation` / `source` / `anchors`.

**Pending:** `deductive-pending.json` — open/resolved items; schema via `$DEDUCTIVE_CTL --help`.

**Compose init input:** `_facts.json` only.

---

## Constraints

- No AI hand-written JSON files — control commands only.
- D1/D2 read only this stage’s facts — never re-open upstream `.md` after Intake.
- Off-edge obligations → pending only (not `derived`).
- Quarantined facts are valid input material; citing their `F-id` from a new fact marks them processed; leftover unreferenced ids must go through Step 3.
- Init / Eval / FreeEdit are out of this runner’s scope.
