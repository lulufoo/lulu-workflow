> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 3 — Gap-check (dialogue flow; archive-10.0)

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G3` (G2 Topic Loop closed).

**Goal (archive-10.0):** **gap-check / 查漏** after Topic Loop — orphans vs collab arc, blocking opens, shape drift. Prefer returning to G2 for full topic discussion rather than resurrecting section dual-lane as the main hub. **Fact writes share the T2 human-confirm gate:** conclusion→facts via `$FACT_SETTLE_CTL commit --confirm`; open settlement via `$INDUCTIVE_G3_SECTION_CTL settle-open … --confirm` (also returns `stale_signal`). No silent fact writes. Existing Class 1/2 tools remain available for processing opens. **Do not** auto-sweep after Shape-confirm — wait for the user.

Legacy refine lanes below still describe tool availability; default user-facing posture is gap-check checklist, not section patrol.

**Setup:** breadth = `section-registry.section_order` (init lens set); depth = per-section `frontier_kw` (the ruler). Mutations via `$INDUCTIVE_G3_SECTION_CTL` only after `activate-section`.

**Norm precondition:** if `$NORM_CONSTRAINT_REFS` non-empty, hold as generation boundary (not a gate). Empty → inert.

G3 runs as two lanes: **Lane A** is the free hub the session sits in; **Lane B** is a per-open channel entered on demand and returned from.

Orchestration prose in this file is English. User-visible menus and landmarks are adapted only via the presentation ref (do not invent alternate labels here).

## Dialogue stops (MUST)

Readable next gate ≠ run it. **Before the first user-facing turn in G3, read** `../references/inductive-presentation.md` and render all menus with its L1 map.

| Stop | When | Do | Do not |
|------|------|----|--------|
| **E** | First G3 user turn | Offer: continue discussion · view extract · open-point detect · open-point process (if opens) · refine close (if Exit can hold) → selecting refine close enters **X** (no close yet) | Auto-detect |
| **D** | After Class 1B batch | Offer open-point process + **Auto / Manual / Ignore**; carry mode into Lane B | Default Auto; re-ask mode in Lane B |
| **P** | Back on Lane A after process | Short nav (E keys) | Auto-close G3; enter G4 |
| **X** | Close requested or Exit holds | Choose **before** any close: (1) continue refine — no close (2) close-only — `check-coverage` → `gate-close G3`, stop (3) pre-publish check — close → **A** | Offer produce-document; close before choose; run G4/G5/doc without (3) or a later **A** |
| **A** | User asks pre-publish / G4 / G5 | Announce G4→G5 (bundled), then enter G4 | Enter G4 unasked |

**Vague "keep going":** list options for the **current stop only** (presentation Stop→L1); never default to close + check + doc.

## Lane A — Discovery hub (the free state the session sits in)

The default state. The user senses and discovers freely; any surfaced open hands off to Lane B.

- **Sense** (baseline; global — available anytime after Seed; may produce no open):
  - free-dialogue sensing (continue discussion) — discuss / look around; no script.
  - **View** (ref Class 3 → view extract) — perception on user intent; contract in ref.
- **Discover** (produces `open` → Lane B) — ref Class 1:
  - **Class 1A — user-triggered** (collision / direct / view-derived, ref): **global — available anytime after Seed** (also in G1), not G3-only.
  - **Class 1B — AI detect** (open-point detect): **G3-scoped**; **only when the user asks** (never automatic). **I5 first:** subtract Settled before detecting. Methods: `ai_scan` / `ai_intent_baseline` / `ai_probe`. Read `$SCOPE_REF` as the same format-neutral source material Seed used (do not branch on JSON vs Markdown). For code/intent/probe paths: optionally dispatch `g3-shallow-grounding-runner` via `$SUBAGENT_TOOL` (ref); parent owns `add-open`. Present the batch as problem + leaning, then **Stop D**.
- **Sense convergence → exit:** when offering close, run **Stop X** (choose path before any `gate-close`). Do **not** enter G4 until Stop A.

## Lane B — Open-processing channel (per open)

Entered when the user chooses open-point process — a single open or a batch. Opens may accumulate in Lane A and sit unprocessed while sensing / discovery continues; entry is user-authorized, not forced by an open's mere existence. Consumes `open` → settle or defer per **Class 2** (ref) — do not restate the per-mode path here.

1. Mode (I6): use Stop D's **Auto / Manual / Ignore** if set; otherwise ask once here.
2. Run the chosen Class 2 mode (ref). **Auto:** optional deep on auto path. **Manual:** Manual turn per open (ref); honor skip / Ignore / legal exit. **Ignore:** `defer-open`. One git commit per settle / defer (I8).
3. After settles that change facts for a lens: re-judge KW → `set-frontier` (only then).
4. Return to Lane A — **Stop P**.

**Lazy consistency (I8):** after `update-decision` on id=X, single-hop re-read `hangs_under==X` opens; conflict → `add-open`.

## Maturity

Gates Lane A's Exit check (`check-coverage`: every **init** lens cleared∨skipped; no blocking∧open; demand manifest fulfilled∨deferred when present):

- `clear-section` when frontier ≥ target, no blocking open under the lens, and the lens has at least one fact with matching `lens_tags`. Optional registry `facets` string seeds are **prompt reminders only** (Class 1B); they do **not** gate clear.
- `skip-section` / `rewind-section` as needed via section-control.
