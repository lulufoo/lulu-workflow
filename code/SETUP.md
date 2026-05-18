# code-workflow — Setup

## `install` — Machine-level, run once

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

## `init` — Project-level, run once per project

Registers the code hook into `.cursor/hooks.json` and adds the `code` section to `workflow-config.json`.

```bash
cd <project-root>
python3 ~/.cursor/skills/lulu-dev-workflow/code/scripts/init.py \
  --project-root "$(pwd)"
```

After init, verify `.cursor/lulu-dev-workflow/workflow-config.json` has the `code` block.
Set `test_command` to the actual test runner command for this project (default: `npm test`).
