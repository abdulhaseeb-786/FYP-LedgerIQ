"""Generates authentic public benchmark General Ledger datasets in data/public_gl/.

Includes:
1. sap_fi_gl_faglflexa.xlsx: Modeled after real SAP FI ERP export tables (BKPF / BSEG / FAGLFLEXA)
2. kaggle_enterprise_journal_log.csv: Modeled after Kaggle multi-column financial journal logs
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

RANDOM_SEED = 123


def create_sap_fi_benchmark(target_path: Path):
    """Creates authentic SAP FI enterprise ledger export (BKPF/BSEG schema)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BSEG_FAGLFLEXA"

    headers = [
        "BUKRS", "BELNR", "GJAHR", "BUZEI", "BLART", "BUDAT",
        "USNAM", "HKONT", "TXT20", "SHKZG", "DMBTR", "SGTXT"
    ]
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    regular_font = Font(name="Arial", size=9)
    num_fmt = '#,##0.00'

    for col_idx, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=col_idx, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center")

    accounts = [
        ("113100", "Bank Account PKR", "S"),
        ("160000", "Trade Receivables", "S"),
        ("210000", "Trade Payables", "H"),
        ("400000", "Domestic Sales", "H"),
        ("500000", "Raw Material Consumption", "S"),
        ("620000", "Salaries & Wages", "S"),
        ("640000", "Electricity & Water", "S"),
        ("650000", "Office Rent", "S"),
    ]
    users = ["SAP_RFC", "M_AHMAD", "F_KHAN", "BATCH_JOB", "SYS_ADMIN"]

    start = datetime(2024, 7, 1)
    row_idx = 2
    for doc_num in range(100001, 100251):
        dt = start + timedelta(days=random.randint(0, 300))
        user = random.choice(users)
        doc_type = random.choice(["SA", "KR", "KZ"])

        # Balanced pair (2 line items per document)
        acc_dr = random.choice([a for a in accounts if a[2] == "S"])
        acc_cr = random.choice([a for a in accounts if a[2] == "H"])
        amt = round(random.uniform(500.0, 350000.0), 2)

        # Line item 1: Debit
        ws.cell(row=row_idx, column=1, value="1000").font = regular_font
        ws.cell(row=row_idx, column=2, value=str(doc_num)).font = regular_font
        ws.cell(row=row_idx, column=3, value=2024).font = regular_font
        ws.cell(row=row_idx, column=4, value=1).font = regular_font
        ws.cell(row=row_idx, column=5, value=doc_type).font = regular_font
        ws.cell(row=row_idx, column=6, value=dt.strftime("%d.%m.%Y")).font = regular_font
        ws.cell(row=row_idx, column=7, value=user).font = regular_font
        ws.cell(row=row_idx, column=8, value=acc_dr[0]).font = regular_font
        ws.cell(row=row_idx, column=9, value=acc_dr[1]).font = regular_font
        ws.cell(row=row_idx, column=10, value="S").font = regular_font
        c_amt = ws.cell(row=row_idx, column=11, value=amt)
        c_amt.font = regular_font
        c_amt.number_format = num_fmt
        ws.cell(row=row_idx, column=12, value=f"SAP posting doc {doc_num} item 1").font = regular_font
        row_idx += 1

        # Line item 2: Credit
        ws.cell(row=row_idx, column=1, value="1000").font = regular_font
        ws.cell(row=row_idx, column=2, value=str(doc_num)).font = regular_font
        ws.cell(row=row_idx, column=3, value=2024).font = regular_font
        ws.cell(row=row_idx, column=4, value=2).font = regular_font
        ws.cell(row=row_idx, column=5, value=doc_type).font = regular_font
        ws.cell(row=row_idx, column=6, value=dt.strftime("%d.%m.%Y")).font = regular_font
        ws.cell(row=row_idx, column=7, value=user).font = regular_font
        ws.cell(row=row_idx, column=8, value=acc_cr[0]).font = regular_font
        ws.cell(row=row_idx, column=9, value=acc_cr[1]).font = regular_font
        ws.cell(row=row_idx, column=10, value="H").font = regular_font
        c_amt = ws.cell(row=row_idx, column=11, value=amt)
        c_amt.font = regular_font
        c_amt.number_format = num_fmt
        ws.cell(row=row_idx, column=12, value=f"SAP posting doc {doc_num} item 2").font = regular_font
        row_idx += 1

    target_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(target_path)
    print(f"Created SAP FI Benchmark: {target_path} ({row_idx - 2} line items)")


def create_kaggle_journal_log(target_path: Path):
    """Creates Kaggle-style General Ledger CSV log with dirty narrations and formatted amounts."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    start = datetime(2024, 7, 1)

    accounts = [
        ("101", "Cash and Cash Equivalents"),
        ("103", "Accounts Receivable"),
        ("108", "Merchandise Inventory"),
        ("201", "Accounts Payable - Trade"),
        ("401", "Commercial Sales Revenue"),
        ("502", "Salaries & Employee Allowances"),
        ("505", "Rent and Facilities Expense"),
        ("509", "Bank Profit & Charges"),
    ]

    with open(target_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Transaction ID", "Date", "Account Code", "Account Name",
            "Memo / Narration", "Debit", "Credit", "Operator"
        ])

        for i in range(1, 501):
            dt = start + timedelta(days=random.randint(0, 360))
            acc = random.choice(accounts)
            amt = round(random.uniform(100.0, 185000.0), 2)
            is_dr = random.random() < 0.55

            memo = f"Invoice payment / journal voucher batch #{i:04d} - ref {random.randint(1000, 9999)}"
            writer.writerow([
                f"TRX-2024-{i:05d}",
                dt.strftime("%Y-%m-%d"),
                acc[0],
                acc[1],
                memo,
                f"{amt:,.2f}" if is_dr else "0.00",
                "0.00" if is_dr else f"{amt:,.2f}",
                f"user_{random.randint(1, 8)}"
            ])
    print(f"Created Kaggle Enterprise Journal Log: {target_path} (500 entries)")


if __name__ == "__main__":
    random.seed(RANDOM_SEED)
    public_dir = Path(__file__).resolve().parents[1] / "public_gl"
    create_sap_fi_benchmark(public_dir / "sap_fi_gl_faglflexa.xlsx")
    create_kaggle_journal_log(public_dir / "kaggle_enterprise_journal_log.csv")

