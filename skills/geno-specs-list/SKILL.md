---
name: geno-specs-list
description: >-
  List specs with optional status and tag filters.
  Use when user says /geno-specs-list.
argument-hint: "[--status ready] [--tag feature]"
license: MIT
metadata:
  author: 42euge
  version: "0.1.0"
observability:
  success_signal: "spec listing displayed (or empty list with suggestion)"
  failure_signals:
    - "geno-specs list command failed"
    - "no scope directory found"
  knowledge_reads:
    - "spec files in active scope (project or global)"
  knowledge_writes: []
---

# List Specs

Show all specs in the active scope with optional filters.

## Input

`$ARGUMENTS` can contain filter flags:
- `--status <status>` or just `ready`, `draft`, `running`, `done`, `failed`
- `--tag <tag>`
- `--json` for machine-readable output

## Workflow

Parse `$ARGUMENTS` for any filters, then run:

```bash
geno-specs list [--status STATUS] [--tag TAG] [--json]
```

Display the results. If the list is empty, suggest creating a spec with `/geno-specs-create`.

## Completion

When this skill finishes (success, failure, or abandoned), emit a trace:

```bash
geno-trace emit \
  --skill geno-specs-list \
  --status <success|failure> \
  --tool-calls <approximate count> \
  --errors <count of tool/command errors> \
  --scope project
```

- `success` = spec listing displayed (including empty lists with suggestion)
- `failure` = list command failed or no scope directory found
