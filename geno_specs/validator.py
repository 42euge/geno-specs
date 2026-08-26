"""Shared spec validation logic — output checks + validation commands.

Extracted from `cli.validate` so both the CLI and the MCP server run the
exact same checks (single source of truth).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from geno_specs.models import Spec


def run_checks(spec: Spec) -> tuple[int, int, list[str]]:
    """Run a spec's output checks + shell checks.

    Returns (passed, failed, lines) where `lines` are human-readable
    PASS/FAIL/SKIP report lines (no trailing summary line included).
    """
    passed = 0
    failed = 0
    lines: list[str] = []

    for out in spec.outputs:
        p = Path(out.path)
        if not p.exists():
            lines.append(f"  FAIL  output missing: {out.path}")
            failed += 1
            continue
        if out.check:
            content = p.read_text(encoding="utf-8", errors="replace")
            if out.check.startswith("contains "):
                needle = out.check[9:].strip().strip('"').strip("'")
                if needle in content:
                    lines.append(f"  PASS  {out.path}: contains {needle!r}")
                    passed += 1
                else:
                    lines.append(f"  FAIL  {out.path}: missing {needle!r}")
                    failed += 1
            else:
                lines.append(f"  SKIP  {out.path}: unknown check syntax {out.check!r}")
        else:
            lines.append(f"  PASS  {out.path}: exists")
            passed += 1

    for chk in spec.checks:
        try:
            result = subprocess.run(
                chk.run, shell=True, capture_output=True, text=True, timeout=120,
            )
            expect_code = 0
            if chk.expect.startswith("exit "):
                expect_code = int(chk.expect.split()[1])
            if result.returncode == expect_code:
                lines.append(f"  PASS  `{chk.run}` → exit {result.returncode}")
                passed += 1
            else:
                lines.append(
                    f"  FAIL  `{chk.run}` → exit {result.returncode} "
                    f"(expected {expect_code})"
                )
                if result.stderr.strip():
                    for line in result.stderr.strip().splitlines()[:5]:
                        lines.append(f"         {line}")
                failed += 1
        except subprocess.TimeoutExpired:
            lines.append(f"  FAIL  `{chk.run}` → timeout")
            failed += 1

    return passed, failed, lines
