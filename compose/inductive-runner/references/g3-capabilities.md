> Part of inductive-runner · capability reference · indexed from `../SKILL.md` and `../gates/g3-refine.md`

# G3 Capabilities

Function-view catalog of G3 capabilities. **This file is the capability SSOT.** Orchestration — *when* each capability is invoked, and the global-vs-flow availability attribute — lives in `../gates/g3-refine.md`, not here. Keeping the two apart lets the capability set and the dialogue flow iterate independently.

**Provenance vocabulary (two layers):**
- **Opens** (`inductive-opens.json`): `trigger ∈ {human, ai}` × `means ∈ {probe, direct, view, ai_scan, intent_baseline}`. Every open carries a human/ai stamp.
- **Seed facts** (`_facts.json`): `origin.type=seed` with hybrid `origin.ref` (scope path + excerpt) — **not** an open `trigger=seed` stamp. Seed bypasses opens.

Stamps are **always** recorded even when hidden from the user's wording — they feed G5 provenance and I10 inheritance.

---

## Class 1 — Discover open points

Produces opens in `inductive-opens.json`. Two triggers with **different natures**: 1A is recognition/intake (AI recognizes a user-surfaced gap and docks it to processing); 1B is active execution (AI runs the method).

**Dedup identity** = `(detected_under|null, KW row, topic)`; on collision, `update-open` to attach provenance — never duplicate. `trigger=human` is altitude-exempt; `trigger=ai` applies `frontier_kw`.

### 1A — User-triggered (recognize & dock)

Not a prescriptive menu — an **awareness map** so the AI recognizes "an open point has arrived" via any of these paths and routes it to Class 2. Lands via `add-open --trigger human`.

| Path | means | Nature |
|------|-------|--------|
| Collision | `probe` | gap surfaced while the user questions / challenges |
| Direct | `direct` | user directly asserts a gap |
| View-derived | `view` | user notices a gap while viewing — one possible situation, **not** required to happen inside View |

**Collision contract:** AI may infer, but **must** label ✅ Verified (with anchor) / ⚠️ Inferred / say unknown; multiple readings OK; **never** decides for the user. Do **not** fold inference into View (violates V2).

### 1B — AI-triggered (active methods)

AI actively executes; lands via `add-open --trigger ai` after the parent forms a leaning.

| Method | means | Evidence |
|--------|-------|----------|
| Code scan | `ai_scan` | code via `SCAN_CRITERIA` |
| Intent baseline | `intent_baseline` | demand manifest via `intent_coverage` |
| AI collision | `probe` | 4 lenses: failure / boundary / assumption / seam |

AI probe rule: silence ∧ KW-false → gap; no correctness judging (that is G4).

**Tool — `g3-shallow-grounding-runner`** (mandatory for 1B): read-only evidence pass feeding 1B. Writes receipts to `grounding-notes.json`; **never** `add-open` — the parent owns open creation.

---

## Class 2 — Process open points

Consumes `open` → facts via `settle-open` (1:N) or `deferred`/`rejected`. The user picks the mode after seeing problem + leaning (I6 informed authorization).

| Mode | Behavior |
|------|----------|
| `auto` | deep-grounding (mandatory) → `attach-code-refs` → `settle-open --facts-file …`, continuous (no per-point pause) |
| `manual` | same path, pausing per point for the user to discuss / adjust before `settle-open` |
| `ignore` | `defer-open` (park; no deep-grounding) |

**Tools:**
- `g3-deep-grounding-runner` (mandatory for `auto`/`manual` before leaning): read-only evidence for **one** chosen open; may carry `file:line` / signatures. Never forms the leaning — the parent does.
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

**Dual role:** View also serves as the *tool* for Class 1A `view`-derived discovery — when a gap is noticed while viewing, it is recorded as a discovery (`human·view`), which is a Class 1 act, not part of View itself. The two are distinguished by whether an `open` is produced: Class 3 does not; Class 1A does.
