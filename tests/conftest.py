"""Pytest fixtures for FYP-Module-3 test suite."""

from pathlib import Path
from typing import List, Optional, Sequence

import openpyxl
import pytest

from fyp_module3.core.models import StandardizedAccountRecord

REPO_ROOT = Path(__file__).parent.parent
SAMPLE_DIR = REPO_ROOT / "data" / "sample_tbs"
SYNTHETIC_DIR = REPO_ROOT / "data" / "synthetic_tbs"


@pytest.fixture
def sample_balanced_accounts():
    """A small balanced ledger dataset (Assets = Liabilities + Equity + P&L)."""
    return [
        StandardizedAccountRecord(account_name="Cash at Bank", debit=100000.0, credit=0.0),
        StandardizedAccountRecord(account_name="Office Equipment", debit=250000.0, credit=0.0),
        StandardizedAccountRecord(account_name="Trade Debtors", debit=80000.0, credit=0.0),
        StandardizedAccountRecord(account_name="Share Capital", debit=0.0, credit=300000.0),
        StandardizedAccountRecord(account_name="Trade Creditors", debit=0.0, credit=50000.0),
        StandardizedAccountRecord(account_name="Revenue - Services", debit=0.0, credit=150000.0),
        StandardizedAccountRecord(account_name="Salaries Expense", debit=70000.0, credit=0.0),
    ]


@pytest.fixture
def make_tb(tmp_path):
    """Factory writing a trial balance workbook from `(code, name, dr, cr)` rows."""

    def _make(
        name: str,
        rows: Sequence[Sequence],
        header: Optional[List[str]] = ("S.NO", "DESCRIPTION", "DEBIT", "CREDIT"),
        title: Optional[str] = "TRIAL BALANCE",
    ) -> str:
        wb = openpyxl.Workbook()
        ws = wb.active
        if title:
            ws.append([title, None, None, None])
        if header:
            ws.append(list(header))
        for row in rows:
            ws.append(list(row))
        path = tmp_path / name
        wb.save(path)
        return str(path)

    return _make
