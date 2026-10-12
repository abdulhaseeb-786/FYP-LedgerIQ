"""Tests for trial balance parsing and ingestion."""

from pathlib import Path

SAMPLE_DIR = Path(__file__).parent.parent / "data" / "sample_tbs"
from fyp_module3.core.parser import parse_trial_balance, parse_numeric


def test_parse_numeric():
    assert parse_numeric(1250.5) == 1250.5
    assert parse_numeric("1,250.50") == 1250.5
    assert parse_numeric("(500.00)") == -500.0
    assert parse_numeric("-") == 0.0
    assert parse_numeric(None) == 0.0


def test_parse_tb1_grant():
    tb1_path = SAMPLE_DIR / "TB 1.xlsx"

    payload = parse_trial_balance(str(tb1_path))
    assert len(payload.accounts) >= 8
    assert payload.is_balanced is True
    assert abs(payload.delta) < 0.01


def test_parse_tb2_services():
    tb2_path = SAMPLE_DIR / "TB 2.xlsx"

    payload = parse_trial_balance(str(tb2_path))
    assert len(payload.accounts) >= 10
    assert payload.is_balanced is True


def test_parser_single_sided_rejection():
    import pytest
    from fyp_module3.core.parser import detect_columns

    single_sided_rows = [
        ["Date", "Description", "Credit"],
        ["01-01-2025", "Cheque Deposited", 50000],
        ["02-01-2025", "Cash Deposit", 25000],
    ]
    with pytest.raises(ValueError, match="Single-sided transaction extract detected"):
        detect_columns(single_sided_rows)

