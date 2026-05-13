---
name: geno-specs-show
description: >-
  Show a spec's full contents, as JSON, or as an agent-executable prompt.
  Use when user says /geno-specs-show.
argument-hint: "<spec-id> [--prompt|--json]"
license: MIT
metadata:
  author: 42euge
  version: "0.1.0"
observability:
  success_signal: "spec contents displayed in requested format"
  failure_signals:
    - "spec ID not found or ambiguous"
    - "geno-specs show command failed"
  knowledge_reads:
    - "spec file (YAML frontmatter + markdown body)"
  knowledge_writes: []
---

# Show Spec

Display a spec's contents in the requested format.

## Input

`$ARGUMENTS` is the spec ID, optionally followed by `--prompt` or `--json`.

## Workflow

```bash
geno-specs show <spec-id> [--prompt] [--json]
```

- Default: show the raw spec file (YAML frontmatter + markdown body)
- `--prompt`: render as a self-contained agent prompt (what an agent would receive)
- `--json`: structured JSON for machine consumption

## Completion

When this skill finishes (success or failure), emit a trace:

```bash
geno-trace emit \
  --skill geno-specs-show \
  --status <success|failure> \
  --tool-calls <approximate count> \
  --errors <count of tool/command errors> \
  --scope project
```

- `success` = spec contents displayed in the requested format
- `failure` = spec ID not found, ambiguous match, or show command failed
