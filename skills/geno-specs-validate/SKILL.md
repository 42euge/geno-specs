---
name: geno-specs-validate
description: >-
  Run a spec's completion checks — verify outputs exist and validation commands pass.
  Use when user says /geno-specs-validate.
argument-hint: "<spec-id>"
license: MIT
metadata:
  author: 42euge
  version: "0.1.0"
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
---

# Validate Spec

Check whether a spec's completion criteria are met.

## Input

`$ARGUMENTS` is the spec ID.

## Workflow

```bash
geno-specs validate <spec-id>
```

This runs three categories of checks, each tagged in the output:

1. **Output checks** (`[output]`) — verify expected output files exist and satisfy their content checks (e.g., `contains "class Foo"`)
2. **must_pass checks** (`[must_pass]`) — the change's own validation commands, which must newly succeed (e.g., `pytest tests/test_new.py` → exit 0). This is the same list as the legacy flat `checks:` field.
3. **must_not_regress checks** (`[must_not_regress]`) — commands that were passing before the change and must still pass after it. A failure here is flagged as a `REGRESSION`, distinct from an unfinished must_pass check.

Add `--json` for a structured `{check: {category, passed, output}}` breakdown instead of (or alongside reading) the human-readable log.

Report results, distinguishing "the change isn't done yet" (must_pass failures) from "the change broke something that worked before" (must_not_regress regressions). If all pass and the spec is in `running` status, suggest marking it done:
```bash
geno-specs done <spec-id>
```

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
