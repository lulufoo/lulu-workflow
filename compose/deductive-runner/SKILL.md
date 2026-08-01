---
name: deductive-runner
description: >-
  Pre-compose deductive fact production for compose stages with
  pipeline.inductive=false. Materializes upstream scope into _facts.json (P0),
  applies Atomize consume disposition (A→B→B′), fidelity, Confirm disposition
  patch, then Pd: edge-coverage floor (means) + Intent ceiling driven by
  published section-kw-criteria (ruler), and clears a human confirm gate before
  handing facts to compose Initializing.
---

# deductive-runner

Run this sub-skill only when dispatched from a compose stage `start` (deductive path) — e.g. `lulu-plan`.

Produces under the active revision dir (`$DEDUCTIVE_OUT_DIR`):
- **Facts:** `_facts.json` — Intake + dispositioned / derived / human-confirmed seeds
- **Pending:** `deductive-pending.json` — confirm-gate SoT (derivation gaps, `kw_shortfall`, unreferenced quarantine)
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
| `$SCOPE_REF` | Upstream scope structure ref |
| `$ATOMIZE_SOURCE_PATH` | Absolute path of the current focus source material (Atomize / fidelity SoT); format-neutral. |
| `$INTENT_BASELINE_REFS` | JSON array of classified, read-only intent baseline refs; not Atomize input. |
| `$NORM_CONSTRAINT_REFS` | JSON array of classified, read-only norm constraint refs; not Atomize input. |
| `$DEDUCTIVE_OUT_DIR` | Active revision dir (`revision{active_doc}/`) |
| `$CODE_GROUNDING` | Optional; profile `pipeline.code_grounding` (boolean string) |

## Script Macros

| Macro | Command |
|-------|---------|
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |
| `$DERIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/derive_control.py"` |
| `$DEDUCTIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/deductive/deductive_control.py" --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |
| `$FIDELITY_EVAL_CONTROL` | `python3 "$SKILL_ROOT/compose/fidelity/scripts/fidelity_control.py" --revision-dir "$DEDUCTIVE_OUT_DIR"` |

`$FACTS_CTL` / `$DERIVE_CTL` / `$DEDUCTIVE_CTL`: see each `--help`. Scripts never invent derived work-item text.

Fetch before Step 1: `$FETCH_COMPOSE --role section-registry` → `SECTION_REGISTRY` (`section_order`, per-lens `intent`/`desc`/`intent_boundary`/`relations`/`presence`). Also fetch `--role role-instance` when Atomize (consume policy).  
Fetch before Step 2: `$FETCH_COMPOSE --role section-kw-criteria` → `KW_CRITERIA` (published per-lens KW tables; **ruler for ceiling only** — no separate target-thickness field).

---

## Method

Deduction projects **known** upstream substance into this stage’s required lenses (whole → parts). **SoT = facts + pending.** Mutations land only via `$FACTS_CTL` / `$DERIVE_CTL` / `$DEDUCTIVE_CTL` — never hand-written JSON.

Collaboration: AI projects and proposes; **user** closes Confirm gates; scripts move state only.

**Atomize disposition funnel (L3):** Atomize cut → **A** (consume policy → `not_needed` only) → **B** (Intent tags → `carried` / `quarantined`) → **B′** (repair A false `not_needed` only) → **E1∥E2** → **Confirm op-list patch** → **Pd** → pending Confirm → Complete.

---

## Pipeline

**Step 1 Intake → Step 1b Fidelity → Step 1c Disposition Confirm → Step 2 Derive → Step 3 Pending Confirm → Step 4 Complete**

### Step 1 — Intake

Atomize **`$ATOMIZE_SOURCE_PATH`** once, regardless of source format. Read the source material content; do not treat the scope structure ref as input prose.

**Hard gate first:**
```bash
$DEDUCTIVE_CTL consume-policy-check
```

**A — consume policy (don’t-list only):** For each atom, evaluate role `consume_policy.rules[]` (`D-RISK` / `D-SEAM` / `D-DEC`, …). If a rule is **true** → write `derivation.disposition=not_needed` + `rule_id` + non-empty `upstream_ref` (source anchors; same family as E2) + `lens_tags=[]`. If unsure or false → **pass to B** (do **not** write `quarantined` or `carried` in A).

**B — Intent tagging:** For A-passed atoms only, match this stage Intent SSOT. Clear match → `carried` + Plan `lens_tags` (N:M). No clear match → `quarantined` + empty tags. **Forbidden:** stuffing `CTX` (or any lens) to avoid quarantine. Do **not** keep Design lens keys (`DECISION`/`RISK`/`SEAM`, …) as tags.

**B′ — mis-kill repair only:** Scan `not_needed`. Promote only when (strict Intent hit) ∧ (re-judge exclusion rule is **false**). True exclusions stay `not_needed` (expected auto-recover ≈ 0). Do **not** promote merely because text “looks like” CTX.

Persist via `$FACTS_CTL write` into the focus L bucket. Every Atomize fact **must** carry `derivation` (`carried`|`quarantined`|`not_needed`) and non-empty `upstream_ref`. Default: **omit** fact `origin` (optional).

```bash
$FACTS_CTL validate --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"
$DEDUCTIVE_CTL pending-init
```

Tighten validate + bind fidelity:

```bash
$FACTS_CTL validate --revision-dir "$DEDUCTIVE_OUT_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" \
  --require-derivation --require-consume-policy
$FIDELITY_EVAL_CONTROL init --intake atomize
$FIDELITY_EVAL_CONTROL paths
```

### Step 1b — Fidelity (E1∥E2; before Confirm / Pd)

Run **E1** and **E2** in parallel (subagents OK) using defs under `$SKILL_ROOT/compose/fidelity/dimension-defs/` (`e1-doc-coverage`, `e2-fact-provenance`). SoT = `$ATOMIZE_SOURCE_PATH` content (`source_path` from `paths` must equal that path); EvalTarget + remediation = this revision `_facts.json`. Remediate **only** `_facts.json`. Max **3** rounds; same round must clear both dimensions. On round-cap with remaining blocking issues: ask the user in **plain text with multiple options and a stated lean** (do not use AskQuestion tool).

**E1 contract:** every doc obligation unit → exactly one fact disposition ∈ {`carried`,`quarantined`,`not_needed`}; for **carried** facts, no weakening vs doc (narrow blocking list in dim-def).

When E1∩E2 clear:

```bash
$FIDELITY_EVAL_CONTROL mark-passed
```

**Done:** validate exit 0 with derivation+consume-policy; fidelity `passed`. Proceed to Step 1c.

### Step 1c — Disposition Confirm (before Pd)

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

### Step 2 — Derive (floor means + ceiling × KW ruler)

**Cognitive split (archive-6.0 Pd×KW):** **Floor** = edge-closure **means** (no KW). **Ceiling** = Intent projection **means** driven by published **`KW_CRITERIA`** as the **only thickness ruler**. Do **not** treat “edges closed” or “should-cover ticked” as “thick enough.” Do **not** run a separate KW-first pass on the Atomize pool.

Mechanical plan first (edge floor + topo). **`$DERIVE_CTL plan-edge` hard-fails** unless fidelity status is `passed`.

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
   - **Do not** batch-retag quarantine/not_needed inside Pd; promote only via Confirm patch or explicit promote ops.
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

For each listed quarantined id: present options (promote/retag via disposition patch or fact update commands; mark out-of-scope; escalate upstream). Record via `$DEDUCTIVE_CTL pending-add` (kind=`quarantine_unref`) then `$DEDUCTIVE_CTL pending-resolve` as the user chooses — or resolve immediately per `--help`. Citing a quarantined/not_needed id settles unreferenced-quarantine accounting without retagging; **retag/promote** requires carried + Plan tags.

2. Present open pending (derivation gaps + quarantine + **`kw_shortfall`**). For each item: options traceable to decided material, or `insufficient`. User chooses:
   - **Local seed (default):** append fact `origin.type=seed` with confirm ref → `$DERIVE_CTL append` or `$FACTS_CTL write` full array per `--help`; then `$DEDUCTIVE_CTL pending-resolve`.
   - **Escalate upstream:** resolve pending as deferred/escalated; do not invent local substance.
   - **`kw_shortfall` accept (soft gate):** user explicitly accepts “KW table not met for this lens” → `$DEDUCTIVE_CTL pending-resolve --status resolved` with note in summary/chat that accept-shortfall was chosen. **Forbidden:** resolving `kw_shortfall` without showing table gap + asking.
3. Incremental settle: resolved ids must not reappear (`pending-resolve` enforces). Full Intake re-run only when upstream material is replaced.

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
- Ceiling thickness ruler = published `section-kw-criteria` only; floor ignores KW; no separate target-thickness field; no KW-first Atomize-pool pass.
- A writes **only** `not_needed` (or pass); B alone routinely writes `quarantined`/`carried`.
- Quarantined / not_needed facts remain addressable; cite settles unref accounting; leftover unreferenced **quarantined** ids must go through Step 3.
- Init / Eval / FreeEdit are out of this runner’s scope.
