# Gap Display (Round Iteration 2b)

Display contract for user-facing gap presentation. **Does not invoke scripts** — parent SKILL 2b runs macros and pins JSON first.

**Invariant:** Display-only. Never mutate `probe-{seq}.json` on disk. Refiner uses original `intent_gap` from `$PROBE.items`.

---

## Prerequisites

Parent **2b** has already:

1. Run `$ROUND_CONTROL read-probe-report --round {N}` → pin stdout as **`$PROBE`**
2. Run `$ROUND_CONTROL read-section-pointer --round {N}` → pin stdout as **`$POINTER`**

Render from **`$PROBE` + `$POINTER` only**. Do not read probe report files on disk. Do not re-run `$ROUND_CONTROL` inside this document.

---

## Input fields

### From `$PROBE`

| Field | Use |
|-------|-----|
| `round` | Title `Round {N}` |
| `section_key` / `active_section` | Title `{ACTIVE_SECTION}` (prefer `active_section` when present) |
| `items[]` | Row source (after filter below) |
| `undecided_count` | Footer; gate for 2c |
| `kw0_pending_count` | KW0 gate |
| `upstream_undecided_count` | Footer |
| `probe_seq` | Footer |

Per item:

| Field | Use |
|-------|-----|
| `id` | ID column; user decision token |
| `gap_kind` | Grouping and issue label |
| `target_kw` | KW check-item label (`gap_kind: kw` only) |
| `intent_gap` | Paraphrase source → plain summary |
| `sub_section_summary` | Optional subject in plain sentence |
| `upstream_section` | Upstream sub-header and sentence subject |
| `decision` | Filter: show only `"—"` |
| `status` | Filter: `open` or `kw0_pending` |

Do not surface full `kw_criteria` in the user table (refiner-only).

### From `$POINTER`

| Field | Use |
|-------|-----|
| `sections` | Footer: `{section_key} {status}` for each registry section |
| `active_section` | Cross-check with `$PROBE` |

Footer counts come from **`$PROBE`**, not re-counted from `items`.

---

## Render pipeline

1. **KW0 gate:** If `$PROBE.kw0_pending_count` > 0 → show only filtered rows with `status: kw0_pending`; omit Upstream; footer + prompt → **stop and wait** (skip 2c).
2. **Filter items:** Include only rows where `decision === "—"` and `status` ∈ `{open, kw0_pending}`. Omit `no_gap`, `resolved`, and decided rows.
3. **Group:**
   - **KW** — `gap_kind` ∈ `kw`, `kw0_pending`
   - **Upstream** — `gap_kind` ∈ `upstream_violation`, `upstream_coverage`; sub-header `Upstream（vs {upstream_section}）`; one table per upstream section; **violation before coverage** within the same upstream.
4. **Label** — maps below; never show raw `KW2` or enum names alone.
5. **Paraphrase** — `intent_gap` → plain summary (user locale below).
6. **Footer** — `$POINTER.sections` statuses + `$PROBE` counts.
7. **Prompt footer** — template below → **stop and wait**; do not infer decisions or enter 2c.

Omit empty groups.

---

## Label maps

### KW check item (`target_kw`)

| target_kw | Label (user locale) |
|-----------|------------------------|
| 1 | 做了什么（是否说清） |
| 2 | 为什么（依据/理由） |
| 3 | 替代方案（是否交代取舍） |
| 4 | 失效条件（何时不再成立） |

### Upstream type (`gap_kind`)

| gap_kind | Label (user locale) |
|----------|---------------------|
| `upstream_coverage` | 上游没写进本节 |
| `upstream_violation` | 与上游冲突 |

### KW0 pending

| Check | Plain summary (user locale) |
|-------|----------------------------|
| 待补内容 | 「{sub_section_summary}」还是空的，请先补一段内容再探测。 |

---

## Paraphrase rules (`intent_gap` → 简单说就是)

**User-facing copy locale: Chinese.**

1. One sentence; no unexplained jargon (`operationalize`, `anchor`, raw enum names).
2. Prefer: `「{sub_section_summary}」{check/issue label}还不够：{what is missing}`.
3. Stay faithful to `$PROBE` item `intent_gap` — paraphrase, do not invent gaps.
4. Upstream rows: name `{upstream_section}` and `{ACTIVE_SECTION}` when helpful.

---

## Layout template (user locale: Chinese)

```text
Round {N} / {ACTIVE_SECTION} — 待决缺口

KW
| 编号 | 检查项 | 简单说就是 |
| {id} | … | … |

Upstream（vs {upstream_section}）
| 编号 | 问题 | 简单说就是 |
| {id} | … | … |

Section 状态： {section_key} {status} · …
Undecided: {n} · KW0 pending: {n} · Upstream undecided: {n} · Probe seq: {seq}

请你决定（Round {N} / {ACTIVE_SECTION}）
例如：{id} accept · {id} skip（多条 accept 可一次 refiner 合并处理）。
```

After this block: **stop and wait** for the user's next message.

---

## Example (NG / Round 1)

| 编号 | 检查项 | 简单说就是 |
|------|--------|------------|
| NG-1 | 为什么（依据/理由） | 「排除项列表」只写了名字，没写清每条为啥不做（主动不做 / MVP 先不做 / 技术上做不了）。 |
| NG-2 | 替代方案（是否交代取舍） | 各条「不做」和 North Star 没对上号，看不出是在保护哪个目标。 |

| 编号 | 问题 | 简单说就是 |
|------|------|------------|
| NG-U-NS-1 | 上游没写进本节 | NS 里「要排除什么」还停在初始化占位写法，NG 正文还没写成清楚的 Non-Goals 条目。 |
