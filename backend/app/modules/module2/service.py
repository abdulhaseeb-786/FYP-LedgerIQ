"""Module 2: High-Level Service & Working Paper Export.

Allows reading raw trial balance files, executing adjustments, and writing
the adjusted working paper and adjusting journal entry log into Excel.
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Sequence

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side as XlSide

from .engine import Adjustment, AdjustmentRun, run as run_adjustments
from .models import (
    Account,
    Element,
    Side,
    TrialBalance,
    TrialBalanceLine,
    ZERO,
    money,
    quantise,
)


def load_trial_balance_from_csv(csv_path: str | Path, period_label: str = "FY2025") -> TrialBalance:
    """Read a CSV containing columns: Code, Name, Balance (or Debit / Credit)."""
    tb = TrialBalance(period_label=period_label)
    path = Path(csv_path)

    with open(path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get("Code") or row.get("code") or "").strip()
            name = (row.get("Name") or row.get("name") or row.get("Account") or "").strip()
            if not code or not name:
                continue

            # Check if signed balance or debit/credit columns
            bal_str = row.get("Balance") or row.get("balance")
            if bal_str is not None:
                bal = money(bal_str)
            else:
                dr = money(row.get("Debit") or row.get("debit") or "0")
                cr = money(row.get("Credit") or row.get("credit") or "0")
                bal = quantise(dr - cr)

            # Infer classification element based on traditional numbering or line code
            first_digit = code[0] if code else "1"
            element = {
                "1": Element.ASSET,
                "2": Element.LIABILITY,
                "3": Element.EQUITY,
                "4": Element.INCOME,
                "5": Element.EXPENSE,
                "6": Element.EXPENSE,
            }.get(first_digit, Element.EXPENSE)

            line_code = {
                Element.ASSET: "BS.CA",
                Element.LIABILITY: "BS.CL",
                Element.EQUITY: "BS.EQ",
                Element.INCOME: "PL.REVENUE",
                Element.EXPENSE: "PL.ADMIN",
            }[element]

            acc = Account(code=code, name=name, element=element, line_code=line_code)
            tb.lines.append(TrialBalanceLine(account=acc, balance=bal))

    return tb


def export_working_papers_to_excel(run_res: AdjustmentRun, output_path: str | Path) -> Path:
    """Export the unadjusted balance, adjustments, and adjusted balance into Excel."""
    wb = openpyxl.Workbook()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1. Sheet 1: Working Trial Balance
    ws_tb = wb.active
    ws_tb.title = "Working Trial Balance"

    headers = [
        "Account Code",
        "Account Title",
        "Element",
        "Unadjusted Dr",
        "Unadjusted Cr",
        "AJE Dr",
        "AJE Cr",
        "Adjusted Dr",
        "Adjusted Cr",
    ]
    ws_tb.append(headers)

    # Calculate adjustments per account
    dr_adj: dict[str, Decimal] = {}
    cr_adj: dict[str, Decimal] = {}
    for entry in run_res.entries:
        for line in entry.lines:
            if line.side == Side.DEBIT:
                dr_adj[line.account_code] = quantise(dr_adj.get(line.account_code, ZERO) + line.amount)
            else:
                cr_adj[line.account_code] = quantise(cr_adj.get(line.account_code, ZERO) + line.amount)

    for line in run_res.adjusted.lines:
        code = line.account.code
        title = line.account.name
        elem = line.account.element.value if line.account.element else "unclassified"

        # Determine original balance before adjustment
        net_adj = quantise(dr_adj.get(code, ZERO) - cr_adj.get(code, ZERO))
        orig_bal = quantise(line.balance - net_adj)

        orig_dr = orig_bal if orig_bal > ZERO else ZERO
        orig_cr = -orig_bal if orig_bal < ZERO else ZERO

        adj_dr = dr_adj.get(code, ZERO)
        adj_cr = cr_adj.get(code, ZERO)

        adj_final_dr = line.debit
        adj_final_cr = line.credit

        ws_tb.append([
            code,
            title,
            elem,
            float(orig_dr),
            float(orig_cr),
            float(adj_dr),
            float(adj_cr),
            float(adj_final_dr),
            float(adj_final_cr),
        ])

    # 2. Sheet 2: Adjusting Journal Entries Log
    ws_aje = wb.create_sheet(title="AJE Log")
    ws_aje.append(["Entry Ref", "Date", "Account Code", "Account Narration", "Debit (PKR)", "Credit (PKR)"])

    for entry in run_res.entries:
        for line in entry.lines:
            dr_amt = float(line.amount) if line.side == Side.DEBIT else 0.0
            cr_amt = float(line.amount) if line.side == Side.CREDIT else 0.0
            ws_aje.append([entry.ref, entry.date, line.account_code, line.narration, dr_amt, cr_amt])

    wb.save(out)
    return out
