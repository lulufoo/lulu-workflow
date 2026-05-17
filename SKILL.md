---
name: lulu-dev-workflow
description: >-
  Top-level development workflow framework. Use when mentioning lulu-dev-workflow,
  开发工作流, dev workflow, product doc workflow, 产品文档流程, or any sub-stage
  (product, tech, qa, deploy).
disable-model-invocation: true
---

# lulu-dev-workflow

A staged development workflow framework. Each stage is an independent sub-module
under this directory.

## Stages

| Stage | Module | Status |
|-------|--------|--------|
| Product documentation | `product/` | Active |
| Tech design | `tech/` | Active |
| Work order | `work-order/` | Active |
| Code | `code/` | Active |

## Commands

### `configure` — Download and apply a workflow-config.json from GitHub

Usage: `lulu-dev-workflow configure <github-blob-url>`

`<github-blob-url>` is a GitHub `blob` URL pointing to a `workflow-config.json`, e.g.:

```
https://github.com/lulufoo/ai-software-dev/blob/main/lulu-dev-workflow-template/workflow-config.json
```

Parse the URL to extract `owner`, `repo`, `ref`, `path`, then run:

```bash
gh api "repos/{owner}/{repo}/contents/{path}?ref={ref}" \
  --jq '.content' | base64 -d \
  > .cursor/lulu-dev-workflow/workflow-config.json
```

After download, read and display the new `.cursor/lulu-dev-workflow/workflow-config.json` to confirm.

**Default template URL** (lulufoo standard config):
```
https://github.com/lulufoo/ai-software-dev/blob/main/lulu-dev-workflow-template/workflow-config.json
```

## Usage

Each stage has its own `SKILL.md` with install / init / start commands.

- **Product doc:** read `~/.cursor/skills/lulu-dev-workflow/product/SKILL.md`
- **Tech design:** read `~/.cursor/skills/lulu-dev-workflow/tech/SKILL.md`
- **Work order:** read `~/.cursor/skills/lulu-dev-workflow/work-order/SKILL.md`
- **Code:** read `~/.cursor/skills/lulu-dev-workflow/code/SKILL.md`
