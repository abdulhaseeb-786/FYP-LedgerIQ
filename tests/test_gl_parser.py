"""Unit tests for General Ledger file ingestion parser (gl_parser.py)."""

import pytest
import tempfile
from pathlib import Path
from app.modules.audit_analytics.infrastructure.gl_parser import (
    GeneralLedgerParser,
    GLParserException,
    parse_clean_float,
    parse_clean_date,
)


def test_parse_clean_float_accounting_formats():
    """Verify clean float extraction supporting parenthetical negative notation."""
    assert parse_clean_float("1,234.56") == 1234.56
    assert parse_clean_float("(1,234.56)") == -1234.56
    assert parse_clean_float("PKR 50,000.00") == 50000.00
    assert parse_clean_float("-") == 0.0
    assert parse_clean_float(None) == 0.0
    assert parse_clean_float(1250) == 1250.0


def test_parse_clean_date_variations():
    """Verify parsing of multiple date formats into datetime."""
    d1 = parse_clean_date("2025-06-30")
    assert (d1.year, d1.month, d1.day) == (2025, 6, 30)

    d2 = parse_clean_date("30/06/2025")
    assert (d2.year, d2.month, d2.day) == (2025, 6, 30)


def test_csv_ingestion_with_debit_credit():
    """Verify parsing a temporary CSV file with Debit/Credit columns."""
    csv_content = """Voucher No,Date,Account Code,Account Title,Narration,Debit,Credit,User
JV-1001,2025-01-10,1010,Cash in Hand,Replenish petty cash,15000.00,0.00,user_ali
JV-1002,2025-01-11,2010,Trade Creditors,Vendor invoice payment,0.00,15000.00,user_ali
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as tmp:
        tmp.write(csv_content)
        tmp_path = tmp.name

    try:
        parser = GeneralLedgerParser()
        records = parser.parse_file(tmp_path)

        assert len(records) == 2
        assert records[0].voucher_no == "JV-1001"
        assert records[0].debit == 15000.0
        assert records[0].account_name == "Cash in Hand"
        assert records[1].credit == 15000.0
        assert records[1].account_code == "2010"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_csv_ingestion_with_net_amount():
    """Verify parsing CSV with single net amount column and negative parentheses."""
    csv_content = """Doc ID,Posting Date,GL Name,Amount,Operator
DOC-001,2025-03-15,Office Supplies,"2,500.00",admin
DOC-002,2025-03-16,Bank Charges,"(450.00)",system
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as tmp:
        tmp.write(csv_content)
        tmp_path = tmp.name

    try:
        parser = GeneralLedgerParser()
        records = parser.parse_file(tmp_path)

        assert len(records) == 2
        assert records[0].debit == 2500.0
        assert records[1].credit == 450.0
        assert records[1].net_amount == -450.0
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_invalid_file_handling():
    """Verify parser raises GLParserException on nonexistent or invalid files."""
    parser = GeneralLedgerParser()
    with pytest.raises(GLParserException, match="not found"):
        parser.parse_file("nonexistent_file_path.xlsx")
