# compose/fact-intake-eval — Fact Intake Eval（独立评估任务）

Doc→`_facts.json` 保真评估，接入共享 Eval 引擎；与交付 Evaluating / `$EVAL_CONTROL` **分离**。

原名 `atomize-eval`；现嵌套于 `fact-intake-runner/`（archive-30 · F3a）。

| 路径 | 用途 |
|------|------|
| `eval-profile.json` | adapter-config（含 `completion_mode=return_to_caller`） |
| `dimension-defs/` | E1 / E2 |
| `methods/` | E1 / E2 method 正文 |
| `scripts/fact_intake_eval_control.py` | `$FACT_INTAKE_EVAL_CTL` 入口 |
| `scripts/fact_intake_eval_adapter.py` | WorkflowAdapter（不触 StageGate；B=`_facts.json`） |
| `{slice}/fact-intake-eval/` | 运行时状态与轮次目录 |

过程档：`docs/domain/archive/compose/archive-8.0/compose-atomize-eval-shared-eval-integration-design.md` · 结构锁：`archive-30.0/compose-fact-intake-runner-structure-framework.md`
