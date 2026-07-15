# Provenance Algorithm Semantics (Gate 5)

> Referenced by: `g5-provenance-runner` (Pipeline steps 5–6) and Gate 5 (`inductive-runner/gates/g5-provenance.md`). Distilled from the compose provenance mechanism design — carries the *why* behind the runner's bucket vocabulary and per-role posture; not a verbatim copy of the design doc.

## Two orthogonal axes

Every provenance edge (this stage's decisions vs. an upstream role) is checked on two axes:

- **Axis 1 — overreach/conflict** (downstream → upstream, scanned per section): did this stage say something it wasn't entitled to say?
- **Axis 2 — coverage/fulfillment** (upstream → downstream, scanned once over the whole document): did this stage miss an upstream item it was supposed to honor? Only roles with an enumerable, promise-like upstream get an axis 2 — `norm-constraint` does not, because a rule is never "fulfilled", only "not violated".

## Per-role default posture (why default-deny vs silence-is-ok)

| Role | Axis 1 posture | Why |
|---|---|---|
| **A — intent-baseline** | **Default-deny.** An unmatched product-visible addition is flagged, not assumed fine. | The upstream intent baseline is the product's own promise; this stage has no authority to silently extend product-visible scope beyond it. |
| **B — scope (派生父级)** | **Silence is ok.** An untraceable decision is expected. | The upstream scope doc is a *selective* set of key decisions — this stage is explicitly authorized to elaborate and branch beyond it; "can't trace lineage" is the normal case, not a deviation. |
| **C — norm-constraint** | **Silence is ok.** | Rules are prohibitions, not a to-do list — absence of violation is the only expected state; there is nothing to "extend" a rule into. |

## Axis 2 (coverage) applies only to A and B

- **A axis 2** — every intent-baseline item must be honored somewhere downstream; unfulfilled → `未履行意图`.
- **B axis 2** — every explicit upstream scope decision must be carried forward, elaborated, or explicitly deferred; silently dropped → `遗漏明确决策`.
- **C has no axis 2** — a constraint is never "fulfilled", so there is no coverage gap to detect.

## Bucket vocabulary (flag names) per role/axis

| Role | Axis 1 buckets | Axis 2 bucket |
|---|---|---|
| A — intent-baseline | `扩充意图` (same topic, exceeds expression) · `新增意图` (no same-topic item) · `不一致` (conflicts with an item) | `未履行意图` |
| B — scope | `不一致` (contradicts an explicit upstream decision) | `遗漏明确决策` |
| C — norm-constraint | `违反` | — (none) |

This vocabulary and posture is exactly what `g5-provenance-runner`'s Pipeline steps 5–6 operationalize; this document exists so a future change to the runner has the reasoning on hand without re-deriving it from the design doc.
