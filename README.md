# geno-specs

[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://42euge.github.io/geno-specs/)

Structured execution specs for coding agents and dev loops. Part of the [geno ecosystem](https://github.com/42euge/geno-tools).

## What's a spec?

A spec is a structured execution blueprint — it has inputs, outputs, steps, and machine-checkable validation criteria. Agents pick up specs and execute them autonomously. Dev loops iterate over ready specs.

Think of it as the difference between:
- **Task**: "Fix the auth bug"
- **Spec**: Read `src/auth.py`, add token refresh with backoff, create tests, run `pytest` → exit 0

## Install

```bash
pipx install geno-specs
# or via geno-tools:
geno-tools install specs
```

## Quick start

```bash
# Create a spec from a template
geno-specs create "Fix token refresh" --template bug-fix --tag auth

# Fill in details
geno-specs edit 20260426-fix-token-refresh \
  --add-input "src/auth.py:Auth module" \
  --add-output "src/auth.py:contains TokenRefresher" \
  --add-check "pytest tests/test_auth.py"

# Mark ready for agents
geno-specs ready 20260426-fix-token-refresh

# Execute (renders agent prompt + transitions to running)
geno-specs run 20260426-fix-token-refresh

# Validate completion
geno-specs validate 20260426-fix-token-refresh

# Mark done
geno-specs done 20260426-fix-token-refresh
```

## Project scaffolding

```bash
# Scaffold .specs/ with placeholder VISION.md, TENETS.md, GOALS.md, features/
geno-specs init

# Same, but draft real starter content from README.md + recent git log
# instead of bare placeholders (existing files are never overwritten)
geno-specs init --fill
```

`--fill` is a heuristic draft, not an LLM call: it pulls your README's opening
description into VISION's "Why this exists", summarizes the last ~15 commit
subjects into GOALS "Active", and seeds TENETS with two generic starter
principles. Every filled file is marked `> DRAFT` at the top — read and edit
before trusting it.

## Templates

| Template | Description |
|---|---|
| `bug-fix` | Fix a bug: reproduce, root-cause, patch, verify |
| `feature` | Add a new feature end-to-end |
| `refactor` | Restructure code without changing behavior |
| `migration` | Data, schema, or API migration |
| `test` | Add or improve test coverage |
| `review` | Code review with structured feedback |

## License

MIT
