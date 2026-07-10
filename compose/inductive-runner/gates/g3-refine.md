> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 3 — Refine (advance actions ③④⑤)

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G3` (G2 closed).

**Goal:** refine section SoT via **advance** capabilities (design §7 ③④⑤). **Do not** auto-sweep after Shape-confirm — wait for the user.

**Global observation (① view / ② 碰撞)** lives in the parent SKILL — available **anytime after Seed**, including during G3. This gate file does **not** own them (I13). When the user asks for a view or collision mid-refine, follow the parent contracts, then return here for ③④⑤.

**Setup:** breadth = `SCAN_CRITERIA.expose_axis.coverage_sections`; depth = per-section `frontier_kw`. Discovery sources (trigger × means): human `probe|direct|view`; ai `ai_scan|intent_baseline|probe`. KW is the ruler. Mutations via `$INDUCTIVE_G3_SECTION_CTL` only after `activate-section`.

**Norm precondition:** if `$NORM_CONSTRAINT_REFS` non-empty, hold as generation boundary (not a gate). Empty → inert.

## ③ Detect (only when asked)

**I5 first:** subtract Settled — do not re-open claims already in `decisions[]` (or already confirmed in the shape checkpoint) unless the user reopens them.

For unsettled sections at `frontier_kw`:

1. **ai_scan** — run applicable `SCAN_CRITERIA` methods over code; qualify with KW.
2. **intent_baseline** — `intent_coverage` vs demand manifest when present (mount-or-create with `intent_ref`).
3. **ai/probe** — black-box 4 lenses (failure / boundary / assumption / seam) at current `frontier_kw`; silence ∧ KW-false → gap; question form + ✅/⚠️; **no** correctness judging (G4).

Each hit → `add-open --trigger ai --means <ai_scan|intent_baseline|probe> …`. Dedup by (section, KW row, topic): if an open already exists, `update-open` to attach provenance — do not duplicate. Present a **batch** (problem + leaning) for user selection.

Optional: dispatch `g3-shallow-grounding-runner` / `g3-deep-grounding-runner` for code facts only — they must **not** call `add-open`; parent does. Prefer `attach-code-refs` on the open/decision being processed.

## ④ Process batch

User picks **auto** / **manual** / **ignore** after seeing problem+leaning (I6 informed authorization):

| Mode | Runner behavior | Scripts |
|------|-----------------|---------|
| auto | User authorized continuous settle for this batch | `attach-code-refs` → `settle-open` |
| manual | Pause per point for user adjust | same + wait |
| ignore | Skip / park | `defer-open --note …` |

- `settle-open --text …` inherits `trigger` / `means` / `intent_ref` (I10).
- One git commit per settle/defer (I8).
- After settles that change `decisions`: AI re-judges KW → `set-frontier` (only then).
- Then user may ①/② (parent) to confirm; request next ③ batch.

**Lazy consistency:** if `update-decision` on id=X, single-hop re-read `hangs_under==X` opens; conflict → `add-open`.

## ⑤ User-proposed open

`add-open --trigger human --means direct …` (or `--means view` if the gap was found while viewing) → **immediately** ④ (no detect batch required).

## Maturity & clear

- `clear-section` when frontier ≥ target and no blocking open (reads section JSON).
- `skip-section` / `rewind-section` as needed via section-control.

## Close G3

When Exit holds: `$INDUCTIVE_G3_SECTION_CTL check-coverage` ok → `$INDUCTIVE_GATE_CTL gate-close --gate G3`.  
Do **not** enter G4 until the user asks for delivery audit.
