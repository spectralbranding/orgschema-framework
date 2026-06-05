"""Organizational Schema Theory YAML schema validator.

Implements the 6-level CI/CD validation pipeline:
1. Schema validation — "Is this valid YAML with required fields?"
2. Cross-reference integrity — "Do all linked specs exist and are consistent?"
3. Contract satisfaction — "Is every declared L0 contract actually satisfied?"
4. Signal coverage — "Does every signal requirement have a satisfying spec?"
5. Experience traceability — "Does every spec trace upward to L0?"
6. Waste detection — "Are any declared units/roles/contracts never consumed?"

Usage:
    orgschema-validate /path/to/orgschema-demo
    python -m orgschema_framework.validate /path/to/orgschema-demo

For a deterministic, machine-readable query over a single schema directory,
see orgschema_framework.query (the ``orgschema-query`` CLI).
"""

import datetime
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).parent / "schemas"

# Map directory/file patterns to their schema
SCHEMA_MAP = {
    "organization.yaml": "organization.json",
    "products/": "product.json",
    "processes/": "process.json",
    "compliance/": "compliance.json",
}


def normalize_yaml_data(data):
    """Convert YAML-parsed date objects to ISO strings."""
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
            rel = filepath.relative_to(root)
            errors.append(f"YAML parse error in {rel}: {e}")
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


def _load_yaml(filepath: Path):
    """Safely load a YAML file, returning None on parse error or empty file."""
    try:
        with open(filepath) as f:
            return yaml.safe_load(f)
    except yaml.YAMLError:
        return None


def _load_experience_contract(root: Path) -> dict | None:
    """Load the L0 customer experience contract, if present."""
    exp_path = root / "perception" / "customer_experience_contract.yaml"
    if not exp_path.exists():
        return None
    return _load_yaml(exp_path)


def _collect_declared_contracts(contract_data: dict) -> dict[str, dict]:
    """Extract every declared L0 contract keyed by its id.

    Both ``constraint_contracts`` and ``commitment_contracts`` map a
    human-readable name to a contract object carrying an ``id`` such as
    ``L0_con_01`` / ``L0_com_01``. We index by that id and remember which
    kind it is so contract references can be type-checked.
    """
    contracts: dict[str, dict] = {}
    for section, kind in (
        ("constraint_contracts", "constraint"),
        ("commitment_contracts", "commitment"),
    ):
        block = contract_data.get(section)
        if not isinstance(block, dict):
            continue
        for _name, contract in block.items():
            if isinstance(contract, dict) and "id" in contract:
                entry = dict(contract)
                entry["_kind"] = kind
                contracts[contract["id"]] = entry
    return contracts


def validate_contract_satisfaction(root: Path) -> list[str]:
    """Level 3: Contract satisfaction.

    Every declared L0 contract (constraint or commitment) must actually be
    satisfied, and every contract reference made by a spec must resolve to a
    declared contract. Concretely this level enforces:

    1. Provider exists — each contract's ``validated_by`` provider file (the
       spec that discharges the contract) must exist on disk. A contract that
       points at a missing provider is an unmet contract.
    2. No dangling reference — every ``satisfies_constraint`` /
       ``satisfies_commitment`` annotation on any spec must point at a
       contract id that is actually declared in the L0 contract, and must use
       the matching reference key for the contract kind (a constraint id may
       only appear under ``satisfies_constraint``, a commitment id only under
       ``satisfies_commitment``).
    3. No unmet contract — every declared contract must be covered by at
       least one satisfying spec, either via an existing ``validated_by``
       provider or via at least one spec that references it.

    Contracts are binding (regulatory / self-imposed obligations), so
    failures here are errors, mirroring Level 2.
    """
    errors: list[str] = []

    contract_data = _load_experience_contract(root)
    if not contract_data:
        # No contract file => nothing to satisfy. Other levels report the
        # missing file; Level 3 stays silent rather than double-reporting.
        return errors

    declared = _collect_declared_contracts(contract_data)
    if not declared:
        return errors

    constraint_ids = {cid for cid, c in declared.items() if c["_kind"] == "constraint"}
    commitment_ids = {cid for cid, c in declared.items() if c["_kind"] == "commitment"}

    # (1) Provider existence + collect which contracts have a provider.
    contracts_with_provider: set[str] = set()
    for cid, contract in sorted(declared.items()):
        validated_by = contract.get("validated_by")
        if not validated_by:
            continue
        # validated_by may carry a parenthetical note, e.g.
        # "processes/opening_closing.yaml (safety checks)".
        provider_file = str(validated_by).split("(")[0].strip()
        provider_path = root / provider_file
        if provider_path.exists():
            contracts_with_provider.add(cid)
        else:
            errors.append(
                f"Unmet contract {cid}: validated_by provider "
                f"'{provider_file}' does not exist"
            )

    # (2) Dangling / mistyped references across all specs, and collect which
    #     contracts are referenced by at least one spec.
    referenced: set[str] = set()
    for filepath in sorted(root.glob("**/*.yaml")):
        if ".github" in str(filepath):
            continue
        data = _load_yaml(filepath)
        if not isinstance(data, dict):
            continue
        rel = str(filepath.relative_to(root))

        for key, valid_ids, kind in (
            ("satisfies_constraint", constraint_ids, "constraint"),
            ("satisfies_commitment", commitment_ids, "commitment"),
        ):
            refs = data.get(key)
            if not refs:
                continue
            for ref in refs:
                if ref in valid_ids:
                    referenced.add(ref)
                elif ref in declared:
                    other = declared[ref]["_kind"]
                    errors.append(
                        f"Contract type mismatch in {rel}: {key} references "
                        f"'{ref}' which is a {other} contract"
                    )
                else:
                    errors.append(
                        f"Unsatisfied contract reference in {rel}: {key} "
                        f"'{ref}' is not a declared {kind} contract"
                    )

    # (3) Every declared contract must be covered by a provider or a reference.
    covered = contracts_with_provider | referenced
    for cid in sorted(set(declared) - covered):
        errors.append(
            f"Unmet contract {cid}: no satisfying spec "
            f"(no existing validated_by provider and no spec references it)"
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
                        f"Signal {req['id']} references " f"missing file: {impl_file}"
                    )

    covered = referenced_signals | implemented_signals
    uncovered = all_signal_ids - covered
    for sig_id in sorted(uncovered):
        warnings.append(f"Signal coverage gap: {sig_id} " f"has no satisfying spec")

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


def _walk_strings(node):
    """Yield every string scalar anywhere inside a nested YAML structure."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_strings(item)


def validate_waste(root: Path) -> list[str]:
    """Level 6: Waste detection.

    Surfaces specification waste — declared organizational units, roles, and
    contracts that are never actually consumed, plus duplicated coverage.
    Waste is advisory (it does not break a build), so this level emits
    warnings, mirroring Levels 4 and 5. Detected forms:

    1. Orphaned roles — a role declared in ``organization.yaml: roles`` that
       is referenced by no process spec (no ``who``/``responsible`` field and
       no mention anywhere in a process file).
    2. Unconsumed products — a product spec under ``products/`` that no signal
       requirement lists in ``implemented_by`` and that no other spec
       references by path or id. Such a product satisfies nothing upward.
    3. Empty contracts — a declared L0 contract whose ``requires`` obligation
       list is missing or empty (a contract that demands nothing is waste).
    4. Duplicate coverage — a contract referenced identically by more units
       than necessary is *not* flagged (redundancy can be intentional), but a
       product appearing twice in a single signal's ``implemented_by`` is
       flagged as duplicate allocation.

    Definitions are deliberately conservative: only entities that are
    declared in one place and consumed nowhere are reported, to avoid noisy
    false positives.
    """
    warnings: list[str] = []

    yaml_files = [f for f in sorted(root.glob("**/*.yaml")) if ".github" not in str(f)]
    docs = {f: _load_yaml(f) for f in yaml_files}

    # --- (1) Orphaned roles -------------------------------------------------
    org_path = root / "organization.yaml"
    org_data = docs.get(org_path)
    declared_roles = []
    if isinstance(org_data, dict) and isinstance(org_data.get("roles"), list):
        declared_roles = [r for r in org_data["roles"] if isinstance(r, str)]

    if declared_roles:
        # A role counts as "referenced" if its name appears anywhere inside a
        # process spec — as a structured ``who``/``responsible`` value or in
        # prose. We join all process strings and test by substring, which is
        # conservative (a declared role mentioned anywhere is not flagged) and
        # avoids false positives from singular/plural or compound usages.
        process_text_parts: list[str] = []
        for filepath, data in docs.items():
            rel = str(filepath.relative_to(root))
            if not rel.startswith("processes/") or not isinstance(data, dict):
                continue
            process_text_parts.extend(_walk_strings(data))
        process_text = "\n".join(process_text_parts)
        for role in declared_roles:
            if role not in process_text:
                warnings.append(
                    f"Waste: role '{role}' declared in organization.yaml "
                    f"is never referenced by any process spec"
                )

    # --- (2) Unconsumed products -------------------------------------------
    product_files = {
        filepath: data
        for filepath, data in docs.items()
        if str(filepath.relative_to(root)).startswith("products/")
        and isinstance(data, dict)
    }

    # Collect all implemented_by references and per-signal duplicates (4).
    implemented_paths: set[str] = set()
    sig_req_path = root / "perception" / "signal_requirements.yaml"
    sig_data = docs.get(sig_req_path)
    if isinstance(sig_data, dict):
        for req in sig_data.get("signal_requirements", []) or []:
            impls = req.get("implemented_by") if isinstance(req, dict) else None
            if not impls:
                continue
            implemented_paths.update(impls)
            seen: set[str] = set()
            for impl in impls:
                if impl in seen:
                    warnings.append(
                        f"Waste: duplicate allocation — signal "
                        f"{req.get('id', '?')} lists '{impl}' more than once "
                        f"in implemented_by"
                    )
                seen.add(impl)

    # Any string anywhere outside the product file itself that mentions its
    # path or id counts as consumption.
    for filepath, data in product_files.items():
        rel = str(filepath.relative_to(root))
        product_id = data.get("id") if isinstance(data, dict) else None

        if rel in implemented_paths:
            continue

        consumed = False
        for other_path, other_data in docs.items():
            if other_path == filepath:
                continue
            for s in _walk_strings(other_data):
                if rel in s or (product_id and product_id == s):
                    consumed = True
                    break
            if consumed:
                break

        if not consumed:
            warnings.append(
                f"Waste: product {rel} is unconsumed — no signal "
                f"implemented_by and no other spec references it"
            )

    # --- (3) Empty contracts ------------------------------------------------
    contract_data = _load_experience_contract(root)
    if contract_data:
        declared = _collect_declared_contracts(contract_data)
        for cid, contract in sorted(declared.items()):
            requires = contract.get("requires")
            if not requires:
                warnings.append(
                    f"Waste: contract {cid} declares no obligations "
                    f"(empty or missing 'requires')"
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

    # Level 3: Contract satisfaction
    print("Level 3: Contract satisfaction...")
    contract_errors = validate_contract_satisfaction(root)
    for err in contract_errors:
        print(f"  ERROR: {err}")
    if contract_errors:
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

    # Level 6: Waste detection
    print("Level 6: Waste detection...")
    waste_warnings = validate_waste(root)
    for warn in waste_warnings:
        print(f"  WARNING: {warn}")
    if not waste_warnings:
        print("  PASSED")

    # Summary
    total_errors = len(schema_errors) + len(xref_errors) + len(contract_errors)
    total_warnings = len(coverage_warnings) + len(trace_warnings) + len(waste_warnings)
    print(f"\nSummary: {total_errors} errors, {total_warnings} warnings")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
