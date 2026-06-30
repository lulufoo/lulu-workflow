# Gap Kinds

每个 `gap_kind` 的语义定义。

**SSOT 分工：**
- 本文件：语义（什么意思 / 由谁检测 / `repair_class` / 触发条件）
- `gap-display.md`：展示标签（用户可见的中文措辞）
- `probe_report_schema.py`：合法枚举值 + 校验规则（`_GAP_KINDS_ALL`；`_SCHEMA.enums.gap_kind.description`）

---

## KW 类（`scope: subsection`，检测者：LLM prober Step 2）

### `kw`

- **语义：** 某子段的 KW 成熟度不足——子段有内容，但 KW1–KW4 某条判据尚未满足。
- **repair_class：** `kw_subsection`
- **fix_mode：** `auto`（profile 可 override 为 `confirm`）
- **触发条件：** prober Step 2 扫描子段，判断不满足 `section-kw-criteria` 中对应 KW 层级的标准。
- **必填字段：** `target_kw`（1–4）、`kw_criteria`（open 时）、`intent_gap`
- **展示标签：** 见 `gap-display.md` §KW check item

### `kw0_pending`

- **语义：** 某子段为空或仅含占位符——连最基础内容（KW0）都没有，无法做成熟度探测。
- **repair_class：** `mechanical`（空段是结构性缺陷，确定性可补骨架）
- **fix_mode：** `auto`
- **触发条件：** prober Step 2 检测到子段 body 为空、仅含 TODO / 占位符文本。
- **必填字段：** `intent_gap`；**禁止** `kw_criteria`
- **展示标签：** 见 `gap-display.md` §KW0 pending（「还是空的，请先补一段内容」）
- **备注：** `kw0_pending` 也可由 `structural_probe.py` 产出（与 LLM Step 2 合流）；两者 gap_kind 相同，由先检测到的一方登记。

---

## Upstream 类（`scope: section`，检测者：LLM prober Step 2b）

### `upstream_violation`

- **语义：** 当前 section 的内容与某个 **stable upstream section** 的约束/意图 **存在矛盾**。
- **repair_class：** `semantic_review`
- **fix_mode：** `confirm`（**红线：** 触及 decision-doc 解读，必须人在环）
- **触发条件：** prober Step 2b 对比当前 section body 与 upstream section body，发现当前 section 违反了 upstream 的 `upstream_relation` 约束。
- **必填字段：** `upstream_section`、`upstream_criteria`（open 时，含 `upstream_intent`/`expected`/`observed`）、`intent_gap`；**禁止** `target_kw`、`kw_criteria`
- **展示标签：** `与上游冲突`

### `upstream_coverage`

- **语义：** 某个 stable upstream section 的意图/约束，在当前 section **没有被承接**（缺失，非矛盾）。
- **repair_class：** `semantic_review`
- **fix_mode：** `confirm`
- **触发条件：** prober Step 2b 对比后，upstream 的要求在当前 section body 中无对应内容。
- **必填字段：** 同 `upstream_violation`
- **展示标签：** `上游没写进本节`

---

## Intent 类（`scope: section`，检测者：LLM prober Step 2c）

### `intent_violation`

- **语义：** 当前 section body 与 **scope doc（decision-doc）** 的决策/约束 **存在矛盾**（如与排除事项冲突、违反已拒绝方案的决策）。
- **repair_class：** `semantic_review`
- **fix_mode：** `confirm`（**红线：** 基准是 decision-doc，SSOT 解读必须人确认）
- **触发条件：** prober Step 2c 对比 section body 与 scope doc，发现 section 内容违反了决策方向或明确排除项。
- **必填字段：** `intent_criteria`（open 时，含 `decision_intent`/`expected`/`observed`）、`intent_gap`；**禁止** `target_kw`、`kw_criteria`、`upstream_section`、`upstream_criteria`
- **展示标签：** `与决策冲突`

### `intent_coverage`

- **语义：** scope doc 的某条决策/方向/AC，在当前 section body **没有被落实**（缺失，非矛盾）。
- **repair_class：** `semantic_review`
- **fix_mode：** `confirm`
- **触发条件：** prober Step 2c 判断 section body 未覆盖 scope doc 中与本 section 类型相关的某条决策要求。
- **必填字段：** 同 `intent_violation`
- **展示标签：** `决策还没写进本节`

---

## Structural 类（`scope: subsection` 或 `section`，检测者：脚本 `structural_probe.py` Step 0）

### `structural`（新增）

- **语义：** 文档结构/引用存在 **确定性缺陷**——不涉及语义判断，可由脚本精确检测。
- **repair_class：** `mechanical`
- **fix_mode：** `auto`（**不可 override**）
- **触发条件（典型）：**
  1. section 存在但 `<!-- section-key:KEY -->` 锚点缺失或 KEY 不匹配；
  2. registry 声明的必填子段缺失；
  3. 占位符 / TODO 字符串残留（非空但未被替换）；
  4. `code_refs` 中 `file::symbol (line)` 在仓库不存在（由共享 `code_ref_validator.py` 校验，与 Eval d1 共用）；
  5. Tasks 段引用的 AC id 在 scope doc 中不存在；
  6. 内部锚链接（`#section-key`）无对应目标。
- **必填字段：** `intent_gap`（描述具体缺陷）；`target_kw` / `upstream_section` / `intent_criteria` 均 **不适用**
- **展示标签：** `结构缺陷（自动修复）`（仅出现在 2b「自动处理·仅知会」区）
- **备注：** 降级路径——`structural_probe.py` 检测失败（无法确定性修复）→ `mechanical_fixer.py` 失败 → `repair_class` 改写为 `kw_subsection`，`degraded_from=mechanical` 留痕。

---

## repair_class 汇总

| `gap_kind` | `repair_class` | `fix_mode` | 人在环 |
|------------|----------------|------------|--------|
| `structural` | `mechanical` | `auto` | 仅知会 |
| `kw0_pending` | `mechanical` | `auto` | 仅知会 |
| `kw` | `kw_subsection` | `auto`（可 override） | 仅知会 |
| `upstream_violation` | `semantic_review` | `confirm` | **必须拍板** |
| `upstream_coverage` | `semantic_review` | `confirm` | **必须拍板** |
| `intent_violation` | `semantic_review` | `confirm` | **必须拍板** |
| `intent_coverage` | `semantic_review` | `confirm` | **必须拍板** |
