"""Smoke tests for the ``orgschema-validate`` CLI arguments."""

import pytest

from orgschema_framework import validate


def test_help_prints_usage_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        validate.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "usage: orgschema-validate" in out
    assert "is not a directory" not in out
