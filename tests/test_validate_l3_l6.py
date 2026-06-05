"""Tests for Level 3 (contract satisfaction) and Level 6 (waste detection).

Fixtures are built on disk under ``tmp_path`` to mirror the orgschema-demo
layout (perception/, processes/, products/, organization.yaml) so the level
functions run against the same file shapes they see in production.
"""

from pathlib import Path

import yaml

from orgschema_framework.validate import (
    validate_contract_satisfaction,
    validate_waste,
)


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _experience_contract(constraints, commitments) -> dict:
    return {
        "version": "1.0.0",
        "experience_contract": {},
        "constraint_contracts": constraints,
        "commitment_contracts": commitments,
    }


def _good_schema(root: Path) -> None:
    """Build a minimal schema where all contracts are satisfied, no waste."""
    _write(
        root / "organization.yaml",
        {
            "name": "Test Co",
            "type": "coffee_shop",
            "version": "1.0.0",
            "roles": ["barista", "shift_lead"],
        },
    )
    _write(
        root / "perception" / "customer_experience_contract.yaml",
        _experience_contract(
            constraints={
                "food_safety": {
                    "id": "L0_con_01",
                    "type": "constraint",
                    "requires": ["HACCP plan documented"],
                    "validated_by": "compliance/food_safety.yaml",
                },
            },
            commitments={
                "transparency": {
                    "id": "L0_com_01",
                    "type": "commitment",
                    "requires": ["Pricing visible"],
                    # No validated_by — must be covered by a referencing spec.
                },
            },
        ),
    )
    _write(
        root / "perception" / "signal_requirements.yaml",
        {
            "version": "1.0.0",
            "signal_requirements": [
                {
                    "id": "L1_exp_01",
                    "implemented_by": ["products/espresso.yaml"],
                }
            ],
        },
    )
    _write(root / "compliance" / "food_safety.yaml", {"version": "1.0.0"})
    _write(
        root / "products" / "espresso.yaml",
        {
            "version": "1.0.0",
            "id": "espresso",
            "name": "Espresso",
            "category": "hot_beverage",
            "available": True,
            "satisfies_commitment": ["L0_com_01"],
        },
    )
    _write(
        root / "processes" / "opening_closing.yaml",
        {
            "version": "1.0.0",
            "satisfies_constraint": ["L0_con_01"],
            "opening": {"who": "shift_lead", "lead": "barista"},
        },
    )


# --------------------------------------------------------------------------
# Level 3: contract satisfaction
# --------------------------------------------------------------------------


def test_l3_positive_all_contracts_satisfied(tmp_path):
    _good_schema(tmp_path)
    errors = validate_contract_satisfaction(tmp_path)
    assert errors == []


def test_l3_negative_missing_provider(tmp_path):
    _good_schema(tmp_path)
    # Remove the provider file the constraint's validated_by points at, and
    # remove the spec that references it, so the contract becomes unmet.
    (tmp_path / "compliance" / "food_safety.yaml").unlink()
    (tmp_path / "processes" / "opening_closing.yaml").unlink()
    errors = validate_contract_satisfaction(tmp_path)
    assert any("L0_con_01" in e for e in errors)


def test_l3_negative_dangling_reference(tmp_path):
    _good_schema(tmp_path)
    # Reference a contract id that is not declared anywhere.
    _write(
        tmp_path / "products" / "ghost.yaml",
        {
            "version": "1.0.0",
            "id": "ghost",
            "name": "Ghost",
            "category": "hot_beverage",
            "available": True,
            "satisfies_constraint": ["L0_con_99"],
        },
    )
    errors = validate_contract_satisfaction(tmp_path)
    assert any("L0_con_99" in e for e in errors)


def test_l3_negative_type_mismatch(tmp_path):
    _good_schema(tmp_path)
    # Reference a commitment id under satisfies_constraint (wrong key).
    _write(
        tmp_path / "products" / "espresso.yaml",
        {
            "version": "1.0.0",
            "id": "espresso",
            "name": "Espresso",
            "category": "hot_beverage",
            "available": True,
            "satisfies_constraint": ["L0_com_01"],
            "satisfies_commitment": ["L0_com_01"],
        },
    )
    errors = validate_contract_satisfaction(tmp_path)
    assert any("mismatch" in e.lower() and "L0_com_01" in e for e in errors)


def test_l3_no_contract_file_is_silent(tmp_path):
    # An empty directory has nothing to satisfy.
    errors = validate_contract_satisfaction(tmp_path)
    assert errors == []


# --------------------------------------------------------------------------
# Level 6: waste detection
# --------------------------------------------------------------------------


def test_l6_positive_no_waste(tmp_path):
    _good_schema(tmp_path)
    warnings = validate_waste(tmp_path)
    assert warnings == []


def test_l6_negative_orphaned_role(tmp_path):
    _good_schema(tmp_path)
    org_path = tmp_path / "organization.yaml"
    org = yaml.safe_load(org_path.read_text())
    org["roles"].append("ghost_role")
    _write(org_path, org)
    warnings = validate_waste(tmp_path)
    assert any("ghost_role" in w for w in warnings)


def test_l6_negative_unconsumed_product(tmp_path):
    _good_schema(tmp_path)
    # A product no signal implements and nothing references.
    _write(
        tmp_path / "products" / "orphan.yaml",
        {
            "version": "1.0.0",
            "id": "orphan",
            "name": "Orphan",
            "category": "hot_beverage",
            "available": True,
        },
    )
    warnings = validate_waste(tmp_path)
    assert any("orphan" in w for w in warnings)


def test_l6_negative_empty_contract(tmp_path):
    _good_schema(tmp_path)
    # Add a commitment contract with no obligations.
    contract_path = tmp_path / "perception" / "customer_experience_contract.yaml"
    data = yaml.safe_load(contract_path.read_text())
    data["commitment_contracts"]["empty_one"] = {
        "id": "L0_com_09",
        "type": "commitment",
        "requires": [],
    }
    _write(contract_path, data)
    warnings = validate_waste(tmp_path)
    assert any("L0_com_09" in w for w in warnings)


def test_l6_negative_duplicate_allocation(tmp_path):
    _good_schema(tmp_path)
    sig_path = tmp_path / "perception" / "signal_requirements.yaml"
    data = yaml.safe_load(sig_path.read_text())
    data["signal_requirements"][0]["implemented_by"] = [
        "products/espresso.yaml",
        "products/espresso.yaml",
    ]
    _write(sig_path, data)
    warnings = validate_waste(tmp_path)
    assert any("duplicate" in w.lower() for w in warnings)
