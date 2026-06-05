"""Smoke tests for the deterministic ``orgschema-query`` CLI."""

import json
from pathlib import Path

import yaml

from orgschema_framework import query


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _clean_schema(root: Path) -> None:
    _write(
        root / "organization.yaml",
        {
            "name": "Test Co",
            "type": "coffee_shop",
            "version": "1.0.0",
            "roles": ["barista"],
        },
    )
    _write(
        root / "perception" / "customer_experience_contract.yaml",
        {
            "version": "1.0.0",
            "experience_contract": {},
            "constraint_contracts": {
                "food_safety": {
                    "id": "L0_con_01",
                    "type": "constraint",
                    "requires": ["HACCP documented"],
                    "validated_by": "compliance/food_safety.yaml",
                }
            },
            "commitment_contracts": {},
        },
    )
    _write(root / "compliance" / "food_safety.yaml", {"version": "1.0.0"})
    _write(
        root / "processes" / "open.yaml",
        {
            "version": "1.0.0",
            "satisfies_constraint": ["L0_con_01"],
            "who": "barista",
        },
    )


def test_cli_runs_all_checks_clean(tmp_path, capsys):
    _clean_schema(tmp_path)
    rc = query.main(["--schema", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Level 3" in out
    assert "contracts" in out
    assert "Level 6" in out
    assert "waste" in out


def test_cli_json_format_is_valid(tmp_path, capsys):
    _clean_schema(tmp_path)
    rc = query.main(["--schema", str(tmp_path), "--format", "json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["error_count"] == 0
    assert {c["check"] for c in payload["checks"]} == {"contracts", "waste"}


def test_cli_check_contracts_only(tmp_path, capsys):
    _clean_schema(tmp_path)
    rc = query.main(
        ["--schema", str(tmp_path), "--check", "contracts", "--format", "json"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert {c["check"] for c in payload["checks"]} == {"contracts"}


def test_cli_level_flag_selects_waste(tmp_path, capsys):
    _clean_schema(tmp_path)
    rc = query.main(["--schema", str(tmp_path), "--level", "6", "--format", "json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert {c["check"] for c in payload["checks"]} == {"waste"}


def test_cli_nonzero_exit_on_contract_violation(tmp_path, capsys):
    _clean_schema(tmp_path)
    # Break the contract: delete provider and the referencing process.
    (tmp_path / "compliance" / "food_safety.yaml").unlink()
    (tmp_path / "processes" / "open.yaml").unlink()
    rc = query.main(["--schema", str(tmp_path), "--check", "contracts"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "L0_con_01" in out


def test_cli_missing_dir_returns_2(tmp_path, capsys):
    rc = query.main(["--schema", str(tmp_path / "nope")])
    assert rc == 2
