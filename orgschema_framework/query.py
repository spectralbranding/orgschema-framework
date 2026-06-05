"""Deterministic query interface over an Organizational Schema directory.

This is a plain, deterministic query CLI — there is NO natural-language or
LLM layer. OrgSchema's constraint space is boolean (a contract is satisfied
or it is not; a unit is consumed or it is not), so the appropriate interface
is a deterministic query over the validator's existing level functions rather
than a grounded NL->DSL pipeline.

The CLI re-uses the Level 3 (contract satisfaction) and Level 6 (waste
detection) functions from ``orgschema_framework.validate`` so the query
results are exactly the validator's results — single source of truth.

Usage:
    orgschema-query --schema ./orgschema-demo
    orgschema-query --schema ./orgschema-demo --check contracts
    orgschema-query --schema ./orgschema-demo --check waste --format json
    orgschema-query --schema ./orgschema-demo --level 3

Exit code is 1 if any selected error-severity check (contracts) reports a
violation, else 0 — making it usable in CI alongside ``orgschema-validate``.
"""

import argparse
import json
import sys
from pathlib import Path

from orgschema_framework.validate import (
    validate_contract_satisfaction,
    validate_waste,
)

# Each query maps to (level, severity, function).
# "error" severity affects the exit code; "warning" is advisory.
CHECKS = {
    "contracts": (3, "error", validate_contract_satisfaction),
    "waste": (6, "warning", validate_waste),
}

# Map --level N to the corresponding check name (deterministic queries only
# expose the levels that this module owns: 3 and 6).
LEVEL_TO_CHECK = {3: "contracts", 6: "waste"}


def run_query(root: Path, checks: list[str]) -> dict:
    """Run the requested deterministic checks and return a structured result.

    The returned dict is stable and JSON-serializable:

        {
          "schema": "<abs path>",
          "checks": [
            {"check": "contracts", "level": 3, "severity": "error",
             "violation_count": N, "violations": [..]},
            ...
          ],
          "error_count": <sum of error-severity violations>,
          "warning_count": <sum of warning-severity violations>,
          "ok": <bool: no error-severity violations>
        }
    """
    results = []
    error_count = 0
    warning_count = 0

    for name in checks:
        level, severity, func = CHECKS[name]
        violations = func(root)
        results.append(
            {
                "check": name,
                "level": level,
                "severity": severity,
                "violation_count": len(violations),
                "violations": violations,
            }
        )
        if severity == "error":
            error_count += len(violations)
        else:
            warning_count += len(violations)

    return {
        "schema": str(root),
        "checks": results,
        "error_count": error_count,
        "warning_count": warning_count,
        "ok": error_count == 0,
    }


def format_text(result: dict) -> str:
    """Render a query result as a human-readable structural report."""
    lines = [f"=== OrgSchema deterministic query: {result['schema']} ==="]
    for check in result["checks"]:
        sev = check["severity"].upper()
        header = (
            f"\nLevel {check['level']} — {check['check']} "
            f"({check['violation_count']} {sev} violations)"
        )
        lines.append(header)
        if not check["violations"]:
            lines.append("  PASSED")
        else:
            for v in check["violations"]:
                lines.append(f"  [{sev}] {v}")
    lines.append(
        f"\nSummary: {result['error_count']} errors, "
        f"{result['warning_count']} warnings"
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orgschema-query",
        description=(
            "Deterministic query interface over an OrgSchema directory "
            "(no natural-language / LLM layer)."
        ),
    )
    parser.add_argument(
        "--schema",
        required=True,
        type=Path,
        help="Path to the orgschema specifications directory.",
    )
    parser.add_argument(
        "--check",
        choices=sorted(CHECKS) + ["all"],
        default="all",
        help="Which deterministic check(s) to run (default: all).",
    )
    parser.add_argument(
        "--level",
        type=int,
        choices=sorted(LEVEL_TO_CHECK),
        help="Run a single validation level by number (3=contracts, 6=waste). "
        "Overrides --check when given.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = args.schema.resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        return 2

    if args.level is not None:
        checks = [LEVEL_TO_CHECK[args.level]]
    elif args.check == "all":
        checks = sorted(CHECKS)
    else:
        checks = [args.check]

    result = run_query(root, checks)

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
