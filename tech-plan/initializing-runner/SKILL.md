---
name: initializing-runner
description: >-
  Autonomous Initializing step for tech-plan drafting. Loads decision-doc and
  frameworks, composes per-section tech-doc body via I* / F / C, then writes
  the initial draft and returns control to the parent Initializing step.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside `tech-plan` Drafting.

## Scope

Steps I1–I4 only:

1. Load decision-doc, section-registry (with `desc`), section-kw-criteria, and Plan Scope Constraints.
2. Compose each section body: Filter `I*` → Derive `F` → Derive `C` → Write body (see Theory).
3. Optionally write R0 rows to anchor-ledger.
4. Write `$TECH_DOC_PATH`.

Do not ask the user questions. Do not run InDialogue, Reopen, Evaluating, or delivery work.

## Theory (Compose)

See [`../references/compose-theory.md`](../references/compose-theory.md).

**Order (strict):** I2a Filter `I*` → I2b Derive `F` → I2c Derive `C` → I2d Write body.

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` |
| `$DECISION_DOC_PATH` | Absolute path to decision-doc |
| `$CYCLE_TYPE` | `topic` or `feature` |
| `$CYCLE_ID` | Active cycle id |

Self-resolved: `$TECH_DOC_PATH` = `{REVISION_DIR}/tech-doc.md`

Load frameworks via `$FETCH_TECH_PLAN` and role via `$RESOLVE_PLAN_ROLE` (see `../SKILL.md` → Script Macros).

## Execution Contract

### Step I1 — Load

1. Run `$RESOLVE_PLAN_ROLE` with `$CYCLE_ID`; read stdout as Plan Scope Constraints; keep `### Role` and `### Role Fields`.
2. Run `$RESOLVE_DOMAIN`; read stdout; keep as `domain instance`.
3. Run `$FETCH_TECH_PLAN section-registry`; parse JSON. Cache `section_order`, `document_preamble`, `sections.{key}.heading`, `sections.{key}.desc`.
4. Run `$FETCH_TECH_PLAN section-kw-criteria`; cache each `## {section_key}` block.
5. Read `$DECISION_DOC_PATH` **full text** once; keep in memory for all sections.
6. Initialize `fill_results` from `section_order`: each entry has `heading_line`, empty `content`, `status: "X"`, internal `draft: true`.

Do **not** fetch `decision-doc-mapping`.

```text
fill_results[section_key] = {
  heading_line: "## {heading} <!-- section-key:{section_key} -->",
  content: "",
  status: "X"
}
```

`heading` = registry `sections.{key}.heading`.

### Step I2 — Compose (per `section_key`, strict I2a → I2d)

For each key in `section_order`:

#### I2a — Filter `I*`

- **Input:** decision full text · `sections.{key}.desc` · kw `## {key}`
- Include an intent sentence in `I*` only if it matches `desc` and supports at least one KW dimension (semantic; do not label KW numbers).
- Exclude intents that belong to other sections' `desc`. Rewrite as tech-neutral sentences; not decision verbatim.
- **Output:** list `I*` (may be empty).

#### I2b — Derive `F`

- **Input:** `### Role Fields` · domain instance · `desc`
- **Derive (three-step narrowing; priority on conflict: desc > domain > role):**
  1. **L1 — domain → lawful form space:** Read `expression_conventions` from the domain instance; establish what forms are idiomatic and legitimate in this domain. Forms outside this space are unconditionally excluded.
  2. **L2 — role × domain → preferred subset:** Read `expressive_tendency` from `### Role Fields` and `information_nature` from the domain instance; within the lawful space, narrow to forms that match both the role's expressive preference and the domain's characteristic information types.
  3. **L3 — desc → concrete selection:** Read `desc` to determine this section's specific information nature; from the preferred subset, select the carrier and structure that best serve it. Extract any explicit exclusion clauses ("No …") from `desc` — these go directly to `F.forbidden`.
- **Output (required):**

```text
F.carrier:   <derived from L1 → L2 → L3>
F.structure: <derived from L1 → L2 → L3; "none" if no diagram>
F.forbidden: <derived from desc exclusion clauses + forms eliminated in L1/L2>
```

#### I2c — Derive `C`

- **Input:** `### Role Fields` · domain instance · `desc` · `F` from I2b
- **Derive (three steps):**
  1. **Role Fields → candidate constraints:** Read each Role Field; map to writing dimensions — `vocabulary_domain` → vocabulary, `cognitive_framework` → abstraction level, `priority_tendency` → emphasis and granularity, `completion_bar` → completeness criterion.
  2. **domain + desc → filter:** Add `expression_conventions` as baseline constraints; drop Role-derived clauses that conflict with this section's nature or target other section types.
  3. **F → adjust:** Cross remaining constraints with `F.carrier` and `F.structure`; adjust any dimension whose criterion depends on the carrier form.
- **Output:** `C = {(d, c), …}` — 2–5 pairs; every `c` traceable to a specific Role Field, `desc`, or `expression_conventions`.

#### I2d — Write body

- **Input:** `I*` · `F` · `C` · `desc`
- Scaffold per `F`; rewrite `I*` into slots; obey every `(d, c)` and `desc`.
- Set `fill_results[section_key].content` to the section markdown body (no H2 line).
- Keep `status: "X"`.

### Step I3 — Ancillary (optional)

- R0-grade User Prior / Known Constraints → `anchor-ledger.md` (`Committed at Round = 0`). Do not stack `[Anchored]` in body.

### Step I4 — Write tech-doc

1. Write `$TECH_DOC_PATH`: `document_preamble` (substitute placeholders) then each section in `section_order` (`heading_line` + `content`).
2. All sections remain draft (`X`) until Round probe.

## Return Summary

```text
Initializing complete.
  Synthesized sections: <space-separated section keys from section_order>
  Decision SSOT: <DECISION_DOC_PATH>
  Draft status: pending Round validation (all sections X until probe)
  Next step: RoundIteration (Step 2)
```
