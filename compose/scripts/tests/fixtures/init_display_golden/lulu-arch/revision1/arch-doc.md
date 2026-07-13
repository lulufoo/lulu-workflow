# 行动层 v1 · Technical Architecture

**Date:** 2026-07-13
**Version:** v1
**Status:** Draft (Init simulation — P0→Pd→P1→P2→P3)

**Decision-doc:** `topic-20260706060746-54e47acc/lulu-approach/decision-doc.md`

---
<!-- chapter:chap-si -->
## Situation & Direction

行动层 v1 技术架构的触发是：在既有 Tauri App、knowledge MCP 与 skills 体系上，要把「计划任务创建→执行→归档→双向可见」做成可落地闭环，覆盖 master/sub 持久化、MCP 任务接口、归档关联自动完成与 Workbench 管理 UI。

收敛方向为**方向 A**：独立 `plan_tasks.json` 存储 + 扩展归档索引（对齐 read_later 模式；新增 MCP task tools；扩展 `archive_document`；Workbench 新 service + UI）。明确排除方向 B（任务嵌入 corpus index）与方向 C（协议先行、存储后置）。

方向落地须同时遵守硬约束：创建仅走 MCP/SKILL（UI 不创建）；完成粒度是 `sub_task_id`；Workbench 不内嵌 AI；Read Later 不改；任务↔归档双向索引；MCP 为 Cursor 侧权威接口；协议支持 `master_task_id → sub_task_id`。

---

<!-- chapter:chap-bd -->
## Boundaries

| 纳入 | 排除 |
|------|------|
| `plan_tasks.json` master/sub 树 | SQLite / 新 DB |
| MCP create/get/list/complete | 改动 read_later |
| `archive_document` 扩展 master/sub task id 自动关联+完成 | UI 创建任务 |
| Tauri `services/plan_task/` | parent 一次性完成 |
| Workbench UI 列表/详情/拷贝/双向关联 | 归档触发策略；Meili 任务索引；已完成历史展示 |
| Skills 对接与端到端闭环 | |

验收要对齐：schema+测试、MCP tools 可用、归档扩展自动关联+完成子项与父任务自动完成、双向可查、Workbench UI、Skills 闭环，且 read_later 与无参归档行为不变。

---

<!-- chapter:chap-sh -->
## Structure Shape

结构形状把**行动持久化**与**知识归档**分开：`plan_tasks.json` 独立持久化（对齐 read_later），MCP 作为唯一写入口；`archive_document` 扩展可选 `task_ref`，在同调用链内关联并完成子项；Tauri `plan_task` service 承载 CRUD；Workbench UI 只做管理与双向可见，不创建任务。

影响面按层切开：Tauri 后端（新增 plan_task、改 archive_write、local_http 路由）、knowledge MCP（task tools + archive 扩展）、corpus `index.json` 可选 `task_ref`、本地 `plan_tasks.json`、Workbench 任务 UI、Skills 对接。

---

<!-- chapter:chap-fd -->
## Feature Dependency Graph

特征依赖顺序（里程碑链）：

1. 定 schema + MCP 契约（本 arch 收敛）
2. Tauri `plan_task` service + MCP tools
3. 扩展 `archive_document`
4. Workbench UI
5. Skills + 端到端验证

后序特征不得跳过前序契约；UI 不得成为写入口。

---

<!-- chapter:chap-kd -->
## Architecture Rationale

采纳方向 A 的理由：与现有 read_later 的 JSON 持久化模式一致，行动层与知识层存储分离，MCP 作为唯一写入口，降低与 corpus index 耦合以及 UI 创建越权的风险。

排除 SQLite（v1 过重）、改 read_later（硬约束）、Cursor 直写任务文件（违反 MCP 权威接口）。这些取舍由结构形状（独立任务存储 + MCP 写入口 + 归档扩展）直接支撑，而非事后补丁。
