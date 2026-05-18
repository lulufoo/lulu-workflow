# product-doc-workflow — Setup

## `install` — Machine-level, run once

```bash
mkdir -p ~/.cursor/skills/lulu-dev-workflow/product/scripts
mkdir -p ~/.cursor/skills/lulu-dev-workflow/product/templates

gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/SKILL.md" \
  --jq '.content' | base64 -d \
  > ~/.cursor/skills/lulu-dev-workflow/SKILL.md

gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/product/SKILL.md" \
  --jq '.content' | base64 -d \
  > ~/.cursor/skills/lulu-dev-workflow/product/SKILL.md

gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/product/transition-whitelist.json" \
  --jq '.content' | base64 -d \
  > ~/.cursor/skills/lulu-dev-workflow/product/transition-whitelist.json

for f in init.py hook_guard.py start.py workflow_common.py; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/product/scripts/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/product/scripts/$f
done

for f in workflow-config.template.json; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/product/templates/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/product/templates/$f
done
```

After install, run `product-doc-workflow init` in the target project.

---

## `init` — Project-level, run once per project

> Prerequisite: `install` has been run.

```bash
python3 ~/.cursor/skills/lulu-dev-workflow/product/scripts/init.py \
  --project-root "$(pwd)"
```

Creates:
- `.cursor/lulu-dev-workflow/workflow-config.json`
- merges a `preToolUse` hook into `.cursor/hooks.json`
- ensures `.gitignore` includes `.cache`

After init, open `.cursor/lulu-dev-workflow/workflow-config.json` and fill in:

| Field | Description |
|-------|-------------|
| `product.template_url` | 产品文档模板 |
| `product.review_checklist_url` | 进入评估前审查清单 |
| `product.pdqa_url` | PDQA 评估框架 |

参考：`https://github.com/lulufoo/ai-software-dev/tree/main/ai-dev-workflow-framework/product_template`
