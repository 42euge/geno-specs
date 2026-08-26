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

## First run

On a fresh install there are no specs yet. `geno-specs demo` seeds one fully-filled example spec (id `demo-http-retry-backoff`, tagged `demo`) so `geno-specs list`/`show` are never empty on first use. `geno-specs demo --remove` deletes it again.
