---
name: geno-specs-validate
description: >-
  Run a spec's completion checks — verify outputs exist and validation commands pass.
  Use when user says /geno-specs-validate.
argument-hint: "<spec-id>"
license: MIT
metadata:
  author: 42euge
  version: "0.2.0"
observability:
  success_signal: "all output checks and validation commands passed"
  failure_signals:
    - "one or more output checks failed"
    - "validation command returned non-zero exit code"
    - "spec ID not found"
  knowledge_reads:
    - "spec file (outputs and checks definitions)"
    - "output files referenced by the spec"
  knowledge_writes:
    - "spec status transition (running → done, if all checks pass and user confirms)"
    - "spec status transition (running → failed, with a structured last_failure record, if any check fails)"
---

# Validate Spec

Check whether a spec's completion criteria are met.

## Input

`$ARGUMENTS` is the spec ID.

## Workflow

```bash
geno-specs validate <spec-id>
```

This runs two categories of checks:

1. **Output checks** — verify expected output files exist and satisfy their content checks (e.g., `contains "class Foo"`)
2. **Validation commands** — run shell commands and check exit codes (e.g., `pytest` → exit 0)

On failure, the full stdout/stderr/exit code of every failing check is captured
into the spec's `last_failure` field (not just pass/fail), and a "why
validation failed" summary is printed. That structured record carries forward
into the next `geno-specs run` after a `failed → ready` retry — the retrying
agent sees exactly what broke last time instead of starting blind. A clean
pass clears any stale `last_failure` from a previous attempt.

Report results. If all pass and the spec is in `running` status, suggest marking it done:
```bash
geno-specs done <spec-id>
```
(`done` also clears `last_failure` — a finished spec has no unresolved failure to carry forward.)

## Completion

When this skill finishes (success or failure), emit a trace:

```bash
geno-trace emit \
  --skill geno-specs-validate \
  --status <success|failure> \
  --tool-calls <approximate count> \
  --errors <count of tool/command errors> \
  --scope project
```

- `success` = all output checks and validation commands passed
- `failure` = one or more checks failed or spec ID not found
