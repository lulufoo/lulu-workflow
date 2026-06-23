---
name: initializing-runner
description: >-
  Autonomous Initializing step for compose-profile drafting. Loads upstream scope
  doc and frameworks; composes per-section body via I* / F / C; persists each
  section incrementally and returns control to the parent Initializing step.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside a parent compose stage Drafting shell.

Use `$COMPOSE_PROFILE` from parent dispatch; kernel default applies only when omitted.

## Scope

Steps I1–I2 only (I2 includes I2a–I2f):

1. Load scope doc, section-registry (with `intent`), outline-registry, section-kw-criteria, and Plan Scope Constraints.
2. Compose and persist each section: Filter `I*` → Derive `F` → Derive `C` → Write body → Derive display title → Persist section (see Theory).

Do not ask the user questions. Do not run InDialogue, Reopen, Evaluating, or delivery work.

## Theory (Compose)

See [`../../references/compose-theory.md`](../../references/compose-theory.md).

**Order (strict):** I2a Filter `I*` → I2b Derive `F` → I2c Derive `C` → I2d Write body → I2e Derive display title → I2f Persist section.

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` |
| `$SCOPE_DOC_PATH` | Absolute path to compose intent SSOT (design-doc or decision-doc) |
| `$OUTPUT_DOC_PATH` | Absolute path to output document (design-doc.md or tech-doc.md) |
| `$COMPOSE_PROFILE` | Compose profile id from parent dispatch |
| `$CYCLE_TYPE` | `feature` |
| `$CYCLE_ID` | Active cycle id |

Self-resolved: `$PROJECT_ROOT` = `$(pwd)` · `$OUTPUT_DOC_PATH` from parent input (fallback `{REVISION_DIR}/tech-doc.md`)

All compose and scope macros (`$FETCH_COMPOSE`, `$RESOLVE_PLAN_ROLE`, `$RESOLVE_DOMAIN`, `$COMPOSE_DOC_CONTROL`) **must** pass `--profile "$COMPOSE_PROFILE"`. `$FETCH_COMPOSE` **must** also pass `--cycle-id "$CYCLE_ID"`.

## Script Macros

| Macro | Command |
|-------|---------|
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile "$COMPOSE_PROFILE"` |
| `$RESOLVE_DOMAIN` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-domain --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile "$COMPOSE_PROFILE"` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/compose_doc_control.py"` |

`$COMPOSE_DOC_CONTROL` subcommands: `--help` · `init-doc` · `append-intent`.

## Execution Contract

### Step I1 — Load

1. `$RESOLVE_PLAN_ROLE` → Plan Scope Constraints (`### Role`, `### Role Fields`).
2. `$RESOLVE_DOMAIN` → `domain instance`.
3. `$FETCH_COMPOSE section-registry --cycle-id "$CYCLE_ID"` (JSON) → `section_order`, `document_preamble`, per-section `heading` / `intent` (else `desc`) / `intent_boundary`.
4. `$FETCH_COMPOSE outline-registry --cycle-id "$CYCLE_ID"` → `outline_order`, per-block `heading` / `intents` / `guidance` / `contract`, `document_preamble_addon`.
5. `$FETCH_COMPOSE section-kw-criteria --cycle-id "$CYCLE_ID"` → each `## {section_key}` block.
6. Read `$SCOPE_DOC_PATH` full text once (shared across I2).
7. **Init document:** Substitute placeholders in `document_preamble`; append `document_preamble_addon`. Write via:

```bash
$COMPOSE_DOC_CONTROL init-doc \
  --path "$OUTPUT_DOC_PATH" \
  --preamble "<substituted document_preamble markdown>" \
  --preamble-addon "<document_preamble_addon markdown>"
```

Prefer `--preamble-file` / `--preamble-addon-file` when content is multiline.

Do **not** fetch spec-template URLs.

### Step I2 — Compose (per `section_key`, strict I2a → I2f)

For each key in `section_order`:

#### I2a — Filter `I*`

- **Input:** scope doc full text · `sections.{key}.intent` (else `desc`) · `intent_boundary` · kw `## {key}`
- **Action:** Include only if content matches `intent` and supports at least one KW dimension (semantic; do not label KW numbers). Exclude intents that belong to other sections' `intent` / `intent_boundary`.
- **Output `I*`:** filtered decision content for this section (may be empty)

#### I2b — Derive `F`

- **Input:** `### Role Fields` · domain instance · `intent` · outline `guidance` for the block containing this intent
- **Derive (three-step narrowing; priority on conflict: outline guidance > domain > role > intent):**
  1. **L1 — domain → lawful form space:** Read `expression_conventions` from the domain instance; establish what forms are idiomatic and legitimate in this domain. Forms outside this space are unconditionally excluded.
  2. **L2 — role × domain → preferred subset:** Read `expressive_tendency` from `### Role Fields` and `information_nature` from the domain instance; within the lawful space, narrow to forms that match both the role's expressive preference and the domain's characteristic information types.
  3. **L3 — intent + outline → concrete selection:** Read `intent` to determine this section's specific information nature; from the preferred subset, select the carrier and structure that best serve it. Apply outline `guidance` when present. Extract exclusion from `intent_boundary` — clauses go to `F.forbidden`. When `intent` names optional blocks (e.g. Interface Contract, Existing Assets, Task Detail with steps), select carriers that include them when `I*` supports it.
- **Output (required):**

```text
F.carrier:   <derived from L1 → L2 → L3>
F.structure: <derived from L1 → L2 → L3; "none" if no diagram>
F.forbidden: <derived from intent_boundary + forms eliminated in L1/L2>
```

#### I2c — Derive `C`

- **Input:** `### Role Fields` · domain instance · `intent` · outline `contract` · `F` from I2b
- **Derive (four steps):**
  1. **Role Fields → candidate constraints:** Read each Role Field; map to writing dimensions — `vocabulary_domain` → vocabulary, `cognitive_framework` → abstraction level, `priority_tendency` → emphasis and granularity, `completion_bar` → completeness criterion.
  2. **domain + intent → filter:** Add `expression_conventions` as baseline constraints; drop Role-derived clauses that conflict with this section's nature or target other section types.
  3. **F → concretize:** Cross remaining constraints with `F.carrier` and `F.structure`; concretize each dimension into carrier-specific criteria.
  4. **contract → structural constraints:** Read outline `contract.required` / `contract.forbidden` when present; add them as high-priority `C` constraints, overriding weaker clauses on conflict.
- **Output:** `C = {(d, c), …}` — 2–5 pairs; every `c` traceable to a specific Role Field, `intent`, outline `contract`, or `expression_conventions`.

#### I2d — Write body

- **Input:** `I*` · `F` · `C` · `intent` · `intent_boundary` · upstream section bodies already persisted in `$OUTPUT_DOC_PATH` (when de-duplicating)
- Scaffold per `F`; rewrite `I*` into slots; obey every `(d, c)` and `intent`.
- When high-priority `C` requires named blocks, ordering, step lists, tables, diagrams, or forbidden-form exclusions, realize them explicitly in body structure.
- **De-duplication:** Do not repeat the same boundary constraint across sections when `intent_boundary` defers elsewhere; upstream sections stay compact. Read upstream bodies from `$OUTPUT_DOC_PATH` via `compose_doc_schema.py --section-body` when needed.
- **Output:** `$SECTION_BODY` — section markdown body (no H2 line).

#### I2e — Derive display title

- **Input:** `sections.{key}.heading` · `$SECTION_BODY` · filtered `I*` substance (decision-level themes only)
- **Action:** Infer a short localized chapter title: use `heading` as type anchor; extract one domain theme from content substance; combine (~8–20 chars); distinguish sibling intents in the same outline block
- **Forbidden:** verbatim registry `heading`; file paths; API names; copying the first body sentence
- **Output:** `$DISPLAY_TITLE`; empty `$SECTION_BODY` → `（待补）`

#### I2f — Persist section

- **Input:** `$SECTION_BODY` · `$DISPLAY_TITLE` · `section_key` · outline-registry (loaded in I1)
- **Action:** Append to `$OUTPUT_DOC_PATH`:

```bash
$COMPOSE_DOC_CONTROL append-intent \
  --path "$OUTPUT_DOC_PATH" \
  --section "{section_key}" \
  --display-title "$DISPLAY_TITLE" \
  --body-file "<temp path with $SECTION_BODY>" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Script writes outline H2 (first intent in block), H3 anchor line, body, and block `---` per outline-registry. Fail on duplicate `section-key` anchor.

All sections remain draft until Round probe (when Round is wired).

## Return Summary

```text
Initializing complete.
  Profile: <COMPOSE_PROFILE>
  Output: <OUTPUT_DOC_PATH>
  Synthesized sections: <space-separated section keys from section_order>
  Scope SSOT: <SCOPE_DOC_PATH>
  Draft status: pending Round validation (all sections X until probe)
  Next step: RoundIteration, or parent pause gate (user may skip Round and Evaluate/Deliver)
```
