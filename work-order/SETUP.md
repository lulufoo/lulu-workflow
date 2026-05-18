# work-order-workflow — Setup

## `install` — Machine-level, run once

```bash
mkdir -p ~/.cursor/skills/lulu-dev-workflow/work-order/scripts

for f in SKILL.md transition-whitelist.json 30-work-order-task-template.md 31-work-order-tasklist-template.md; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/work-order/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/work-order/$f
done

for f in workflow_common.py hook_guard.py start.py init.py; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/work-order/scripts/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/work-order/scripts/$f
done
```

After install, run `work-order-workflow init` in the target project.

---

## `init` — Project-level, run once per project

Registers the work-order hook into `.cursor/hooks.json` and ensures `workflow-config.json`
has a `work_order` section.

```bash
cd <project-root>
python3 ~/.cursor/skills/lulu-dev-workflow/work-order/scripts/init.py \
  --project-root "$(pwd)"
```

After init, verify `.cursor/lulu-dev-workflow/workflow-config.json` has the `work_order`
block. Fill in `twca_url` and `woqa_url` if the default GitHub URLs differ from your project's copies.
