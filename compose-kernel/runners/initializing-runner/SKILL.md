---
name: initializing-runner
description: >-
  Autonomous Initializing step for compose-profile drafting. Loads decision-doc,
  narrow codebase context, and frameworks; composes per-section body via I* / F
  / C; writes the initial draft and returns control to the parent Initializing
  step.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside a parent compose stage Drafting shell.

Use `$COMPOSE_PROFILE` from parent dispatch; kernel default applies only when omitted.

## Scope

Steps I1–I4 only:

1. Load decision-doc, narrow codebase context, section-registry (with `intent`), outline-registry when `$CYCLE_TYPE` is `feature`, section-kw-criteria, and Plan Scope Constraints.
2. Compose each section body: Filter `I*` → Derive `F` → Derive `C` → Write body (see Theory).
3. Optionally write R0 rows to anchor-ledger.
4. Write `$OUTPUT_DOC_PATH` (or `{REVISION_DIR}/tech-doc.md` when `OUTPUT_DOC_PATH` is absent).

Do not ask the user questions. Do not run InDialogue, Reopen, Evaluating, or delivery work.

## Theory (Compose)

See [`../../references/compose-theory.md`](../../references/compose-theory.md).

**Order (strict):** I2a Filter `I*` → I2b Derive `F` → I2c Derive `C` → I2d Write body.

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` |
| `$DECISION_DOC_PATH` | Absolute path to decision-doc |
| `$OUTPUT_DOC_PATH` | Absolute path to output document (design-doc.md or tech-doc.md) |
| `$COMPOSE_PROFILE` | Compose profile id from parent dispatch |
| `$DESIGN_DOC_PATH` | Optional supplementary design context when parent provides it (decision-doc remains SSOT) |
| `$CYCLE_TYPE` | `feature` |
| `$CYCLE_ID` | Active cycle id |

Self-resolved: `$PROJECT_ROOT` = `$(pwd)` · `$OUTPUT_DOC_PATH` from parent input (fallback `{REVISION_DIR}/tech-doc.md`)

All compose and scope macros (`$FETCH_COMPOSE`, `$RESOLVE_PLAN_ROLE`, `$RESOLVE_DOMAIN`) **must** pass `--profile "$COMPOSE_PROFILE"`.

## Script Macros

| Macro | Command |
|-------|---------|
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile "$COMPOSE_PROFILE"` |
| `$RESOLVE_DOMAIN` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-domain --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile "$COMPOSE_PROFILE"` |

## Execution Contract

### Step I1 — Load

1. Run `$RESOLVE_PLAN_ROLE` with `$CYCLE_ID` and `--profile $COMPOSE_PROFILE`; read stdout as Plan Scope Constraints; keep `### Role` and `### Role Fields`.
2. Run `$RESOLVE_DOMAIN` with `$CYCLE_ID` and `--profile $COMPOSE_PROFILE`; read stdout; keep as `domain instance`.
3. Run `$FETCH_COMPOSE section-registry --profile $COMPOSE_PROFILE`; parse JSON. Cache `section_order`, `document_preamble`, `sections.{key}.heading`, `sections.{key}.intent` (fallback `desc`), `sections.{key}.intent_boundary`.
4. Run `$FETCH_COMPOSE outline-registry --profile $COMPOSE_PROFILE`; cache `outline_order`, `blocks.{key}.heading`, `blocks.{key}.intents`, `blocks.{key}.reader_note`, `document_preamble_addon`.
5. Run `$FETCH_COMPOSE section-kw-criteria --profile $COMPOSE_PROFILE`; cache each `## {section_key}` block.
6. Read `$DECISION_DOC_PATH` **full text** once; keep in memory for all sections.
7. When `$DESIGN_DOC_PATH` is provided, read it **full text** once as supplementary context (decision-doc remains scope SSOT).
8. Initialize `fill_results` from `section_order`: each entry has `content`, `status: "X"`, internal `draft: true`.
9. **Codebase read scope** — parse from decision Impact Surface, Implementation Sketch, and explicit reference implementations (paths, modules, or globs). Do not scan the whole repo.
10. **Codebase context** — read only scoped files under `$PROJECT_ROOT`; keep structural facts (paths, entry points, dialog patterns, vendor layout, public symbols). Skip when scope is empty.
11. When `$CYCLE_TYPE` is `feature` and codebase context is non-empty, note reference paths for I3 anchor-ledger R0 (`Ref: {path}`).

Do **not** fetch `decision-doc-mapping` or spec-template URLs.

```text
fill_results[section_key] = {
  content: "",
  status: "X"
}
```
### Step I2 — Compose (per `section_key`, strict I2a → I2d)

For each key in `section_order`:

#### I2a — Filter `I*`

- **Input:** decision full text · `sections.{key}.intent` (else `desc`) · `intent_boundary` · kw `## {key}` · outline `blocks.*.reader_note` when intent maps to that block · codebase context (when allowed)
- **I*_scope:** Include only if intent matches `intent` and supports at least one KW dimension (semantic; do not label KW numbers). Rewrite as tech-neutral sentences; not decision verbatim.
- **I*_impl:** When `$CYCLE_TYPE` is `feature` — **tech-plan:** `CTX`, `AR`, `SK`, `T`, or `VF`; **tech-design:** `CTX`, `ST`, or `IF` only — add paths, APIs, or patterns from codebase context only when decision already points at that surface. For `CTX`, use only in existing-assets context. Never add capabilities beyond decision-doc.
- Exclude intents that belong to other sections' `intent` / `intent_boundary`.
- **Output:** `I* = I*_scope ∪ I*_impl` (either may be empty).

#### I2b — Derive `F`

- **Input:** `### Role Fields` · domain instance · `intent` · outline `reader_note` for the block containing this intent (feature)
- **Derive (three-step narrowing; priority on conflict: outline reader_note > domain > role > intent):**
  1. **L1 — domain → lawful form space:** Read `expression_conventions` from the domain instance; establish what forms are idiomatic and legitimate in this domain. Forms outside this space are unconditionally excluded.
  2. **L2 — role × domain → preferred subset:** Read `expressive_tendency` from `### Role Fields` and `information_nature` from the domain instance; within the lawful space, narrow to forms that match both the role's expressive preference and the domain's characteristic information types.
  3. **L3 — intent + outline → concrete selection:** Read `intent` to determine this section's specific information nature; from the preferred subset, select the carrier and structure that best serve it. Apply outline `reader_note` when present (feature). Extract exclusion from `intent_boundary` — clauses go to `F.forbidden`. When `intent` names optional blocks (e.g. Interface Contract, Existing Assets, Task Detail with steps), select carriers that include them when `I*` supports it.
- **Output (required):**

```text
F.carrier:   <derived from L1 → L2 → L3>
F.structure: <derived from L1 → L2 → L3; "none" if no diagram>
F.forbidden: <derived from intent_boundary + forms eliminated in L1/L2>
```

#### I2c — Derive `C`

- **Input:** `### Role Fields` · domain instance · `intent` · outline `reader_note` · `F` from I2b
- **Derive (three steps):**
  1. **Role Fields → candidate constraints:** Read each Role Field; map to writing dimensions — `vocabulary_domain` → vocabulary, `cognitive_framework` → abstraction level, `priority_tendency` → emphasis and granularity, `completion_bar` → completeness criterion.
  2. **domain + intent → filter:** Add `expression_conventions` as baseline constraints; drop Role-derived clauses that conflict with this section's nature or target other section types.
  3. **F → adjust:** Cross remaining constraints with `F.carrier` and `F.structure`; adjust any dimension whose criterion depends on the carrier form.
- **Feature momentum (tech-plan only, when `$COMPOSE_PROFILE` is `tech-plan`):** For `SK`, include an execution-arc lead-in and phase Done clarity. For `T`, include checkbox steps (`- [ ]`) at 2–5 minute granularity and Create/Modify/Test paths from `I*_impl` when present.
- **Design register (tech-design only, when `$COMPOSE_PROFILE` is `tech-design`):** Forbidden in body: task decomposition, checkbox steps, file-level change lists, `Run:` commands, SK/T/VF, phase Done markers, metric thresholds, runbook steps, Owner/Timing tables.
- **Output:** `C = {(d, c), …}` — 2–5 pairs; every `c` traceable to a specific Role Field, `intent`, outline `reader_note`, or `expression_conventions`.

#### I2d — Write body

- **Input:** `I*` · `F` · `C` · `intent` · `intent_boundary`
- Scaffold per `F`; rewrite `I*` into slots; obey every `(d, c)` and `intent`.
- **De-duplication:** Do not repeat the same boundary constraint across sections when `intent_boundary` defers elsewhere; upstream sections stay compact.
- **Feature (tech-plan):** `SK` — lead with **Execution arc** before the phase table. `T` — include Task Index, Change Overview, and at least one `[C] Task Detail` with a **Steps** checkbox list when `I*_impl` or decision paths exist. `AR` — include `[E] Interface Contract` when `intent` and `I*` support module boundaries.
- **Feature (tech-design):** `ST` — structure or flow diagram when it clarifies systemic placement. `IF` — interface/event/schema table when cross-boundary contracts are in `I*`. `KD` — option/chosen/rejected table when alternatives exist in decision.
- Set `fill_results[section_key].content` to the section markdown body (no H2 line).
- Keep `status: "X"`.

### Step I3 — Ancillary (optional)

- R0-grade User Prior / Known Constraints → `anchor-ledger.md` (`Committed at Round = 0`). Include codebase reference paths from I1 when used. Do not stack `[Anchored]` in body.

### Step I4 — Write document

1. **Preamble:** `document_preamble` with placeholders substituted. When `$CYCLE_TYPE` is `feature`, append `document_preamble_addon` from outline-registry after substitution.
2. **Feature assembly (`$CYCLE_TYPE` is `feature`):** For each key in `outline_order`, write `## {blocks.{key}.heading}` then for each intent in `blocks.{key}.intents` write `<!-- section-key:{intent} -->` on its own line followed by `fill_results[intent].content`. Separate outline blocks with `---` when not the last block.
3. **Topic assembly:** For each key in `section_order`, write `heading_line` + `fill_results[section_key].content`.
4. Write the assembled document to `$OUTPUT_DOC_PATH`.
5. All sections remain draft (`X`) until Round probe (when Round is wired).

## Return Summary

```text
Initializing complete.
  Profile: <COMPOSE_PROFILE>
  Output: <OUTPUT_DOC_PATH>
  Synthesized sections: <space-separated section keys from section_order>
  Decision SSOT: <DECISION_DOC_PATH>
  Codebase scope: <paths read, or "none">
  Draft status: pending Round validation (all sections X until probe)
  Next step: RoundIteration, or parent pause gate (user may skip Round and Evaluate/Deliver)
```
