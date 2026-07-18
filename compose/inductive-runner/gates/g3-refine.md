> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 3 — Refine (dialogue flow)

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G3` (G2 closed).

**Goal:** refine section SoT toward Exit. This file orchestrates **when** each capability is used; **what** each capability is (means / tools / provenance) lives in `../references/g3-capabilities.md`; **how** it sounds to the user follows `../references/inductive-presentation.md`. **Do not** auto-sweep after Shape-confirm — wait for the user.

**Setup:** breadth = `section-registry.section_order` (init lens set); depth = per-section `frontier_kw` (the ruler). Mutations via `$INDUCTIVE_G3_SECTION_CTL` only after `activate-section`.

**Norm precondition:** if `$NORM_CONSTRAINT_REFS` non-empty, hold as generation boundary (not a gate). Empty → inert.

G3 runs as two lanes: **Lane A** is the free hub the session sits in; **Lane B** is a per-open channel entered on demand and returned from.

## Lane A — Discovery hub (the free state the session sits in)

The default state. The user senses and discovers freely; any surfaced open hands off to Lane B.

- **Sense** (baseline; global — available anytime after Seed; may produce no open):
  - free-dialogue sensing — discuss / look around; no script.
  - **View** (ref Class 3) — perception on user intent; contract in ref.
- **Discover** (produces `open` → Lane B) — ref Class 1:
  - **Class 1A — user-triggered** (collision / direct / view-derived, ref): **global — available anytime after Seed** (also in G1), not G3-only.
  - **Class 1B — AI detect**: **G3-scoped**; **only when the user asks** (never automatic). **I5 first:** subtract Settled before detecting. Dispatch `g3-shallow-grounding-runner` via `$SUBAGENT_TOOL` (mandatory) → `grounding-check` must pass before leaning; never inline-read source. Parent owns `add-open`. Present the batch as problem + leaning for Lane B.
- **Sense convergence → exit:** run `$INDUCTIVE_G3_SECTION_CTL check-coverage`; when Exit holds → `$INDUCTIVE_GATE_CTL gate-close --gate G3`. This is Lane A's exit action. Do **not** enter G4 until the user asks for delivery audit.

## Lane B — Open-processing channel (per open)

Entered when the user chooses to process — a single open or a batch. Opens may accumulate in Lane A and sit unprocessed while sensing / discovery continues; entry is user-authorized, not forced by an open's mere existence. Consumes `open` → settle or defer per **Class 2** (ref) — do not restate the per-mode path here.

1. User picks **auto / manual / ignore** after seeing problem + leaning (I6 informed authorization).
2. Run the chosen Class 2 mode; for `auto`/`manual`, dispatch `g3-deep-grounding-runner` via `$SUBAGENT_TOOL` (mandatory) and fetch receipt before leaning (`ignore` skips). One git commit per settle / defer (I8).
3. After settles that change facts for a lens: re-judge KW → `set-frontier` (only then).
4. Return to Lane A — user may sense / confirm / request the next discovery.

**Lazy consistency (I8):** after `update-decision` on id=X, single-hop re-read `hangs_under==X` opens; conflict → `add-open`.

## Maturity

Gates Lane A's Exit check (`check-coverage` requires every **init** lens cleared∨skipped):

- `clear-section` when frontier ≥ target and no blocking open.
- `skip-section` / `rewind-section` as needed via section-control.
