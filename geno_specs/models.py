"""Domain objects — typed leaves and the flat `Spec` surface.

House style: pure `@dataclass` data holders, zero behavior. All verbs live in
free functions (here `to_dict`, elsewhere `loader`/`nodes`/`renderer`).

The canonical internal form of a spec is the `Node` tree (`nodes.py`). `Spec`
is a flat, mutable view the CLI reads and mutates in place (e.g.
`spec.inputs.append(...)`); `loader.spec_to_node` / `node_to_spec` bridge the
two. Section types that have no flat attribute (composes, phases,
open_questions, deferred, depends_on, subspec) ride along in `children_extra`
as raw `Node`s so they survive a load→save round-trip untouched.

This module must NOT import `nodes` (avoids an import cycle — `nodes` may
reference the leaf types here, not vice versa).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime import
    from geno_specs.nodes import Node


# ─── lifecycle ────────────────────────────────────────────────────────

VALID_STATUSES: set[str] = {
    "draft",
    "ready",
    "running",
    "done",
    "failed",
    "abandoned",
}


# ─── typed leaves ─────────────────────────────────────────────────────


@dataclass
class InputFile:
    """A file the agent should read, with a human description of its role."""

    path: str
    role: str = ""


@dataclass
class OutputFile:
    """An expected output file + an optional content assertion.

    `check` grammar (evaluated in cli.validate / nodes validate):
      - ""                    → existence only
      - "contains <needle>"   → substring assertion
    """

    path: str
    check: str = ""


@dataclass
class Check:
    """A shell validation command + expected result.

    `expect` grammar: "exit <N>" (defaults to "exit 0").
    """

    run: str
    expect: str = "exit 0"


@dataclass
class AgentRequirements:
    """What the executing agent needs — capabilities and a preferred model."""

    capabilities: list[str] = field(default_factory=list)
    model: str | None = None


@dataclass
class FailureCheck:
    """One failed check/output assertion captured during `validate`.

    `kind` is "output" or "check" (mirrors the two categories `cli.validate`
    runs). `target` is the output path or the shell command. `stdout`/`stderr`
    are the exact captured text; `exit_code` is None for output checks (they
    don't run a subprocess).
    """

    kind: str
    target: str
    message: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None


@dataclass
class Failure:
    """A structured record of why a spec's last `validate` run failed.

    Persisted on the Spec as `last_failure` so the next `run` (after a
    failed → ready retry) can show the executing agent exactly what broke,
    instead of starting blind. Cleared when the spec reaches `done`.
    """

    timestamp: str
    checks: list[FailureCheck] = field(default_factory=list)


# ─── the flat Spec surface ────────────────────────────────────────────


@dataclass
class Spec:
    """Flat, mutable view of a spec.

    The attribute set is fixed by the CLI contract (`cli.py`). Section types
    without a flat home live in `children_extra`.
    """

    id: str
    title: str
    status: str = "draft"
    tags: list[str] = field(default_factory=list)
    context: str = ""
    template: str | None = None
    steps: list[str] = field(default_factory=list)
    acceptance: list[str] = field(default_factory=list)
    inputs: list[InputFile] = field(default_factory=list)
    outputs: list[OutputFile] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    agent: AgentRequirements = field(default_factory=AgentRequirements)
    # Structured record of the most recent failed `validate` run (None once
    # the spec has never failed, or after it reaches `done`).
    last_failure: Failure | None = None
    # Section nodes the flat view has no attribute for (composes, phases,
    # open_questions, deferred, depends_on, subspec, raw). Preserved verbatim
    # across load→save so unknown/extended content is never dropped.
    children_extra: list["Node"] = field(default_factory=list)


# ─── serialization helpers ────────────────────────────────────────────


def _input_to_dict(x: InputFile) -> dict[str, Any]:
    return {"path": x.path, "role": x.role}


def _output_to_dict(x: OutputFile) -> dict[str, Any]:
    return {"path": x.path, "check": x.check}


def _check_to_dict(x: Check) -> dict[str, Any]:
    return {"run": x.run, "expect": x.expect}


def _agent_to_dict(x: AgentRequirements) -> dict[str, Any]:
    return {"capabilities": list(x.capabilities), "model": x.model}


def _failure_check_to_dict(x: FailureCheck) -> dict[str, Any]:
    return {
        "kind": x.kind,
        "target": x.target,
        "message": x.message,
        "stdout": x.stdout,
        "stderr": x.stderr,
        "exit_code": x.exit_code,
    }


def _failure_to_dict(x: "Failure | None") -> dict[str, Any] | None:
    if x is None:
        return None
    return {
        "timestamp": x.timestamp,
        "checks": [_failure_check_to_dict(c) for c in x.checks],
    }


def to_dict(spec: Spec) -> dict[str, Any]:
    """Flat JSON-able mirror of a Spec (the machine view).

    `renderer.render_json` augments this with a nested ``tree`` key built from
    the Node form; this function stays flat and dependency-free.
    """

    d: dict[str, Any] = {
        "id": spec.id,
        "title": spec.title,
        "status": spec.status,
        "tags": list(spec.tags),
        "context": spec.context,
        "template": spec.template,
        "steps": list(spec.steps),
        "acceptance": list(spec.acceptance),
        "inputs": [_input_to_dict(i) for i in spec.inputs],
        "outputs": [_output_to_dict(o) for o in spec.outputs],
        "checks": [_check_to_dict(c) for c in spec.checks],
        "agent": _agent_to_dict(spec.agent),
        "last_failure": _failure_to_dict(spec.last_failure),
    }
    # Fold extra section nodes in by type so the flat view stays informative.
    for node in spec.children_extra:
        payload = node.data.get("items", node.data)
        d.setdefault(node.type, _plain(payload))
    return d


def _plain(value: Any) -> Any:
    """Convert dataclass leaves to plain JSON-able data (recursive)."""
    import dataclasses

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _plain(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value
