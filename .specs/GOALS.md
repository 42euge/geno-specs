# Goals

Current goals for geno-specs. Review and update regularly.

## Active

- <!-- Goal 1: description, target date -->
- **Support multi-repo / phased / architecture specs** — added optional `composes`, `phases`,
  `open_questions`, and `deferred` fields to `FEATURE_TEMPLATE` in `geno_specs/scaffold.py`
  (2026-07-15) so an ecosystem-layer design (e.g. the ADW layer: geno-adw/geno-rev/geno-grams) can
  be expressed as one spec. Simple single-feature specs omit them. TODO: mirror these fields in
  `models.py`/loader validation once the incomplete Python package (currently only `cli.py` +
  `scaffold.py` on disk, though GENO.md documents models/loader/renderer/templates) is filled in.

## Completed

- <!-- Moved here when done -->

## Deferred

- <!-- Moved here when deprioritized -->
