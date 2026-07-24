---
name: geno-specs-wiki
description: >-
  Generate an LLM-wiki from specs — deep, linked per-feature pages that expand
  how each feature should work (behaviour, UI, data flow, conventions,
  acceptance). Use when user says /geno-specs-wiki or wants browsable
  design-doc pages from their specs.
argument-hint: "[--out <dir>] [--spec <id>] [--status <status>]"
license: MIT
metadata:
  author: 42euge
  version: "0.1.0"
observability:
  success_signal: "wiki pages written (index + one deep page per feature)"
  failure_signals:
    - "no specs to render"
    - "spec ID not found"
  knowledge_reads:
    - "all spec files in scope (or one, with --spec)"
  knowledge_writes:
    - "markdown wiki pages under the output dir (default docs/features/)"
---

# Spec Wiki

Turn specs into a linked, deep-dive **LLM-wiki**: one page per feature that
expands the spec's terse fields into readable design-doc prose — behaviour, how
the UI should work, data/state, conventions & gotchas, build, acceptance — plus
an index that groups features by tag and cross-links related specs.

## Input

Optional `$ARGUMENTS`:
- `--out <dir>` — output directory (default `docs/features/`; drops into an MkDocs tree)
- `--spec <id>` — deep page for just one spec (index still written)
- `--status <status>` — only include specs in that status
- `--stdout` — print instead of writing files

## Workflow

```bash
geno-specs wiki                    # all specs -> docs/features/
geno-specs wiki --spec <spec-id>   # one feature's deep page
geno-specs wiki --status ready     # only ready specs
```

Each page is generated from the spec's own content (including free-form
sections like `architecture`, `geno_additions`, `critical_conventions`, `ui`,
`build`), restructured into titled, browsable sections. No LLM call required.

## Completion

```bash
geno-trace emit \
  --skill geno-specs-wiki \
  --status <success|failure> \
  --tool-calls <approximate count> \
  --errors <count> \
  --scope project
```

- `success` = wiki pages written (or printed with --stdout)
- `failure` = no specs found or the named spec ID missing
