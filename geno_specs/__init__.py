"""geno-specs — structured execution specs for coding agents and dev loops.

A spec is a recursive tree of typed section nodes (see `nodes.py`). The flat
`Spec` dataclass (see `models.py`) is the ergonomic surface the CLI mutates;
`loader` bridges between the two.
"""

from __future__ import annotations

__version__ = "0.2.0"

# Bump when the on-disk .genospecs.yaml schema changes in a breaking way.
SCHEMA_VERSION = 1
