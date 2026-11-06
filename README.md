<p align="center">
  <img src="docs/readme/logo.png" width="160" alt="Lulu Workflow" />
</p>

<h1 align="center">Lulu Workflow</h1>

<p align="center"><b>A staged development workflow for AI coding agents.</b></p>

<p align="center">
  <a href="https://lulufoo.github.io/interview/lulu-workflow.html"><img src="https://img.shields.io/badge/docs-architecture-green.svg?style=flat-square" alt="Architecture" align="absmiddle"></a>
  &nbsp;
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square" alt="License" align="absmiddle"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/status-Beta%20v1.0-orange.svg?style=flat-square" alt="Status: Beta v1.0" align="absmiddle">
</p>

---

## Why

An agent asked to "build the feature" jumps straight to code. Lulu Workflow slows that down on purpose: it puts a named stage between each decision and the next, so product intent, technical choices, design, plan, and code each get settled and delivered before the next begins. You choose every step.

## How it works

- A **cycle** is one run of the workflow, and it is one of two types. A **topic** cycle settles product and technical decisions and ends with a ticket dependency graph for the work they imply. A **feature** cycle carries one feature through to code, and can optionally be linked to a topic.
- A **stage** is one named step in a cycle, with one job.
- A **delivered artifact** is what a stage hands to the next one. A stage is done when it has delivered, and the next stage starts from that artifact.

## The two lines

Both lines start at `lulu-brainstorm` and pass through a product decision (`lulu-bet`) and a technical decision (`lulu-approach`). The topic line runs them in sequence and stops there. The feature line runs them as two tracks and carries on to code.

### Topic line

<img src="docs/readme/topic-line.svg" alt="Topic line: lulu-brainstorm leads to lulu-bet, then lulu-approach, which delivers a ticket dependency graph" width="504" />

- `lulu-approach` follows `lulu-bet` and ends the line. It delivers a ticket dependency graph for the work the topic implies. A ticket is a workflow work item sized for an issue. Producing the graph creates no issues.

### Feature line

<img src="docs/readme/feature-line.svg" alt="Feature line: lulu-brainstorm splits into lulu-bet then lulu-spec, and lulu-approach then lulu-design; both join at lulu-plan, then lulu-tasks and lulu-exec" width="952" />

- The product and technical tracks have no order between them. They join at `lulu-plan`.
- On both lines, `lulu-bet` is the recommended start for full-feature work. Purely technical work can start at `lulu-approach`.
- A change that needs no plan can go from `lulu-approach` straight to `lulu-tasks`.

## Stages

| Stage | Key | Line | What it does | Needs | Produces |
|---|---|---|---|---|---|
| [`lulu-brainstorm`](./lulu-brainstorm/SKILL.md) | — | topic, feature (entry) | Divergent thinking before a problem is defined. Surfaces your framing and tests which constraints are real | nothing | A mirror summary of what opened. No ranking |
| [`lulu-bet`](./lulu-bet/SKILL.md) | `pd` | topic, feature | Product decision | — | Product decision package |
| [`lulu-spec`](./lulu-spec/SKILL.md) | `ps` | feature | Product doc for a feature | Delivered `lulu-bet` | Product doc |
| [`lulu-approach`](./lulu-approach/SKILL.md) | `td` | topic, feature | Technical decision | — | Tech decision package. On a topic, it includes a ticket dependency graph |
| [`lulu-design`](./lulu-design/SKILL.md) | `ds` | feature | Design doc for a feature | Delivered `lulu-approach` | Design doc |
| [`lulu-plan`](./lulu-plan/SKILL.md) | `t` | feature | Implementation-ready plan | Delivered `lulu-spec` and `lulu-design` | Plan doc |
| [`lulu-tasks`](./lulu-tasks/SKILL.md) | `w` | feature | Splits the plan, or the approach decision when no plan is delivered, into independently executable tasks | Delivered `lulu-plan` or `lulu-approach` | Work order: a task-dependency list |
| [`lulu-exec`](./lulu-exec/SKILL.md) | `c` | feature | Executes the work order | Delivered work order | Delivered code and task receipts |

## Platforms

Cursor, GitHub Copilot, Claude Code, and Codex.

Session hooks and state are platform-neutral, and each platform gets its own adapter. Lulu Workflow has no dependency on other Lulu skill packs or on an issue tracker.

## Architecture

This README covers the first layer of the [architecture map](https://lulufoo.github.io/interview/lulu-workflow.html), Workflow Collaboration. The layers beneath it are Harness Engineering, Domain Modeling, the SKILL design paradigm, and the cognition about AI collaboration that drives the design. The map covers them.

## License

[MIT](./LICENSE)
