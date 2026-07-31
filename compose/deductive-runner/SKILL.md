---
name: deductive-runner
description: >-
  Pre-compose deductive fact production for compose stages with
  pipeline.inductive=false. Materializes upstream scope into _facts.json (P0),
  applies Atomize consume disposition (A→B→B′), fidelity, Confirm disposition
  patch, then completes required lenses via intent-ceiling + edge-coverage floor
  (Pd), and clears a human confirm gate before handing facts to compose
  Initializing.
---

# deductive-runner

Run this sub-skill only when dispatched from a compose stage `start` (deductive path) — e.g. `lulu-plan`.

Produces under the active revision dir (`$DEDUCTIVE_OUT_DIR`):
- **Facts:** `_facts.json` — Intake + dispositioned / derived / human-confirmed seeds
- **Pending:** `deductive-pending.json` — confirm-gate SoT (derivation gaps + unreferenced quarantine)
- **Disposition patch (Atomize):** `deductive-disposition-review.patch` — Confirm op-list before Pd

Compose Initializing reads **`_facts.json`** validate-only. After `deductive-complete`, control returns to the parent for Initializing.

This runner is **stage-agnostic**: lens set / Intent / derivation edges = `section-registry`; do not hardcode stage lens names.

**Must not:** invent decisions; label off-edge obligations as `derived`; write chapter prose; ask the user during Initializing (confirm only here); read upstream prose during Steps 2–4 (Intake only); Import upstream `_facts.json` as delivery; enter workflow `Evaluating` for fidelity; edit the input delivery doc during fidelity remediation; hand-edit `_facts.json` for Confirm disposition (use `$DEDUCTIVE_CTL disposition-patch-*`).

---

## Dispatch Inputs (from parent compose stage)

| Var | Meaning |
|-----|---------|
| `$COMPOSE_PROFILE` | Compose profile id |
| `$CYCLE_ID` | Active cycle id |
| `$SCOPE_REF` | Upstream scope SSOT (`*-package.json` or `decision-fact.json`) |
| `$ATOMIZE_DOC_PATH` | When `$SCOPE_REF` is a package: absolute path of the **current focus** upstream prose doc (Atomize / fidelity SoT). Absent for unit-import. |
| `$DEDUCTIVE_OUT_DIR` | Active revision dir (`revision{active_doc}/`) |
| `$CODE_GROUNDING` | Optional; profile `pipeline.code_grounding` (boolean string) |

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

Fetch before Step 1: `$FETCH_COMPOSE --role section-registry` → `SECTION_REGISTRY` (`section_order`, per-lens `intent`/`desc`/`intent_boundary`/`relations`/`presence`). Also fetch `--role role-instance` when Atomize (consume policy).

---

## Method

Deduction projects **known** upstream substance into this stage’s required lenses (whole → parts). **SoT = facts + pending.** Mutations land only via `$FACTS_CTL` / `$DERIVE_CTL` / `$DEDUCTIVE_CTL` / `$DECISION_FACT_CLAIM_CTL` — never hand-written JSON.

Collaboration: AI projects and proposes; **user** closes Confirm gates; scripts move state only.

**Atomize disposition funnel (L3):** Atomize cut → **A** (consume policy → `not_needed` only) → **B** (Intent tags → `carried` / `quarantined`) → **B′** (repair A false `not_needed` only) → **E1∥E2** → **Confirm op-list patch** → **Pd** → pending Confirm → Complete.

---

## Pipeline

**Step 1 Intake → Step 1b Fidelity → Step 1c Disposition Confirm → Step 2 Derive → Step 3 Pending Confirm → Step 4 Complete**

### Step 1 — Intake

Materialize upstream into this stage’s `_facts.json`. Exactly one branch:

1. **Unit-import** — when `$SCOPE_REF` is `decision-fact.json`: `$DECISION_FACT_CLAIM_CTL ensure`; claim→emit local seed facts→settled for units pulled into this stage’s lenses; leave unclaimed on the ledger (do not drop). Then:
   ```bash
   $FIDELITY_EVAL_CONTROL mark-skipped --reason unit-import
   ```
   Unit-import **does not** run A→B consume funnel in v1 (deferred). Proceed to Step 2 after pending-init + validate (no `--require-derivation`).

2. **Atomize** — else: atomize **`$ATOMIZE_DOC_PATH`** prose once (required when `$SCOPE_REF` is a `*-package.json`; do **not** treat the package JSON as prose).

   **Hard gate first:**
   ```bash
   $DEDUCTIVE_CTL consume-policy-check
   ```

   **A — consume policy (don’t-list only):** For each atom, evaluate role `consume_policy.rules[]` (`D-RISK` / `D-SEAM` / `D-DEC`, …). If a rule is **true** → write `derivation.disposition=not_needed` + `rule_id` + non-empty `upstream_ref` (doc anchors; same family as E2) + `lens_tags=[]`. If unsure or false → **pass to B** (do **not** write `quarantined` or `carried` in A).

   **B — Intent tagging:** For A-passed atoms only, match this stage Intent SSOT. Clear match → `carried` + Plan `lens_tags` (N:M). No clear match → `quarantined` + empty tags. **Forbidden:** stuffing `CTX` (or any lens) to avoid quarantine. Do **not** keep Design lens keys (`DECISION`/`RISK`/`SEAM`, …) as tags.

   **B′ — mis-kill repair only:** Scan `not_needed`. Promote only when (strict Intent hit) ∧ (re-judge exclusion rule is **false**). True exclusions stay `not_needed` (expected auto-recover ≈ 0). Do **not** promote merely because text “looks like” CTX.

   Persist via `$FACTS_CTL write` into the focus L bucket. Every Atomize fact **must** carry `derivation` (`carried`|`quarantined`|`not_needed`) and non-empty `upstream_ref`. Default: **omit** fact `origin` (optional).

Then (both branches):

```bash
$FACTS_CTL validate --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"
$DEDUCTIVE_CTL pending-init
```

**After Atomize only** — tighten validate + fidelity:

```bash
$FACTS_CTL validate --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" \
  --require-derivation --require-consume-policy
$FIDELITY_EVAL_CONTROL init --intake atomize
$FIDELITY_EVAL_CONTROL paths
```

### Step 1b — Fidelity (E1∥E2; Atomize only; before Confirm / Pd)

Run **E1** and **E2** in parallel (subagents OK) using defs under `$SKILL_ROOT/compose/fidelity/dimension-defs/` (`e1-doc-coverage`, `e2-fact-provenance`). SoT = `$ATOMIZE_DOC_PATH` prose (`scope_doc` from `paths` must resolve to that doc, not the package JSON); EvalTarget + remediation = this revision `_facts.json`. Remediate **only** `_facts.json`. Max **3** rounds; same round must clear both dimensions. On round-cap with remaining blocking issues: ask the user in **plain text with multiple options and a stated lean** (do not use AskQuestion tool).

**E1 contract:** every doc obligation unit → exactly one fact disposition ∈ {`carried`,`quarantined`,`not_needed`}; for **carried** facts, no weakening vs doc (narrow blocking list in dim-def).

When E1∩E2 clear:

```bash
$FIDELITY_EVAL_CONTROL mark-passed
```

**Done (Atomize):** validate exit 0 with derivation+consume-policy; fidelity `passed`. Proceed to Step 1c.  
**Done (Unit-import):** fidelity `skipped`. Skip Step 1c; proceed to Step 2.

### Step 1c — Disposition Confirm (Atomize only; before Pd)

Draft op-list JSON at `$DEDUCTIVE_OUT_DIR/deductive-disposition-review.patch` (agent drafts; **no** hand-edit of `_facts.json`):

- `version: "1"`
- `counts` — disposition totals
- `cohorts` — theme/reason groups with 1–3 exemplar `F-id`s (full id lists may sit in `appendix_ids`, not in chat)
- `ops` — `promote` / `demote` / `retag` / `escalate`

Chat: path + counts + accept / edit-patch / reject-cohorts — **not** full id dumps.

```bash
$DEDUCTIVE_CTL disposition-patch-validate --patch-file "$DEDUCTIVE_OUT_DIR/deductive-disposition-review.patch"
# after user accept:
$DEDUCTIVE_CTL disposition-patch-apply --patch-file "$DEDUCTIVE_OUT_DIR/deductive-disposition-review.patch"
```

When user accepts current dispositions unchanged, write a patch with a single metadata op `{"op":"escalate","fact_id":"<one exemplar>","note":"accept-as-is"}` so the Confirm artifact exists (no fact mutation). When promote/demote/retag is needed, ops must be non-empty and applied after validate.

**Done:** patch validated; applied when ops mutate facts. Proceed to Step 2.

### Step 2 — Derive (floor + ceiling)

Mechanical plan first (edge floor + topo). **`$DERIVE_CTL plan-edge` hard-fails** unless fidelity status is `passed`|`skipped`.

```bash
$DERIVE_CTL plan-edge \
  --revision-dir "$DEDUCTIVE_OUT_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Use stdout: `order`, `edge_holes`, `true_gaps`, `materials_total` (carried-primary pool).

**Semantic work (you):**

1. **Floor** — for each hole in `edge_holes`: if projectable from decided substance → emit derived fact `{text, lens_tags:[L], origin:{type:derived, ref:[upstream F-id, …]}, source?}` with **exact** upstream `F-id` in `origin.ref` (and prefer `source`). If not projectable → `$DEDUCTIVE_CTL pending-add` (kind=`edge_hole`).
2. **Ceiling** — for each required lens in topo order (same `order`, then any remaining required): using **carried** (and legacy no-disposition) materials + Intent — **not** default `quarantined`/`not_needed` pool — list should-cover items. Already covered → skip. Projectable **and** on a `decompose`/`instantiate` edge → derived with `F-id` refs. Gap recovery order when a required lens is still missing substance: carried → quarantined ledger → not_needed ledger → pending. Off-edge should-cover or undecided → `$DEDUCTIVE_CTL pending-add` (kind=`off_edge` \| `undecided`) — **never** `origin.type=derived` for off-edge. **Do not** batch-retag quarantine/not_needed inside Pd; promote only via Confirm patch or explicit promote ops.
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

```bash
$FACTS_CTL validate --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"
```

**Done:** validate exit 0; every floor hole is either covered by a derived/seed ref or has a pending item. Proceed to Step 3.

### Step 3 — Pending Confirm

Interactive in this conversation (not a subagent).

1. Refresh unreferenced quarantine list:

```bash
$DEDUCTIVE_CTL quarantine-unref
```

For each listed quarantined id: present options (promote/retag via disposition patch or fact update commands; mark out-of-scope; escalate upstream). Record via `$DEDUCTIVE_CTL pending-add` (kind=`quarantine_unref`) then `$DEDUCTIVE_CTL pending-resolve` as the user chooses — or resolve immediately per `--help`. Citing a quarantined/not_needed id settles unreferenced-quarantine accounting without retagging; **retag/promote** requires carried + Plan tags.

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

Return control to the parent compose stage. Parent runs `$L_STEP deductive-complete` then `$L_STEP begin-init`.

**Done:** both commands exit 0; `_facts.json` ready for Init validate-only.

---

## Output Contract

**Facts:** `_facts.json` — `F-n` with `text`, `lens_tags` (empty for `quarantined` / `not_needed`), optional `origin` / `derivation` / `source` / `anchors`. Atomize: `derivation.disposition` ∈ {`carried`,`quarantined`,`not_needed`}; `not_needed` requires `rule_id` ∈ role `consume_policy.rules[].id`.

**Pending:** `deductive-pending.json` — open/resolved items; schema via `$DEDUCTIVE_CTL --help`.

**Disposition patch:** `deductive-disposition-review.patch` — op-list JSON; validate/apply via `$DEDUCTIVE_CTL`.

**Compose init input:** `_facts.json` only.

---

## Constraints

- No AI hand-written JSON files — control commands only (disposition patch is drafted then applied by control).
- D1/D2 read only this stage’s facts — never re-open upstream `.md` after Intake.
- Off-edge obligations → pending only (not `derived`).
- A writes **only** `not_needed` (or pass); B alone routinely writes `quarantined`/`carried`.
- Quarantined / not_needed facts remain addressable; cite settles unref accounting; leftover unreferenced **quarantined** ids must go through Step 3.
- Init / Eval / FreeEdit are out of this runner’s scope.
