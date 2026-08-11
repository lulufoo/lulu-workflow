# compose/atomize-eval — Atomize Eval（独立评估任务）

Doc→`_facts.json` 保真评估，接入共享 Eval 引擎；与交付 Evaluating / `$EVAL_CONTROL` **分离**。

| 路径 | 用途 |
|------|------|
| `eval-profile.json` | adapter-config（含 `completion_mode=return_to_caller`） |
| `dimension-defs/` | E1 / E2 |
| `methods/` | E1 / E2 method 正文 |
| `scripts/atomize_eval_control.py` | `$ATOMIZE_EVAL_CONTROL` 入口 |
| `scripts/atomize_eval_adapter.py` | WorkflowAdapter（不触 StageGate；B=`_facts.json`） |
| `{slice}/atomize-eval/` | 运行时状态与轮次目录 |

过程档：`docs/domain/archive/compose/archive-8.0/compose-atomize-eval-shared-eval-integration-design.md`
