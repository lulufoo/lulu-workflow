---
name: code-workflow
description: >-
  Use when: TDD, tdd session, 测试驱动开发, 写测试代码, 写实现代码, Red Green Refactor,
  tdd-task-list, task-from-work-order, task-from-tech, tdd workflow,
  lulu-dev-workflow tdd.
disable-model-invocation: true
---

# code-workflow

从已交付的 tech-doc 或 work-order task 文件集，执行 Test-Driven Development：先写测试，确认 Red，再写最小实现，确认 Green，最后重构。

**Scope：** TDD 代码生成阶段。输入为 Delivered tech-doc（Path A）或 Delivered work-order task 文件集（Path B），产出测试文件 + 实现文件。
**Scripts location (after install):** `~/.cursor/skills/lulu-dev-workflow/code/scripts/`
**This workflow runs in Agent mode.**（需要写代码文件并执行 Shell 命令）

---

## Commands

### `install` — Machine-level, run once

```bash
mkdir -p ~/.cursor/skills/lulu-dev-workflow/code/scripts

for f in SKILL.md transition-whitelist.json; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/code/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/code/$f
done

for f in workflow_common.py hook_guard.py start.py init.py; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/code/scripts/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/code/scripts/$f
done
```

After install, run `code-workflow init` in the target project.

---

### `init` — Project-level, run once per project

Registers the code hook into `.cursor/hooks.json` and adds the `code` section to `workflow-config.json`.

```bash
cd <project-root>
python3 ~/.cursor/skills/lulu-dev-workflow/code/scripts/init.py \
  --project-root "$(pwd)"
```

After init, verify `.cursor/lulu-dev-workflow/workflow-config.json` has the `code` block.
Set `test_command` to the actual test runner command for this project (default: `npm test`).

---

### `/code <input>` — 用户调用入口

用户通过 `/code <input>` 触发 code workflow。

**`<input>` 合法格式：**

| 格式 | 含义 | 示例 |
|------|------|------|
| `work-order/<uuid>` | 来源：指定 work-order session | `/code work-order/1d2ea64b-065d-4e12-9008-9163d475ee00` |
| `tech/<path-to-tech-doc.md>` | 来源：指定 tech doc | `/code tech /abs/path/tech-doc.md` |

**如果用户未按格式输入，停止执行，输出以下提示：**

```
❌ 无效输入。请按以下格式调用 code workflow：

  来源 work-order：
    /code work-order/<work-order-conv-id>
    例：/code work-order/1d2ea64b-065d-4e12-9008-9163d475ee00

  来源 tech doc：
    /code tech <path-to-tech-doc.md>
    例：/code tech /Users/me/proj/.cache/.../tech-doc.md

前置要求：上游必须处于 Delivered 状态。
```

---

### AI 启动序列（收到合法输入后执行）

**Step 1：解析 `<input>` 类型**

- 以 `work-order/` 开头 → **Path B**，提取 `<work-order-conv-id>`
- 以 `tech ` 开头 → **Path A**，提取 `<tech-doc-path>`
- 其他 → 非法，输出上方错误提示，**停止**

**Step 2：校验上游状态**

Path B：
```bash
# 读 work-order session 的 workflow-state.md，确认 current_state: Delivered
cat <project-root>/.cache/lulu-dev-workflow/work-order/<work-order-conv-id>/*/workflow-state.md
```
- 若 `current_state` 不是 `Delivered` → 输出错误："work-order `<id>` 尚未交付（当前状态：`<state>`），无法启动 code workflow。" 停止。
- 若路径不存在 → 输出错误："找不到 work-order `<id>`，请确认 ID 正确。" 停止。

Path A：
- 读 `<tech-doc-path>` 确认文件存在
- 若不存在 → 输出错误："找不到 tech doc：`<path>`。" 停止。

**Step 3：收集上游文件路径**

Path B：
```bash
# task-list.md
<project-root>/.cache/lulu-dev-workflow/work-order/<id>/<revision>/task-list.md
# 所有 task.md（通配符枚举）
<project-root>/.cache/lulu-dev-workflow/work-order/<id>/<revision>/tasks/*/task.md
```

Path A：直接使用 `<tech-doc-path>`。

**Step 4：运行 start.py**

Path B：
```bash
python3 ~/.cursor/skills/lulu-dev-workflow/code/scripts/start.py \
  --project-root "$(pwd)" \
  --conversation-id "<current-conv-id>" \
  --mode task-from-work-order \
  --task-list-ref "<abs-path-to-task-list.md>" \
  --task-refs <abs-path-to-t1/task.md> <abs-path-to-t2/task.md> ...
```

Path A：
```bash
python3 ~/.cursor/skills/lulu-dev-workflow/code/scripts/start.py \
  --project-root "$(pwd)" \
  --conversation-id "<current-conv-id>" \
  --mode task-from-tech \
  --tech-ref "<abs-path-to-tech-doc.md>"
```

> `<current-conv-id>` 从当前对话 transcript ID 获取（系统在每轮对话开头已提供，勿自行 `ls` 搜索）。

**Step 5：读 `code-task-list.md`，展示任务列表，等待用户确认后开始执行**

---

## Session File Structure

```
.cache/lulu-dev-workflow/code/<conv_id>/
  session-state.md              ← active_session: N（线性递增，不回退）

  s{N}/                         ← 第 N 个 code session
    workflow-state.md           ← current_state / current_task / current_phase（AI 写，Hook 校验）
    code-task-list.md            ← checkbox 进度列表（统一执行锚点）
    human-delivery-gate.md      ← 所有 task Done 后，用户确认写入

    tasks/
      t{X}/
        code-log.md              ← 每个 Phase 的时间戳 + 执行说明
        red-run.md              ← Phase 2：测试运行输出（Hook 依赖此文件）
        green-run.md            ← Phase 4：测试运行输出
```

---

## State Model

### Session 级

States: `Executing → Completed`

| 起始状态 | 目标状态 | 触发条件 |
|---------|---------|---------|
| `[*]` | `Executing` | start 命令 |
| `Executing` | `Completed` | Hook 校验：code-task-list.md 所有 task 均为 [x] |

### Task Phase 级

```
WriteTests → VerifyRed → WriteImpl → VerifyGreen → Refactor → Done
                                              ↑
                                    tdd_exempt: true 时可直接 VerifyGreen → Done
```

| 起始 Phase | 目标 Phase | 前置条件（Hook 校验） |
|-----------|-----------|-------------------|
| `[*]` | `WriteTests` | 所有 depends_on task 均为 [x] |
| `WriteTests` | `VerifyRed` | — |
| `VerifyRed` | `WriteImpl` | `tasks/t{X}/red-run.md` 存在 |
| `WriteImpl` | `VerifyGreen` | — |
| `VerifyGreen` | `Refactor` | — |
| `VerifyGreen` | `Done` | tdd_exempt: true |
| `Refactor` | `Done` | — |
| `Done` | `WriteTests` | 下一个 task |

---

## Operating Rules

### General

1. 读 `.cursor/lulu-dev-workflow/workflow-config.json` → `code.test_command` 获取测试命令，在 Phase 2 / 4 / 5 均使用此命令运行测试。
2. 读 `session-state.md` → `active_session: N` 确定当前 session 轮次。
3. `s{N}/workflow-state.md` 是权威状态来源，通过写入它来请求状态迁移。
4. 永远不从文件存在与否推断状态，只读 `workflow-state.md`。
5. 使用全量 `Write`（不使用 `Edit`）更新 `workflow-state.md`。
6. 写 `workflow-state.md` 时必须保留所有字段（`mode`、`task_list_ref`、`current_task`、`current_phase`）。

### 启动序列

> 此节是 AI 在 `start.py` 成功运行后的后续步骤，对应上方"Step 5"。

**Path B（task-from-work-order）：**

1. start.py 已自动生成 `code-task-list.md`（所有 task ⏳ Pending）
2. 读 `code-task-list.md`，向用户展示任务列表（含依赖关系）
3. 等待用户确认任务范围 → 确认后开始执行第一个 task

**Path A（task-from-tech）：**

1. 读 `<tech-doc-path>`，按 Test First 逻辑分析改动点，起草 `code-task-list.md`（task_id 从 t1 开始，粒度：单函数变更）
2. 向用户展示草稿，等待确认
3. 用户确认后写入 `s{N}/code-task-list.md`
4. 写 `workflow-state.md`：`current_task: t1, current_phase: WriteTests`
5. 开始执行第一个 task

### Phase 执行规则（每个 task 循环一次）

**Phase 1 — WriteTests**

- 输入：task.md「验收条件」节（Path B）或 code-task-list.md 中该 task 的描述（Path A）
- 产出：写入测试文件（`test_file` 路径）
- 约束：**禁止写任何实现代码**
- 完成：所有验收条件均有对应测试用例
- 退出：写 `workflow-state.md: current_phase: VerifyRed`

**Phase 2 — VerifyRed（必须执行，不可跳过）**

- 操作：运行 `test_command`（Shell），捕获完整输出
- 期望：所有测试 FAIL，失败原因 = 函数/类不存在（非语法错误）
- 异常：
  - 测试通过 → 测试了已有行为，返回 Phase 1 修正测试
  - 语法错误 → 修复语法，重新运行，直到失败原因正确
- 记录：写 `tasks/t{X}/red-run.md`（含完整输出 + 一行确认："失败原因：函数不存在"）
- 退出：写 `workflow-state.md: current_phase: WriteImpl`（Hook 校验 red-run.md 存在）

**Phase 3 — WriteImpl**

- 产出：写入实现文件（`target_file` 路径）
- 约束：
  - **Do not modify tests**（绝对禁止修改测试文件）
  - Minimum implementation only
  - 遵守 task.md「约束」节所有硬性规则
- 退出：写 `workflow-state.md: current_phase: VerifyGreen`

**Phase 4 — VerifyGreen**

- 操作：运行 `test_command`（Shell），捕获完整输出
- 期望：所有测试 PASS，无 warning / error
- 失败：修改实现代码（禁止改测试），重新运行，循环直到全部 PASS
- 记录：写 `tasks/t{X}/green-run.md`（含完整输出）
- 退出：写 `workflow-state.md: current_phase: Refactor`（tdd_exempt 时写 `Done`）

**Phase 5 — Refactor**

- 操作：去重、改名、提取 helper、消除魔法数字
- 约束：每次重构后重新运行测试，确认仍全部 PASS
- 禁止：添加新行为、新测试
- tdd_exempt: true 的 task 跳过此 phase
- 退出：写 `workflow-state.md: current_phase: Done`

**Task 完成动作（每个 task Done 后执行）**

1. 更新 `code-task-list.md` 对应行：`[ ]` → `[x]`，状态标记改为 `✅ Done`，frontmatter `done` 计数 +1
2. 写 `tasks/t{X}/code-log.md`（各 Phase 时间戳 + 执行说明）
3. 若还有未完成 task：写 `workflow-state.md: current_task: t{X+1}, current_phase: WriteTests`
4. 若所有 task 已完成：写 `workflow-state.md: current_state: Completed`（Hook 校验）

**Session 完成动作**

1. 向用户展示 `code-task-list.md` 最终状态（所有 task ✅ Done）
2. 等待用户显式确认
3. 写 `s{N}/human-delivery-gate.md`（`approved: true`）
4. 写 `s{N}/workflow-state.md: current_state: Completed`

---

## Session File Formats

### session-state.md

```markdown
---
version: 1
active_session: 1
updated_at: 2026-05-17T09:00:00+08:00
---
```

### s{N}/workflow-state.md

```markdown
---
version: 1
workflow: code
current_state: Executing
mode: task-from-work-order
task_list_ref: /abs/path/.cache/lulu-dev-workflow/code/<conv_id>/s1/code-task-list.md
current_task: t2
current_phase: WriteImpl
updated_at: 2026-05-17T09:00:00+08:00
---
```

> 写 `workflow-state.md` 时必须保留所有字段，包括 `mode`、`task_list_ref`。

### s{N}/code-task-list.md

```markdown
---
source: work-order
task_list_ref: /abs/path/.cache/lulu-dev-workflow/work-order/<conv_id>/r1/task-list.md
total: 5
done: 1
---

# Code Task List

- [x] t1 · validateEmail · `src/utils/validators.ts` · ✅ Done
- [ ] t2 · validatePhone · `src/utils/validators.ts` · 🔴 WriteImpl
- [ ] t3 · authService 集成 · `src/services/auth.ts` · ⏳ Pending (depends: t1, t2)
- [ ] t4 · 集成测试 · `tests/auth.test.ts` · ⏳ Pending (depends: t3)
- [ ] t5 · 错误处理层 · `src/utils/error.ts` · ⏳ Pending
```

tdd_exempt 任务在行末加 `[tdd_exempt]` 标注：
```markdown
- [ ] t6 · 更新按钮样式 · `src/components/Button.tsx` · ⏳ Pending [tdd_exempt]
```

### s{N}/tasks/t{X}/code-log.md

```markdown
# t{X} TDD 执行日志

## Phase 1 — WriteTests
- 时间：2026-05-17T10:00:00+08:00
- 产出：`tests/utils/validators.test.ts`（3 个测试用例）

## Phase 2 — VerifyRed
- 时间：2026-05-17T10:02:00+08:00
- 结果：3 FAIL（validateEmail is not a function）
- 确认：失败原因符合预期

## Phase 3 — WriteImpl
- 时间：2026-05-17T10:05:00+08:00
- 产出：`src/utils/validators.ts`（validateEmail 函数，15 行）

## Phase 4 — VerifyGreen
- 时间：2026-05-17T10:06:00+08:00
- 结果：3 PASS

## Phase 5 — Refactor
- 时间：2026-05-17T10:08:00+08:00
- 变更：提取 EMAIL_REGEX 常量，重命名内部变量
- 验证：3 PASS（重构后）
```

### human-delivery-gate.md

```markdown
---
approved: true
approved_at: 2026-05-17T10:30:00+08:00
note: All tasks Done. User confirmed completion.
---
```

---

## work-order → code 契约

- **Path B 输入**：`--task-list-ref`（Delivered work-order task-list.md）+ `--task-refs`（所有 task.md）
- **task.md 自包含**：「约束」+「补充」节显式搬运 tech-doc 信息，code session 只读 task.md，无需回头读 tech-doc
- **tdd_exempt 标记**：从 task.md frontmatter 或 code-task-list.md 行末 `[tdd_exempt]` 读取，跳过 Phase 1/2/5
- **测试命令**：从 `workflow-config.json → tdd.test_command` 读取，每次测试前确认命令正确
