"""`python -m injex check module:container` — the CI gate around validate()."""

import pytest

from injex.cli import main


def test_check_valid_container_exits_zero(capsys):
    assert main(["check", "tests._cli_app:container"]) == 0
    out = capsys.readouterr().out
    assert "valid" in out


def test_check_accepts_a_factory(capsys):
    assert main(["check", "tests._cli_app:make_container"]) == 0
    assert "valid" in capsys.readouterr().out


def test_check_broken_container_exits_nonzero(capsys):
    assert main(["check", "tests._cli_app:broken"]) == 1
    err = capsys.readouterr().err
    assert "Missing" in err  # names the missing binding


def test_check_reports_bad_target_spec():
    with pytest.raises(SystemExit) as excinfo:
        main(["check", "no_colon_here"])
    assert "module:attribute" in str(excinfo.value)


def test_check_reports_import_failure():
    with pytest.raises(SystemExit) as excinfo:
        main(["check", "tests._no_such_module_here:container"])
    assert "could not import" in str(excinfo.value)


def test_check_reports_missing_attribute():
    with pytest.raises(SystemExit) as excinfo:
        main(["check", "tests._cli_app:nope"])
    assert "no attribute" in str(excinfo.value)


def test_check_rejects_non_container():
    with pytest.raises(SystemExit) as excinfo:
        main(["check", "tests._cli_app:not_a_container"])
    assert "not a Container" in str(excinfo.value)
