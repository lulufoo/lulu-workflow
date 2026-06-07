# decision-doc 模板章节解读

> **Source:** [`decision-doc.template.md`](decision-doc.template.md) · [`diagnostic/SKILL.md`](../SKILL.md) · gate files under [`../gates/`](../gates/)
>
> ✅ Verified against repository sources as of the diagnostic template refactor (2026-06-08).

---

## 结构总览

```
# Decision                         ← 文档标识

## User Prior                      ← Open channel + G0 全程
## Problem Definition              ← Q gate
## Direction Comparison            ← E gate
## Decision Rationale              ← D gate
## Scope                           ← D gate

## Assumptions & Risks             ← 全程收集 + R 定级（关键决策风险，前置）

## Execution Analysis              ← X gate（父节）
### Acceptance Criteria
### Impact Surface
### External Dependencies
### Implementation Sketch
```

---

## 文档头部（YAML frontmatter）

```yaml
input:
  domain_constraints: |
    Evaluated by diagnostic kernel `Domain Constraints HARD-GATE`.
```

机器可读的元数据。DC gate 写文件时，读取 `domain_constraints` 决定哪些节要省略（由 domain holder 注入的约束控制）。**不出现在最终 decision-doc 正文中。**

---

## User Prior

**来源：** Open channel 阶段用户主动提供的内容，以及全程任意 gate 由 G0 自动捕获的内容。

**四个类型标签：**

| 标签 | 含义 | 隐性假设检查 |
|------|------|------------|
| `[judgment]` | 用户对某件事的评估或结论 | **必须检查**：「这个判断成立，需要 X 为真」→ 提取 X 到 Assumption Log |
| `[preference]` | 偏好某种方式，无强制理由 | 不检查 |
| `[concern]` | 顾虑或风险感知 | 不检查 |
| `[excluded]` | 已排除的方向或选项，附原因 | **必须检查**：排除理由里可能隐含假设 |

**用途：** D gate 前 review，确认决策方向反映了用户偏好；R gate 签字确认，确认没有遗漏的 prior 被忽视。

---

## Problem Definition

**来源：** Q gate（Problem Clarification）。

- 上半部分：触发原因 + 要解决的问题（problem statement）
- `Known Constraints`：**事实性约束，不可谈判**。这是 Q gate 明确说「不要试图挑战或协商掉」的内容，例如平台限制、合规要求、已有承诺。

**用途：** 整个 decision-doc 的需求锚点，plan 阶段的起点。

---

## Direction Comparison

**来源：** E gate（Direction Exploration）。

两张表：

- **候选方向表**：2–3 个方向，每个有 Core Approach / Pros / Cons
- **Excluded Directions 表**：E gate 要求列出已否决方向及原因

**关键作用：** 防止已否决的方案在 plan 阶段或实现阶段被重新翻出。后续任何阶段的「为什么不用方案 B」都应该回引这里，而不是重新讨论。

---

## Decision Rationale

**来源：** D gate（Decision & Scope）。

格式强制要求 rationale **必须引用 Direction Comparison 的 trade-offs**——不能凭空写结论。既要说「选了什么、为什么」，也要说「排除了什么、为什么」。

对应 Plan 文档里「已确认决策」的叙事版：Plan 里的表格是压缩写法，decision-doc 这里保留完整的 trade-off 推理链。

---

## Scope

**来源：** D gate。

两行，缺一不可：

- `Applies to`：这个决策覆盖什么
- `Explicitly excludes`：**明确不覆盖什么**

「Explicitly excludes」是强约束，必须写。对应 Plan 的「不在 MVP」。强迫作者说清「不做什么」，防止实现阶段边界蔓延。

---

## Assumptions & Risks

**位置：** 放在 Scope 之后、Execution Analysis 之前——读完「决定了什么」，立刻看「这个决定押了哪些赌注」，再进入执行细节。

**来源：** 各 gate 逐步发现（source 列记录来源 gate），R gate 统一定级。

**表格七列：**

| 列 | 说明 |
|----|------|
| # | 假设编号（A1/A2...） |
| Assumption | 假设内容 |
| Source | 首次发现的 gate（Q/E/D/X） |
| Risk | H / M / L（R gate 定级） |
| Failure Consequence | 假设不成立时的后果 |
| Verification | H → `Method / Owner / Timing / Release condition`；M/L → `Accepted` |
| Status | `[待验证]` / `[已验证]` / `[失效]` |

**Status 生命周期：**

- `[待验证]`：默认初始
- `[已验证]`：R exit 3（全部无不确定）/ RR Released / M-L batch-confirmed
- `[失效]`：RS 触发后由 Register Reopen Protocol 标记

这节合并了原来分散的 Assumptions & Risks 和 Verification Items 两张表，统一用一张表追踪全生命周期。对应 Plan 文档里的「风险」节。

---

## Execution Analysis

X gate 的 5 个维度产出，收归在同一个父节下，读者一眼看出这是「执行可行性分析块」。

### Acceptance Criteria

**来源：** X gate dim 1。

- 正文：可观察、可验证的完成标准（不是主观感受）
- `Gap (if any)`：**X dim 5（Gap Check）的结果写在这里**，不是单独一节。若实现预期产出与 AC 之间有差距，显式写出；若无，写 `None`。Gap 非 None 会触发 reopen E 或 D。

### Impact Surface

**来源：** X gate dim 2。

表格格式，**层名不预设**——由 domain holder 通过 Role 注入参考层，或 AI 根据角色自主枚举：

- tech 角色典型层：System-internal / System boundary / External parties
- product 角色典型层：User experience / Business process / Operations / External parties

`Change Type` 列用枚举值（add / modify / delete / read-only），防止 AI 自由发挥。

diagnostic 阶段只做方向性枚举；体系化影响链分析属于 Plan 阶段。

### External Dependencies

**来源：** X gate dim 3。

四列：Dependency / Contract / Authoritative Source / Confirmation Mechanism。

「契约不清楚」→ 直接进 Assumption Log，不强行填写。tech 和 product 都需要填（产品层也有平台依赖、跨团队依赖、合规要求）。

### Implementation Sketch

**来源：** X gate dim 4（原 Implementation Cost，已重构）。

三个字段：

| 字段 | 问的问题 | 对应价值 |
|------|---------|---------|
| Key changes | 改什么 | 给 plan 阶段的起点 |
| Critical constraints | 有哪些非显而易见的约束 | 容易进 Assumption Log |
| Reversibility | 容不容易撤回 | 影响 R gate 风险定级；不可逆 = 天然高风险 |

这三个字段对 tech 和 product 都通用：Key changes 在产品层是功能/流程变化，在技术层是代码/模块变化；Reversibility 在产品层往往比技术层更重要。

---

## 节与 gate 的完整对应

```
document section          gate          register / loop
─────────────────────────────────────────────────────
User Prior                Open + G0     User Prior Log
Problem Definition        Q             —
Direction Comparison      E             —
Decision Rationale        D             —
Scope                     D             —
Assumptions & Risks       全程 → R      Assumption Log（合并 LoopB）
  └─ Verification column  V / RR        LoopB
Execution Analysis        X             —
  Acceptance Criteria     X dim 1+5     Gap Check 结果写入此处
  Impact Surface          X dim 2       —
  External Dependencies   X dim 3       —
  Implementation Sketch   X dim 4       —
```

**DC gate 在对话里强制展示的 3 节**（不只显示文件路径）：

1. Decision Rationale
2. Scope（含 exclusions）
3. Assumptions & Risks（含风险等级和 Verification 列）
