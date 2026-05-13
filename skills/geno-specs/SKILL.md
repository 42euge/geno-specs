---
name: geno-specs
description: >-
  Structured execution specs for coding agents and dev loops.
  Use when user says /geno-specs-create, /geno-specs-run,
  /geno-specs-list, /geno-specs-validate, or /geno-specs-show.
license: MIT
metadata:
  author: 42euge
  version: "0.1.0"
---

# geno-specs — Execution Specs for Agents

Create, manage, and execute structured specs that agents (`/geno-agents`) or dev loops (`/geno-dev`) can pick up and run autonomously. Specs go beyond tasks — they define inputs, outputs, steps, and machine-checkable validation criteria.

## Commands

| Command | Description |
|---|---|
| `/geno-specs-create [title]` | Create a new spec (interactive or from template) |
| `/geno-specs-run [spec-id]` | Pick up a spec, render its agent prompt, and execute it |
| `/geno-specs-list` | List specs with optional status/tag filters |
| `/geno-specs-show [spec-id]` | Show a spec's full contents or render as agent prompt |
| `/geno-specs-validate [spec-id]` | Run a spec's completion checks (output existence, commands) |

## Spec Lifecycle

```
draft → ready → running → done
                       → failed → ready (retry)
Any state → abandoned
```

## Spec Format

YAML frontmatter + markdown body. Frontmatter carries machine-readable metadata (inputs, outputs, checks, agent requirements). Body carries human/agent-readable instructions (context, steps, acceptance criteria).

## Integration

- **geno-notes**: Specs can reference geno-notes tasks. A spec is the execution blueprint; a task is the tracking item.
- **geno-agents**: Agents pick up `ready` specs via `geno-specs list --status ready --json` and execute them.
- **geno-dev**: Dev loops iterate over specs via `geno-specs run <id>` which renders the agent prompt.

## Runtime

Python CLI: `geno-specs` (installed via pipx or editable install).
