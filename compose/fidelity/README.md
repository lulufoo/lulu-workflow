# compose/fidelity — Doc→facts 保真 Eval（过程门）

与 stage **Evaluating** / `$EVAL_CONTROL` **隔离**（词根 `fidelity`）。

| 路径 | 用途 |
|------|------|
| `dimension-defs/` | E1 / E2 单维定义 |
| `scripts/fidelity_control.py` | 状态门闩 CLI（`$FIDELITY_EVAL_CONTROL`） |
| revision `fidelity-evaluate-state.md` | 旁路状态（不切 `Evaluating`） |

过程档：`docs/domain/archive/compose/archive-3.0/compose-doc-ssot-facts-fidelity-eval-design.md`

**Atomize / 夹具约定：** `_facts.json` 条目默认**不写** `origin`（可选字段）。若写入 `origin`，`ref` 必须为非空字符串数组——空 `ref: []` 会在 `load_facts` 失败并盖过 fidelity 报错。
