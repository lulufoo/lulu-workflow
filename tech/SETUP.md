# tech-doc-workflow — Setup

## `install` — Machine-level, run once

```bash
mkdir -p ~/.cursor/skills/lulu-dev-workflow/tech/scripts

for f in SKILL.md transition-whitelist.json; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/tech/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/tech/$f
done

for f in workflow_common.py hook_guard.py start.py init.py; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/tech/scripts/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/tech/scripts/$f
done
```

After install, run `tech-doc-workflow init` in the target project.

---

## `init` — Project-level, run once per project

Registers the tech hook into `.cursor/hooks.json` and ensures `workflow-config.json`
has a `tech` section.

```bash
cd <project-root>
python3 ~/.cursor/skills/lulu-dev-workflow/tech/scripts/init.py \
  --project-root "$(pwd)"
```

After init, verify `.cursor/lulu-dev-workflow/workflow-config.json` has the `tech`
block. Fill in `ac_url` if an architecture-constraints document exists.
