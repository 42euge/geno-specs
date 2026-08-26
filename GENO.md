# geno-specs — Structured Execution Specs

`geno-specs` creates, manages, and validates structured specs — execution blueprints detailed enough for coding agents or dev loops to run autonomously. A spec goes beyond a task: it declares inputs, outputs, steps, validation checks, and agent requirements.

## Validation checks: must_pass / must_not_regress

Validation checks are split into two named pass-lists (SWE-bench-style
FAIL_TO_PASS / PASS_TO_PASS):

- `checks` (on-disk key, kept for backward compat) / `must_pass` — checks
  that must newly succeed. `Spec.must_pass` is a property alias for
  `Spec.checks`; they are the same list.
- `must_not_regress` — checks that were passing before the change and must
  still pass after it. A failure here is a regression, not unfinished work.

`geno-specs edit --add-check ...` still appends to `must_pass`/`checks`;
`--add-must-not-regress ...` appends to the new list. `geno-specs validate`
runs both categories and reports each failure tagged with its category
(`[must_pass]` or `[must_not_regress]`); `--json` emits a
`{check: {category, passed, output}}` breakdown. Spec files with only the
legacy flat `checks:` field load and validate exactly as before — nothing
about existing spec files changes.

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
