---
name: geno-specs-run
description: >-
  Pick up a spec, render its agent prompt, and execute it.
  Use when user says /geno-specs-run.
argument-hint: "[spec-id or pattern]"
license: MIT
metadata:
  author: 42euge
  version: "0.1.0"
observability:
  success_signal: "spec executed and all validation checks passed, marked done"
  failure_signals:
    - "validation checks failed after execution"
    - "dependency specs not in done state"
    - "spec marked failed after unrecoverable error"
  knowledge_reads:
    - "spec file (inputs, steps, outputs, checks)"
    - "dependency specs (depends_on entries)"
    - "input files listed in the spec"
  knowledge_writes:
    - "output files listed in the spec"
    - "spec status transition (ready → running → done/failed)"
---

# Run Spec

Pick up a `ready` spec and execute it as the current agent.

## Input

`$ARGUMENTS` is the spec ID or a fuzzy pattern. If empty, show ready specs and ask which to run.

## Workflow

### 1. Select the spec

If `$ARGUMENTS` is provided:
```bash
geno-specs show "$ARGUMENTS" --json
```

If empty, list ready specs:
```bash
geno-specs list --status ready --json
```
Then use `AskUserQuestion` to let the user pick one.

### 2. Check dependencies

If the spec has `depends_on` entries, verify those specs are `done`:
```bash
geno-specs show <dep-id> --json
```
If any dependency is not done, warn the user and ask whether to proceed anyway.

### 3. Transition to running

```bash
geno-specs run <spec-id>
```

This prints the rendered agent prompt. Read it to understand the full task.

### 4. Execute

Work through the spec's steps:
1. Read the input files listed in the spec
2. Follow the steps in order
3. Create/modify the output files as specified
4. After each major step, check if the acceptance criteria are being met

### 5. Validate

When you believe the work is complete, run validation:
```bash
geno-specs validate <spec-id>
```

Review the results. If all checks pass, mark done:
```bash
geno-specs done <spec-id>
```

If checks fail, fix the issues and re-validate. If the spec cannot be completed, mark failed:
```bash
geno-specs fail <spec-id>
```

### 6. Report

Summarize what was done, what passed, and any issues encountered.

## Loop Integration

When called from a `/geno-dev` loop or `/geno-agents` supercharge cycle, this skill can process multiple specs in sequence. The loop driver selects specs via `geno-specs list --status ready --json` and calls this skill for each.

## Completion

When this skill finishes (success, failure, or abandoned), emit a trace:

```bash
geno-trace emit \
  --skill geno-specs-run \
  --status <success|failure|abandoned> \
  --tool-calls <approximate count> \
  --errors <count of tool/command errors> \
  --scope project \
  --produced "<list of output files created/modified>"
```

- `success` = spec executed, all validation checks passed, marked done
- `failure` = validation checks failed after execution or spec marked failed
- `abandoned` = user stopped execution before completion or dependency check blocked
