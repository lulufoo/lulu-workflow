> Part of inductive-runner · capability reference · indexed from `../SKILL.md` and `../gates/g3-refine.md`

# G3 Capabilities

Function-view catalog of G3 capabilities. **This file is the capability SSOT.** Orchestration — *when* each capability is invoked, and the global-vs-flow availability attribute — lives in `../gates/g3-refine.md`, not here. Keeping the two apart lets the capability set and the dialogue flow iterate independently.

**Provenance vocabulary (two layers):**
- **Opens** (`inductive-opens.json`): `trigger ∈ {human, ai}` × `means ∈ {human_probe, ai_probe, human_direct, human_view, ai_scan, ai_intent_baseline, ai_scope_scan}`. Means names are self-describing (`human_*` / `ai_*`); phase 1 keeps `trigger` and validates prefix ↔ trigger. Legacy means migrate on load/save.
- **Seed facts** (`_facts.json`): `origin.type=seed` with hybrid `origin.ref` (scope path + excerpt / unit id) — **not** an open `trigger=seed` stamp. Seed bypasses opens.

Stamps are **always** recorded even when hidden from the user's wording — they feed G5 provenance and I10 inheritance.

---

## Class 1 — Discover open points

Produces opens in `inductive-opens.json`. Two triggers with **different natures**: 1A is recognition/intake (AI recognizes a user-surfaced gap and docks it to processing); 1B is active execution (AI runs the method).

**Open identity:** active opens are not keyed by facet. `trigger=human` is altitude-exempt; `trigger=ai` applies `frontier_kw`.

**Facet seeds (1B):** when section-registry declares `facets: string[]` on the active lens, paste those short labels into the detect prompt as **non-exhaustive seeds** (friction with demand + Context may open list-external gaps). Seeds are not a closed question set and do **not** create `facet_id` or clear receipts.

### 1A — User-triggered (recognize & dock)

Not a prescriptive menu — an **awareness map** so the AI recognizes "an open point has arrived" via any of these paths and routes it to Class 2. Lands via `add-open --trigger human`.

| Path | means | Nature |
|------|-------|--------|
| Collision | `human_probe` | gap surfaced while the user questions / challenges |
| Direct | `human_direct` | user directly asserts a gap |
| View-derived | `human_view` | user notices a gap while viewing — one possible situation, **not** required to happen inside View |

**Collision contract:** AI may infer, but **must** label ✅ Verified (with anchor) / ⚠️ Inferred / say unknown; multiple readings OK; **never** decides for the user. Do **not** fold inference into View (violates V2).

### 1B — AI-triggered (active methods)

AI actively executes; lands via `add-open --trigger ai` after the parent forms a leaning.

| Method | means | Evidence |
|--------|-------|----------|
| Code scan | `ai_scan` | code via `SCAN_CRITERIA` |
| Intent baseline | `ai_intent_baseline` | demand manifest via `intent_coverage` (role A) |
| Scope / decision-fact scan | `ai_scope_scan` | `$SCOPE_REF` units (when decision-fact.json) via design lenses; mount-or-create with `intent_ref=<unit-id>` (role B; **not** A safety-net) |
| AI collision | `ai_probe` | 4 lenses: failure / boundary / assumption / seam |

AI probe rule: silence ∧ KW-false → gap; no correctness judging (that is G4).

**`ai_scope_scan` contract:** authorized Class 1B only (never automatic — I6). Subtract Settled facts first (I5). Reuse mount-or-create + `intent_ref` shape from `intent_coverage`; do **not** call `is_generation_guaranteed` for this means. Unclaimed units remain on the claim ledger.

**Tool — `g3-shallow-grounding-runner`** (optional): read-only evidence pass feeding 1B. Writes receipts to `grounding-notes.json`; **never** `add-open` — the parent owns open creation. For `ai_scope_scan`, evidence is the decision-fact unit list (not code shallow-grounding).

---

## Class 2 — Process open points

Consumes `open` → facts via `settle-open` (1:N) or `deferred`/`rejected`. The user picks the mode after seeing problem + leaning (I6 informed authorization).

| Mode | Behavior |
|------|----------|
| `auto` | (optional `deep-grounding`) → `attach-code-refs` → `settle-open --facts-file …`, continuous (no per-point pause) |
| `manual` | **Manual turn** per open (below) |
| `ignore` | `defer-open` (park) |

**Manual turn** (Class 2 only — not detect Output):
1. Lock one open.
2. **Optional** `g3-deep-grounding-runner` once before options — AI decides; no hard trigger. Parent: `deep-grounding-list`. No second deep after act.
3. **Plain block** — `/plain` obligations (mention `/plain`; do **not** dispatch `plain` skill): lead with conclusion; zero-context; fixed wording; keep key proper nouns (gloss once). Cover stuck / why / blocking. No standalone `/plain` confirmation closer.
4. **Options (2–5)** — `/plain` wording; keep proper nouns. Command names are orchestration maps only, not option titles.
5. **Objective leaning** — recommended option + one-line why; do not select for the user.
6. **Wait / legal replies:** refine option · new idea (rewrite) · discuss-then-decide (no settle) · **skip** (leave `open`, next Manual turn; ≠ Ignore) · **Ignore** (`defer-open`) · settle when ready.
7. **Legal exit** (anytime): stop/abandon Manual · return to open-point detect · switch to **Auto**. No prescription after exit.
8. **Act** — settle tools / `defer-open` / skip-to-next / leave as chosen.

**Manual turn MUST NOT:** batch opens in one ask; second deep after act; deep agent user-facing or settling; dispatch `plain` skill; treat skip as Ignore.

**Tools:**
- `g3-deep-grounding-runner` (optional): read-only evidence for **one** chosen open; may carry `file:line` / signatures. Never forms the leaning — the parent does.
- `attach-code-refs`: fix code anchors onto an **open** (`O-` only; facts have no `code_refs` field).
- `settle-open`: commit `open` → 1:N facts (`origin.type=discovered`, `ref=[O-n]`); `code_refs` stay on the open; `resolved_by` lists new `F-` ids. One git commit (I8).
- `defer-open`: park open (`status=deferred` + `note`; keeps `intent_ref`; does **not** copy stamps onto facts). One git commit (I8).
- `reject-open`: true out-of-domain exit (`status=rejected` + `--reason`).

---

## Class 3 — View (perception tool)

Read-only fidelity projection of current SoT, driven by user intent. **Produces no `open`, performs no inference.** View contract:

- **V1** source = facts + opens + maturity SoT only
- **V2** no invention; gaps stay gaps
- **V3** shape-free
- **V4** non-authoritative
- **V5** `synthesis:off` = compose-init mechanical assembly of fact text by lens

View ≠ 碰撞 (I13).

View is **one tool** for perception, not perception itself. The ambient baseline is free-dialogue sensing (no script); it is described by the flow layer (`../gates/g3-refine.md`), not catalogued here — it has no capability of its own.

**Dual role:** View also serves as the *tool* for Class 1A `human_view`-derived discovery — when a gap is noticed while viewing, it is recorded as a discovery (`human` × `human_view`), which is a Class 1 act, not part of View itself. The two are distinguished by whether an `open` is produced: Class 3 does not; Class 1A does.
