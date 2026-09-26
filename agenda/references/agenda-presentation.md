> Part of agenda · presentation reference · indexed from `../SKILL.md`

# Agenda Presentation

**Sole user-facing adaptation layer** for stage agenda. Flow *when* = `../SKILL.md`. This file = **L1 labels** only.

- SKILL stays English for orchestration keys; **L1 landmarks are fixed** (no mid-session synonyms). Surrounding prose follows the user's language.
- **All user-facing command phrases MUST start with `agenda`** (prefix) so they are not confused with other workflow stops.
- **L0 never to user as primary copy:** raw field names alone (`class`, `async`, bare `A-n` without gloss), mechanism talk about schema.
- **L1 ok:** landmarks below. Optional L2 = one first-use gloss only.

## L1 map (SSOT)

| Key (orchestration) | L1 | L2 (first use, optional) |
|---------------------|----|--------------------------|
| agenda / menu | **agenda 查看命令** | 列出本阶段议程可用操作 |
| add blocker | **agenda 新增 blocker** | 未了结且非异步时会挡住交付 |
| add note | **agenda 新增 note** | 只记录，不挡交付 |
| set async | **agenda 标为异步** | 仍跟踪，但不挡交付 |
| clear async | **agenda 取消异步** | 恢复为会挡交付 |
| release | **agenda 已做完** | status → released |
| waive | **agenda 放弃** | 须理由；不挡交付 |
| list blocking | **agenda 查看 blocker list** | 交付前会拦下的 blocker |
| list all | **agenda 查看全部** | 含 note 与异步 blocker |
| update | **agenda 更新项** | 改状态 / 文案 / 异步 |

**Retired (do not offer):** `agenda 新增挡门项` / `agenda 新增备忘` / `agenda 查看挡门清单` / bare labels without `agenda` prefix.

## Dialogue entry

When the user says exactly (or clearly means) **`agenda 查看命令`**:

1. Run `$AGENDA_CTL menu`.
2. Offer only the prefixed L1 options below (from stdout `l1_options` / this table).
3. After the user picks a prefixed option, run the matching `$AGENDA_CTL` command (writes only after explicit human instruction).

## Stop → L1

After **agenda 查看命令** / `$AGENDA_CTL menu`, offer:

**agenda 新增 blocker** · **agenda 新增 note** · **agenda 标为异步** · **agenda 取消异步** · **agenda 已做完** · **agenda 放弃** · **agenda 查看 blocker list** · **agenda 查看全部** · **agenda 更新项**
