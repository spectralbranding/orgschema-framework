"""Organizational Schema Theory YAML schema validator.

Implements the first two levels of the 6-level CI/CD validation pipeline:
1. Schema validation — "Is this valid YAML with required fields?"
2. Cross-reference integrity — "Do all linked specs exist and are consistent?"

Usage:
    orgschema-validate /path/to/orgschema-demo
    python -m orgschema_framework.validate /path/to/orgschema-demo
"""

import datetime
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, ValidationError

SCHEMA_DIR = Path(__file__).parent / "schemas"

# Map directory/file patterns to their schema
SCHEMA_MAP = {
    "organization.yaml": "organization.json",
    "products/": "product.json",
    "processes/": "process.json",
    "compliance/": "compliance.json",
}


def normalize_yaml_data(data):
    """Convert YAML-parsed date objects to ISO strings for JSON Schema validation."""
    if isinstance(data, dict):
        return {k: normalize_yaml_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [normalize_yaml_data(item) for item in data]
    if isinstance(data, (datetime.date, datetime.datetime)):
        return data.isoformat()
    return data


def load_schema(schema_name: str) -> dict:
    schema_path = SCHEMA_DIR / schema_name
    with open(schema_path) as f:
        return json.load(f)


def get_schema_for_file(filepath: Path, root: Path) -> str | None:
    rel = str(filepath.relative_to(root))
    for pattern, schema in SCHEMA_MAP.items():
        if rel == pattern or rel.startswith(pattern):
            return schema
    return None


def validate_schema(root: Path) -> list[str]:
    """Level 1: Schema validation — validate all YAML against JSON schemas."""
    errors = []
    yaml_files = sorted(root.glob("**/*.yaml"))

    for filepath in yaml_files:
        if ".github" in str(filepath):
            continue

        # Parse YAML
        try:
            with open(filepath) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            errors.append(f"YAML parse error in {filepath.relative_to(root)}: {e}")
            continue

        if data is None:
            continue

        data = normalize_yaml_data(data)

        # Find matching schema
        schema_name = get_schema_for_file(filepath, root)
        if schema_name is None:
            continue

        schema = load_schema(schema_name)
        validator = Draft202012Validator(schema)

        for error in validator.iter_errors(data):
            path = ".".join(str(p) for p in error.absolute_path)
            loc = f" at {path}" if path else ""
            errors.append(
                f"Schema error in {filepath.relative_to(root)}{loc}: "
                f"{error.message}"
            )

    return errors


def validate_cross_references(root: Path) -> list[str]:
    """Level 2: Cross-reference integrity — check that linked specs exist."""
    errors = []
    yaml_files = sorted(root.glob("**/*.yaml"))

    # Collect all signal requirement IDs
    signal_req_ids = set()
    experience_test_ids = set()

    # Load signal requirements
    sig_req_path = root / "perception" / "signal_requirements.yaml"
    if sig_req_path.exists():
        with open(sig_req_path) as f:
            sig_data = yaml.safe_load(f)
        if sig_data and "signal_requirements" in sig_data:
            for req in sig_data["signal_requirements"]:
                signal_req_ids.add(req["id"])

    # Load experience contract
    exp_path = root / "perception" / "customer_experience_contract.yaml"
    if exp_path.exists():
        with open(exp_path) as f:
            exp_data = yaml.safe_load(f)
        if exp_data and "experience_contract" in exp_data:
            for dimension, content in exp_data["experience_contract"].items():
                if isinstance(content, dict) and "tests" in content:
                    for test in content["tests"]:
                        experience_test_ids.add(test["id"])

    # Check cross-references in all files
    for filepath in yaml_files:
        if ".github" in str(filepath):
            continue

        try:
            with open(filepath) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError:
            continue

        if data is None:
            continue

        rel = str(filepath.relative_to(root))

        # Check satisfies_signal references
        if "satisfies_signal" in data:
            for ref in data["satisfies_signal"]:
                if ref not in signal_req_ids:
                    errors.append(
                        f"Broken cross-ref in {rel}: "
                        f"satisfies_signal '{ref}' not found in "
                        f"signal_requirements.yaml"
                    )

        # Check satisfies_experience references
        if "satisfies_experience" in data:
            for ref in data["satisfies_experience"]:
                if ref not in experience_test_ids:
                    errors.append(
                        f"Broken cross-ref in {rel}: "
                        f"satisfies_experience '{ref}' not found in "
                        f"customer_experience_contract.yaml"
                    )

    return errors


def validate_signal_coverage(root: Path) -> list[str]:
    """Level 4: Signal coverage — are all signal requirements satisfied?"""
    warnings = []

    # Load signal requirements
    sig_req_path = root / "perception" / "signal_requirements.yaml"
    if not sig_req_path.exists():
        return ["signal_requirements.yaml not found"]

    with open(sig_req_path) as f:
        sig_data = yaml.safe_load(f)

    if not sig_data or "signal_requirements" not in sig_data:
        return ["No signal_requirements found"]

    all_signal_ids = {req["id"] for req in sig_data["signal_requirements"]}
    referenced_signals = set()

    # Collect all satisfies_signal references across the demo
    for filepath in sorted(root.glob("**/*.yaml")):
        if ".github" in str(filepath):
            continue
        try:
            with open(filepath) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError:
            continue
        if data and "satisfies_signal" in data:
            referenced_signals.update(data["satisfies_signal"])

    # Also check implemented_by in signal_requirements.yaml itself
    # (signals may be implemented by files that don't carry satisfies_signal)
    implemented_signals = set()
    for req in sig_data["signal_requirements"]:
        if "implemented_by" in req and req["implemented_by"]:
            for impl_file in req["implemented_by"]:
                impl_path = root / impl_file
                if impl_path.exists():
                    implemented_signals.add(req["id"])
                else:
                    warnings.append(
                        f"Signal {req['id']} references missing file: {impl_file}"
                    )

    covered = referenced_signals | implemented_signals
    uncovered = all_signal_ids - covered
    for sig_id in sorted(uncovered):
        warnings.append(f"Signal coverage gap: {sig_id} has no satisfying spec")

    return warnings


def validate_experience_traceability(root: Path) -> list[str]:
    """Level 5: Experience traceability — does every spec trace to L0?"""
    warnings = []
    yaml_files = sorted(root.glob("**/*.yaml"))

    for filepath in yaml_files:
        if ".github" in str(filepath):
            continue

        rel = str(filepath.relative_to(root))

        # Only check products and processes (these should trace to L0)
        if not (rel.startswith("products/") or rel.startswith("processes/")):
            continue

        try:
            with open(filepath) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError:
            continue

        if data is None:
            continue

        has_signal = "satisfies_signal" in data and data["satisfies_signal"]
        has_experience = "satisfies_experience" in data and data["satisfies_experience"]

        if not has_signal and not has_experience:
            warnings.append(
                f"Traceability gap: {rel} has no satisfies_signal or "
                f"satisfies_experience — no upward justification"
            )

    return warnings


def main():
    if len(sys.argv) < 2:
        print("Usage: orgschema-validate <path-to-orgschema-demo>")
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory")
        sys.exit(1)

    exit_code = 0

    # Level 1: Schema validation
    print("Level 1: Schema validation...")
    schema_errors = validate_schema(root)
    for err in schema_errors:
        print(f"  ERROR: {err}")
    if schema_errors:
        exit_code = 1
    else:
        print("  PASSED")

    # Level 2: Cross-reference integrity
    print("Level 2: Cross-reference integrity...")
    xref_errors = validate_cross_references(root)
    for err in xref_errors:
        print(f"  ERROR: {err}")
    if xref_errors:
        exit_code = 1
    else:
        print("  PASSED")

    # Level 4: Signal coverage
    print("Level 4: Signal coverage...")
    coverage_warnings = validate_signal_coverage(root)
    for warn in coverage_warnings:
        print(f"  WARNING: {warn}")
    if not coverage_warnings:
        print("  PASSED")

    # Level 5: Experience traceability
    print("Level 5: Experience traceability...")
    trace_warnings = validate_experience_traceability(root)
    for warn in trace_warnings:
        print(f"  WARNING: {warn}")
    if not trace_warnings:
        print("  PASSED")

    # Summary
    total_errors = len(schema_errors) + len(xref_errors)
    total_warnings = len(coverage_warnings) + len(trace_warnings)
    print(f"\nSummary: {total_errors} errors, {total_warnings} warnings")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
