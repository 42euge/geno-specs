# geno-specs — Structured Execution Specs

`geno-specs` creates, manages, and validates structured specs — execution blueprints detailed enough for coding agents or dev loops to run autonomously. A spec goes beyond a task: it declares inputs, outputs, steps, validation checks, and agent requirements.

## Skills

| Skill | Slash command | Purpose |
|-------|---------------|---------|
| geno-specs | — | Umbrella |
| geno-specs-create | /geno-specs-create | Interactive spec authoring |
| geno-specs-list | /geno-specs-list | List specs with filters |
| geno-specs-show | /geno-specs-show | Display spec contents |
| geno-specs-run | /geno-specs-run | Execute a spec |
| geno-specs-validate | /geno-specs-validate | Run completion checks |

## Repo structure

```
geno-specs/
├── GENO.md                        # agent instructions (this file)
├── SKILL.md -> skills/geno-specs/SKILL.md
├── CLAUDE.md                      # detailed design docs
├── genotools.yaml                 # install manifest
├── pyproject.toml                 # Python package
├── geno_specs/                    # Python CLI package
│   ├── cli.py                     #   click CLI
│   ├── models.py                  #   Spec dataclass, Status enum
│   ├── loader.py                  #   parse/dump, CRUD, transitions
│   ├── paths.py                   #   scope resolution
│   ├── renderer.py                #   render spec → agent prompt
│   └── templates.py              #   built-in templates
└── skills/
    ├── geno-specs/SKILL.md
    ├── geno-specs-create/SKILL.md
    ├── geno-specs-list/SKILL.md
    ├── geno-specs-show/SKILL.md
    ├── geno-specs-run/SKILL.md
    └── geno-specs-validate/SKILL.md
```

## Entry point

```toml
[project.scripts]
geno-specs = "geno_specs.cli:main"
```

## Spec lifecycle

```
draft → ready → running → done
                       → failed → ready (retry)
Any state → abandoned
```

## Structured failure feedback (`last_failure`)

A `Spec` carries an optional `last_failure` field (`geno_specs.models.Failure`,
holding a `timestamp` and a list of `FailureCheck` records with `kind`
("output" or "check"), `target`, `message`, `stdout`, `stderr`, and
`exit_code`). It closes the loop between a failed `validate` run and the next
`run` after a `failed → ready` retry, so the executing agent sees exactly
what broke instead of starting blind — the same "raw output back into the
prompt" pattern used by Aider and the SWE-bench FAIL_TO_PASS/PASS_TO_PASS
harness.

- **`geno-specs validate`** now captures the full stdout/stderr/exit code of
  every failing output check and validation command (not just pass/fail),
  writes them into `spec.last_failure`, and prints a "why validation failed"
  summary. A clean pass clears any stale `last_failure` left over from a
  previous attempt.
- **`loader.set_failure(scope, spec_id, failure)`** transitions a spec to
  `failed` and persists the `Failure` record in one call — the primitive
  `cli.validate` uses instead of a bare `loader.transition(..., "failed")`.
- **`loader.transition(..., "done")`** clears `last_failure` — a spec that
  finishes has no unresolved failure to carry forward.
- **`renderer.render_prompt`** surfaces `last_failure` (when present) as a
  `## Last failure (<timestamp>)` section at the top of the rendered agent
  prompt, above the spec's own inputs/steps/checks, listing each failed
  check's target, message, and captured stdout/stderr.
- On disk, `last_failure` is plain YAML frontmatter on the spec file
  (`.genospecs.yaml`) — a `last_failure:` mapping with `timestamp` and
  `checks:` — following the same format as every other section (`inputs`,
  `checks`, `agent`, …). It round-trips through `nodes.parse`/`nodes.dump`
  like any other registered section type.
