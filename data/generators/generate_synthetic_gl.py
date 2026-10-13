"""Domain-Calibrated Synthetic General Ledger Generator (Track 2 Benchmark).

Generates multi-scenario accounting General Ledger datasets with mathematical
ground truth:
1. gl_01_clean_benford.xlsx: Natural Benford geometric distribution (Close conformity)
2. gl_02_benford_spike.xlsx: Fictitious numbers spiking on digits 5 and 7 (Non-conforming)
3. gl_03_round_numbers.xlsx: Cluster of round-sum management adjustments near period-end
4. gl_04_weekend_override.xlsx: Off-hour & weekend unauthorized manual entries
5. gl_05_threshold_splits.xlsx: Split invoices just below internal approval limits (smurfing)

Outputs data/synthetic_gl/ and manifest.json detailing ground-truth labels for precision/recall evaluation.
"""

import json
import random
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

RANDOM_SEED = 42

CHART_OF_ACCOUNTS = [
    {"code": "1010", "name": "Cash in Hand", "type": "Asset", "normal": "DR"},
    {"code": "1020", "name": "Main Operating Bank Account", "type": "Asset", "normal": "DR"},
    {"code": "1050", "name": "Trade Debtors / Accounts Receivable", "type": "Asset", "normal": "DR"},
    {"code": "1080", "name": "Inventory / Stock in Trade", "type": "Asset", "normal": "DR"},
    {"code": "1510", "name": "Property, Plant & Equipment", "type": "Asset", "normal": "DR"},
    {"code": "2010", "name": "Trade Creditors / Accounts Payable", "type": "Liability", "normal": "CR"},
    {"code": "2030", "name": "Accrued Expenses & Other Liabilities", "type": "Liability", "normal": "CR"},
    {"code": "2050", "name": "Short-Term Bank Borrowings", "type": "Liability", "normal": "CR"},
    {"code": "3010", "name": "Issued Share Capital", "type": "Equity", "normal": "CR"},
    {"code": "3050", "name": "Retained Earnings", "type": "Equity", "normal": "CR"},
    {"code": "4010", "name": "Sales Revenue - Goods", "type": "Revenue", "normal": "CR"},
    {"code": "4020", "name": "Service Fee Income", "type": "Revenue", "normal": "CR"},
    {"code": "5010", "name": "Cost of Goods Sold", "type": "Expense", "normal": "DR"},
    {"code": "5030", "name": "Salaries & Wages Expense", "type": "Expense", "normal": "DR"},
    {"code": "5040", "name": "Office Rent Expense", "type": "Expense", "normal": "DR"},
    {"code": "5050", "name": "Utilities & Communication", "type": "Expense", "normal": "DR"},
    {"code": "5060", "name": "Repairs & Maintenance", "type": "Expense", "normal": "DR"},
    {"code": "5070", "name": "Legal & Professional Charges", "type": "Expense", "normal": "DR"},
    {"code": "5080", "name": "Depreciation Expense", "type": "Expense", "normal": "DR"},
    {"code": "5090", "name": "Finance Costs & Bank Charges", "type": "Expense", "normal": "DR"},
    {"code": "9999", "name": "Suspense / Clearing Account", "type": "Liability", "normal": "CR"},
]

USERS = ["acc_junior1", "acc_senior2", "payroll_officer", "mgr_bilal", "sys_batch"]


def generate_benford_amount(min_val: float = 100.0, max_val: float = 1000000.0) -> float:
    """Generate numbers naturally following Benford's Law via log-uniform distribution over full decades."""
    log_min = math.log10(min_val)
    log_max = math.log10(max_val)
    val = 10 ** random.uniform(log_min, log_max)
    return round(val, 2)


def generate_random_date(start_date: datetime, end_date: datetime, allow_weekend: bool = False) -> datetime:
    """Generate dates within period, optionally excluding weekends."""
    delta_days = (end_date - start_date).days
    while True:
        rand_days = random.randint(0, delta_days)
        cand_date = start_date + timedelta(days=rand_days)
        if allow_weekend or cand_date.weekday() < 5:  # 0-4 are Mon-Fri
            hour = random.randint(9, 17)
            minute = random.randint(0, 59)
            return cand_date.replace(hour=hour, minute=minute)


def build_workbook(records: List[Dict[str, Any]], output_path: Path):
    """Write standard General Ledger Excel file with accounting styles."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "General Ledger"

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    regular_font = Font(name="Calibri", size=10)
    border_thin = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )
    num_format = '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)'

    headers = [
        "Voucher No", "Date", "Account Code", "Account Title",
        "Narration / Description", "Debit (PKR)", "Credit (PKR)", "User ID"
    ]
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for r_idx, rec in enumerate(records, 2):
        ws.cell(row=r_idx, column=1, value=rec["voucher_no"]).font = regular_font
        ws.cell(row=r_idx, column=2, value=rec["date"].strftime("%Y-%m-%d")).font = regular_font
        ws.cell(row=r_idx, column=3, value=rec["account_code"]).font = regular_font
        ws.cell(row=r_idx, column=4, value=rec["account_name"]).font = regular_font
        ws.cell(row=r_idx, column=5, value=rec["narration"]).font = regular_font
        
        c_dr = ws.cell(row=r_idx, column=6, value=rec["debit"])
        c_dr.font = regular_font
        c_dr.number_format = num_format
        
        c_cr = ws.cell(row=r_idx, column=7, value=rec["credit"])
        c_cr.font = regular_font
        c_cr.number_format = num_format
        
        ws.cell(row=r_idx, column=8, value=rec["user_id"]).font = regular_font

        for col_idx in range(1, 9):
            ws.cell(row=r_idx, column=col_idx).border = border_thin

    # Auto-fit columns
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)


def generate_scenario_1_clean(num_entries: int = 600) -> List[Dict[str, Any]]:
    """Clean baseline conforming naturally to Benford's Law."""
    records = []
    start_date = datetime(2024, 7, 1)
    end_date = datetime(2025, 6, 30)

    for i in range(1, num_entries + 1):
        amt = generate_benford_amount(100.0, 1000000.0)
        dt = generate_random_date(start_date, end_date, allow_weekend=False)
        user = random.choice(USERS[:-1])  # Exclude system batch
        acc = random.choice([a for a in CHART_OF_ACCOUNTS if a["code"] != "9999"])
        
        # Decide Dr or Cr based on normal account polarity
        is_dr = (acc["normal"] == "DR") if random.random() < 0.90 else (acc["normal"] != "DR")
        records.append({
            "voucher_no": f"JV-2025-{i:05d}",
            "date": dt,
            "account_code": acc["code"],
            "account_name": acc["name"],
            "narration": f"Routine transaction for {acc['name'].lower()}",
            "debit": amt if is_dr else 0.0,
            "credit": 0.0 if is_dr else amt,
            "user_id": user,
            "is_anomaly": False,
            "anomaly_type": None,
        })
    return records


def generate_scenario_2_benford_spike(num_entries: int = 600) -> List[Dict[str, Any]]:
    """Injects high spike of numbers starting with digit 7 and 5 (Expense fabrication)."""
    records = generate_scenario_1_clean(num_entries - 120)
    start_date = datetime(2024, 7, 1)
    end_date = datetime(2025, 6, 30)

    # Injected entries
    for i in range(len(records) + 1, num_entries + 1):
        lead_digit = random.choice([5, 7])
        rest = random.randint(100, 9999)
        amt = float(f"{lead_digit}{rest}.00")
        dt = generate_random_date(start_date, end_date, allow_weekend=False)
        acc = random.choice([a for a in CHART_OF_ACCOUNTS if a["type"] == "Expense"])
        records.append({
            "voucher_no": f"JV-2025-{i:05d}",
            "date": dt,
            "account_code": acc["code"],
            "account_name": acc["name"],
            "narration": f"Fabricated consulting invoice from vendor X",
            "debit": amt,
            "credit": 0.0,
            "user_id": "acc_junior1",
            "is_anomaly": True,
            "anomaly_type": "BENFORD_DIGIT_SPIKE",
        })
    random.shuffle(records)
    return records


def generate_scenario_3_round_numbers(num_entries: int = 600) -> List[Dict[str, Any]]:
    """Injects large round-number entries ($50k, $100k, $500k) near year end."""
    records = generate_scenario_1_clean(num_entries - 30)
    year_end_start = datetime(2025, 6, 25)
    year_end_end = datetime(2025, 6, 30)

    round_values = [50000.0, 100000.0, 150000.0, 200000.0, 250000.0, 500000.0]
    for i in range(len(records) + 1, num_entries + 1):
        amt = random.choice(round_values)
        dt = generate_random_date(year_end_start, year_end_end, allow_weekend=True)
        acc = random.choice([a for a in CHART_OF_ACCOUNTS if a["type"] in ("Expense", "Asset")])
        records.append({
            "voucher_no": f"JV-2025-{i:05d}",
            "date": dt,
            "account_code": acc["code"],
            "account_name": acc["name"],
            "narration": f"Year-end lump sum management adjustment estimate",
            "debit": amt,
            "credit": 0.0,
            "user_id": "mgr_bilal",
            "is_anomaly": True,
            "anomaly_type": "ROUND_NUMBER_ESTIMATE",
        })
    random.shuffle(records)
    return records


def generate_scenario_4_weekend_override(num_entries: int = 600) -> List[Dict[str, Any]]:
    """Injects off-hour/Sunday entries to suspense and contra accounts by admin user."""
    records = generate_scenario_1_clean(num_entries - 25)
    start_date = datetime(2024, 7, 1)
    end_date = datetime(2025, 6, 30)

    delta_days = (end_date - start_date).days
    sundays = [start_date + timedelta(days=d) for d in range(delta_days) if (start_date + timedelta(days=d)).weekday() == 6]

    for i in range(len(records) + 1, num_entries + 1):
        sunday = random.choice(sundays).replace(hour=23, minute=random.randint(10, 55))
        amt = generate_benford_amount(50000.0, 300000.0)
        acc = random.choice([a for a in CHART_OF_ACCOUNTS if a["code"] in ("9999", "5070", "2030")])
        records.append({
            "voucher_no": f"JV-2025-{i:05d}",
            "date": sunday,
            "account_code": acc["code"],
            "account_name": acc["name"],
            "narration": "Late night administrative override reclassification",
            "debit": amt if random.random() < 0.5 else 0.0,
            "credit": 0.0 if random.random() < 0.5 else amt,
            "user_id": "mgr_bilal",
            "is_anomaly": True,
            "anomaly_type": "WEEKEND_MANAGEMENT_OVERRIDE",
        })
    random.shuffle(records)
    return records


def generate_scenario_5_threshold_splits(num_entries: int = 600) -> List[Dict[str, Any]]:
    """Injects smurfing/split entries just below PKR 50,000 approval limit on same day."""
    records = generate_scenario_1_clean(num_entries - 30)
    split_dates = [datetime(2025, 2, 14), datetime(2025, 3, 20), datetime(2025, 5, 10)]

    for dt in split_dates:
        for _ in range(10):
            amt = round(random.uniform(48500.0, 49950.0), 2)
            records.append({
                "voucher_no": f"JV-2025-SPLIT-{random.randint(100, 999)}",
                "date": dt,
                "account_code": "5070",
                "account_name": "Legal & Professional Charges",
                "narration": "Advisory retainer tranche payment",
                "debit": amt,
                "credit": 0.0,
                "user_id": "acc_senior2",
                "is_anomaly": True,
                "anomaly_type": "SPLIT_INVOICE_EVASION",
            })
    random.shuffle(records)
    return records


def main():
    random.seed(RANDOM_SEED)
    output_dir = Path(__file__).resolve().parents[1] / "synthetic_gl"
    output_dir.mkdir(parents=True, exist_ok=True)

    scenarios = [
        ("gl_01_clean_benford.xlsx", generate_scenario_1_clean, "Clean baseline conforming to Benford's Law"),
        ("gl_02_benford_spike.xlsx", generate_scenario_2_benford_spike, "Fabricated expense entries with digit 5 and 7 spikes"),
        ("gl_03_round_numbers.xlsx", generate_scenario_3_round_numbers, "Round numbers clusters at year end"),
        ("gl_04_weekend_override.xlsx", generate_scenario_4_weekend_override, "Sunday off-hour unauthorized management entries"),
        ("gl_05_threshold_splits.xlsx", generate_scenario_5_threshold_splits, "Split invoices just below 50k authorization limit"),
    ]

    manifest = {"generated_at": datetime.now().isoformat(), "scenarios": {}}

    for filename, gen_fn, desc in scenarios:
        target_path = output_dir / filename
        data = gen_fn(num_entries=600)
        build_workbook(data, target_path)

        anomalies = [r["voucher_no"] for r in data if r["is_anomaly"]]
        manifest["scenarios"][filename] = {
            "description": desc,
            "total_records": len(data),
            "anomaly_count": len(anomalies),
            "anomaly_vouchers": anomalies,
            "path": str(target_path.relative_to(target_path.parents[2])),
        }
        print(f"Generated {filename}: {len(data)} records, {len(anomalies)} anomalies.")

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest written to: {manifest_path}")


if __name__ == "__main__":
    main()
