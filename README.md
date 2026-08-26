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
  --add-check "pytest tests/test_auth.py" \
  --add-must-not-regress "pytest tests/test_session.py"

# Mark ready for agents
geno-specs ready 20260426-fix-token-refresh

# Execute (renders agent prompt + transitions to running)
geno-specs run 20260426-fix-token-refresh

# Validate completion
geno-specs validate 20260426-fix-token-refresh

# Mark done
geno-specs done 20260426-fix-token-refresh
```

## Checks: must_pass vs must_not_regress

Validation checks are split into two named pass-lists, following the
FAIL_TO_PASS / PASS_TO_PASS distinction from SWE-bench — a regression
contract instead of one undifferentiated pass/fail blob:

- **`must_pass`** — checks that must newly start passing (the change is
  incomplete until these succeed). This is the same field as the original
  flat `checks:` — it's still supported and behaves identically; `checks`
  and `must_pass` are the same list under the hood.
- **`must_not_regress`** — checks that were passing *before* the change and
  must still pass *after* it. A failure here means the change broke
  something that already worked, not that the change is unfinished.

```bash
geno-specs edit 20260426-fix-token-refresh \
  --add-check "pytest tests/test_auth.py::test_refresh"        # must_pass
  --add-must-not-regress "pytest tests/test_auth.py::test_login"  # must_not_regress

geno-specs validate 20260426-fix-token-refresh
#   PASS  [must_pass]         `pytest tests/test_auth.py::test_refresh` → exit 0
#   FAIL  [must_not_regress]  `pytest tests/test_auth.py::test_login` → REGRESSION: exit 1 (expected 0)
#
# 1 passed, 1 failed (0 must_pass failures, 1 regressions)
```

Old spec files that only have the flat `checks:` field keep working
unmodified — they're loaded as `must_pass` with an empty
`must_not_regress`. Add `--json` to `validate` for a machine-readable
breakdown keyed by check, each with `category` (`output` / `must_pass` /
`must_not_regress`), `passed`, and `output`.

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
