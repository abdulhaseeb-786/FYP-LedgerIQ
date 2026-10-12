"""A labelled trial balance corpus for exercising the compiler.

Public trial balances effectively do not exist - firms publish finished
statements, not working papers - so robustness has to be tested against
deliberately constructed shapes rather than volume of real data.

Every case here is built from a known ledger, so the expected account count,
totals and classifications are derived from the construction rather than
recorded from whatever the pipeline happened to produce. A case that expects
to compile also asserts the exported workbook's own formulas tie out.

Regenerate the files with:

    python -m fyp_module3.testing.corpus --out data/generated
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import openpyxl

# ---------------------------------------------------------------------
# The base ledger every layout variant re-presents.
#
#   Debits  800,000 + 300,000 + 250,000 + 150,000 + 500,000 + 200,000 + 80,000
#           = 2,280,000
#   Credits 1,000,000 + 200,000 + 180,000 + 900,000
#           = 2,280,000
#
# Statements that follow from it:
#   Non-current assets  800,000 - 200,000            =   600,000
#   Current assets      300,000 + 250,000 + 150,000  =   700,000
#   Total assets                                     = 1,300,000
#   Net profit          900,000 - 500,000 - 280,000  =   120,000
#   Equity              1,000,000 + 120,000          = 1,120,000
#   Liabilities                                      =   180,000
# ---------------------------------------------------------------------

Row = Tuple[str, str, float, float]  # code, name, debit, credit

BASE_LEDGER: List[Row] = [
    ("1001", "Capital Account", 0.0, 1_000_000.0),
    ("1201", "Plant and Machinery", 800_000.0, 0.0),
    ("1202", "Accumulated Depreciation", 0.0, 200_000.0),
    ("1301", "Stock in Trade", 300_000.0, 0.0),
    ("1302", "Trade Debtors", 250_000.0, 0.0),
    ("1303", "Cash in Hand", 150_000.0, 0.0),
    ("2001", "Trade Creditors", 0.0, 180_000.0),
    ("3001", "Sales", 0.0, 900_000.0),
    ("4001", "Purchases", 500_000.0, 0.0),
    ("4002", "Salaries Expense", 200_000.0, 0.0),
    ("4003", "Rent Expense", 80_000.0, 0.0),
]

BASE_DR = 2_280_000.0
BASE_CR = 2_280_000.0
BASE_ACCOUNTS = len(BASE_LEDGER)
BASE_ASSETS = 1_300_000.0
BASE_NET_PROFIT = 120_000.0

BASE_CLASSIFICATIONS = {
    "Capital Account": "sofp.eq.capitalaccount",
    "Plant and Machinery": "sofp.nca.ppe",
    "Accumulated Depreciation": "sofp.nca.accdep",
    "Stock in Trade": "sofp.ca.stock",
    "Trade Debtors": "sofp.ca.debtors",
    "Cash in Hand": "sofp.ca.cash",
    "Trade Creditors": "sofp.cl.payables",
    "Sales": "pl.revenue",
    "Purchases": "pl.cos",
}

STANDARD_HEADER = ["Code", "Account Name", "Debit", "Credit"]


# ---------------------------------------------------------------------
# Case definition
# ---------------------------------------------------------------------

@dataclass
class CorpusCase:
    """One trial balance file plus what the pipeline should make of it."""

    name: str
    dimension: str
    description: str
    sheets: List[Tuple[str, List[List[Any]]]]

    # Expectations. None means "do not assert".
    expect_status: str = "SUCCESS"
    expect_accounts: Optional[int] = BASE_ACCOUNTS
    expect_total_dr: Optional[float] = BASE_DR
    expect_total_cr: Optional[float] = BASE_CR
    expect_total_assets: Optional[float] = BASE_ASSETS
    expect_net_profit: Optional[float] = BASE_NET_PROFIT
    expect_classifications: Dict[str, str] = field(default_factory=dict)
    expect_message_contains: Optional[str] = None
    allow_plug: bool = False
    enforce_health_gate: bool = True

    @property
    def filename(self) -> str:
        return f"{self.name}.xlsx"

    def manifest_entry(self) -> Dict[str, Any]:
        return {
            "file": self.filename,
            "dimension": self.dimension,
            "description": self.description,
            "expect": {
                "status": self.expect_status,
                "accounts": self.expect_accounts,
                "total_debits": self.expect_total_dr,
                "total_credits": self.expect_total_cr,
                "total_assets": self.expect_total_assets,
                "net_profit": self.expect_net_profit,
                "classifications": self.expect_classifications,
                "message_contains": self.expect_message_contains,
            },
            "options": {
                "allow_working_capital_plug": self.allow_plug,
                "enforce_health_gate": self.enforce_health_gate,
            },
        }


# ---------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------

def _blank(value: float) -> Optional[float]:
    """Trial balances leave the unused side empty rather than writing zero."""
    return value if value else None


def rows_4col(ledger: Sequence[Row] = BASE_LEDGER, header: bool = True,
              title: bool = True) -> List[List[Any]]:
    out: List[List[Any]] = []
    if title:
        out.append(["TRIAL BALANCE", None, None, None])
    if header:
        out.append(list(STANDARD_HEADER))
    for code, name, dr, cr in ledger:
        out.append([code, name, _blank(dr), _blank(cr)])
    return out


def rows_3col(ledger: Sequence[Row] = BASE_LEDGER) -> List[List[Any]]:
    out: List[List[Any]] = [["TRIAL BALANCE", None, None],
                            ["Particulars", "Debit", "Credit"]]
    for _code, name, dr, cr in ledger:
        out.append([name, _blank(dr), _blank(cr)])
    return out


def _grand_total(ledger: Sequence[Row] = BASE_LEDGER) -> List[Any]:
    return [None, "Total",
            sum(r[2] for r in ledger),
            sum(r[3] for r in ledger)]


# ---------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------

def _layout_cases() -> List[CorpusCase]:
    cases: List[CorpusCase] = []

    cases.append(CorpusCase(
        name="layout_01_four_column",
        dimension="layout",
        description="Canonical 4-column sheet: code, name, debit, credit, with a grand total row.",
        sheets=[("Trial Balance", rows_4col() + [_grand_total()])],
        expect_classifications=dict(BASE_CLASSIFICATIONS),
    ))

    cases.append(CorpusCase(
        name="layout_02_three_column",
        dimension="layout",
        description="3-column sheet with no account codes.",
        sheets=[("Trial Balance", rows_3col())],
        expect_classifications=dict(BASE_CLASSIFICATIONS),
    ))

    cases.append(CorpusCase(
        name="layout_03_no_header_row",
        dimension="layout",
        description=("No header row at all. Column positions must be inferred without "
                     "mistaking the numeric account-code column for money."),
        sheets=[("Sheet1", [[code, name, _blank(dr), _blank(cr)]
                            for code, name, dr, cr in BASE_LEDGER])],
    ))

    cases.append(CorpusCase(
        name="layout_04_codes_inside_names",
        dimension="layout",
        description="Account codes embedded in the description: '1001 - Capital Account'.",
        sheets=[("Trial Balance", [["TRIAL BALANCE", None, None],
                                   ["Particulars", "Debit", "Credit"]] +
                 [[f"{code} - {name}", _blank(dr), _blank(cr)]
                  for code, name, dr, cr in BASE_LEDGER])],
        expect_classifications=dict(BASE_CLASSIFICATIONS),
    ))

    # A column headed "Account Name" that actually holds codes, with the real
    # descriptions in an unlabelled column beside it - the shape that produced
    # a statement full of accounts called "1020101".
    mislabelled = [["SWIFT TRADERS", None, None, None, None],
                   [None, None, None, "Trial Balance", None],
                   ["Account Name", None, "Description", "Debit", "Credit"]]
    for code, name, dr, cr in BASE_LEDGER:
        mislabelled.append([code, None, name, _blank(dr), _blank(cr)])
    cases.append(CorpusCase(
        name="layout_05_name_column_holds_codes",
        dimension="layout",
        description=("The column headed 'Account Name' holds codes; descriptions sit in "
                     "an unlabelled neighbour. Trusting the header loses every name."),
        sheets=[("Updated Trial", mislabelled)],
        expect_classifications=dict(BASE_CLASSIFICATIONS),
    ))

    # Branch A + Branch B = Adjusted. Only the adjusted pair is the ledger.
    multi = [[None, "Trial Balance KHI", None, "Trial Balance LHR", None, "Adjusted Trial", None],
             ["Account Name", "Debit", "Credit", "Debit", "Credit", "Debit", "Credit"]]
    for _code, name, dr, cr in BASE_LEDGER:
        multi.append([name,
                      _blank(dr * 0.6), _blank(cr * 0.6),
                      _blank(dr * 0.4), _blank(cr * 0.4),
                      _blank(dr), _blank(cr)])
    cases.append(CorpusCase(
        name="layout_06_multiple_amount_pairs",
        dimension="layout",
        description=("Branch and adjusted debit/credit pairs side by side. Reading the "
                     "leftmost pair reports one branch as though it were the ledger."),
        sheets=[("Updated Trial", multi)],
        expect_classifications=dict(BASE_CLASSIFICATIONS),
    ))

    # Accounting notation: parentheses, currency prefixes, Dr/Cr suffixes, dashes.
    formatted = [["TRIAL BALANCE", None, None, None],
                 ["Code", "Account Name", "Debit (PKR)", "Credit (PKR)"]]
    for code, name, dr, cr in BASE_LEDGER:
        formatted.append([
            code, name,
            f"PKR {dr:,.2f}" if dr else "-",
            f"{cr:,.2f} Cr" if cr else "-",
        ])
    cases.append(CorpusCase(
        name="layout_07_formatted_amounts",
        dimension="layout",
        description="Amounts as text: thousands separators, currency prefixes, Dr/Cr suffixes, dashes for nil.",
        sheets=[("Trial Balance", formatted)],
    ))

    return cases


def _sheet_cases() -> List[CorpusCase]:
    decoy_grouping = [["Line Item", "Maps To"], ["Cash", "Current Assets"]]
    decoy_coa = [["Code", "Head"], ["1001", "Capital"]]
    return [
        CorpusCase(
            name="sheet_01_many_tabs",
            dimension="sheet-selection",
            description=("Mapping, grouping and chart-of-accounts tabs precede the real "
                         "trial balance; the compiler must not parse a lookup table."),
            sheets=[
                ("grouping", decoy_grouping),
                ("COA", decoy_coa),
                ("Notes", [["Prepared by finance"], ["Reviewed 12 June"]]),
                ("Trial Balance", rows_4col()),
            ],
            expect_classifications=dict(BASE_CLASSIFICATIONS),
        ),
        CorpusCase(
            name="sheet_02_tb_not_first",
            dimension="sheet-selection",
            description="A plausible but non-ledger tab sits first; the TB tab is named explicitly.",
            sheets=[
                ("Cover", [["SWIFT TRADERS"], ["Financial Statements 2025"]]),
                ("Working TB", rows_4col()),
            ],
        ),
    ]


def _noise_cases() -> List[CorpusCase]:
    # Section headers, mid-table subtotals, narrative rows and a grand total.
    noisy: List[List[Any]] = [
        ["SWIFT TRADERS (PVT.) LTD.", None, None, None],
        ["Detailed Trial Balance", None, None, None],
        ["Code", "Account Name", "Debit", "Credit"],
        [None, "EQUITY", None, None],
        ["1001", "Capital Account", None, 1_000_000.0],
        [None, "Total Equity", None, 1_000_000.0],
        [None, None, None, None],
        [None, "NON-CURRENT ASSETS", None, None],
        ["1201", "Plant and Machinery", 800_000.0, None],
        ["1202", "Accumulated Depreciation", None, 200_000.0],
        [None, "Total Non-Current Assets", 600_000.0, None],
        [None, "CURRENT ASSETS", None, None],
        ["1301", "Stock in Trade", 300_000.0, None],
        ["1302", "Trade Debtors", 250_000.0, None],
        ["1303", "Cash in Hand", 150_000.0, None],
        [None, "LIABILITIES", None, None],
        ["2001", "Trade Creditors", None, 180_000.0],
        [None, "Note: creditors confirmed by circularisation", None, None],
        [None, "REVENUE AND EXPENSES", None, None],
        ["3001", "Sales", None, 900_000.0],
        ["4001", "Purchases", 500_000.0, None],
        ["4002", "Salaries Expense", 200_000.0, None],
        ["4003", "Rent Expense", 80_000.0, None],
        [None, "Grand Total", 2_280_000.0, 2_280_000.0],
    ]
    cases = [CorpusCase(
        name="noise_01_section_headers_and_subtotals",
        dimension="row-noise",
        description=("Section captions, mid-table subtotals, a narrative row and a grand "
                     "total. Subtotals must not be ingested as accounts."),
        sheets=[("Trial Balance", noisy)],
        expect_classifications=dict(BASE_CLASSIFICATIONS),
    )]

    # A genuine account whose title begins with the word "Total".
    with_total_named = list(BASE_LEDGER)
    with_total_named.insert(9, ("4004", "Total Quality Management Fees", 60_000.0, 0.0))
    extended = [list(r) for r in with_total_named]
    extended[6] = ["2001", "Trade Creditors", 0.0, 240_000.0]  # keep it balanced
    cases.append(CorpusCase(
        name="noise_02_account_named_total",
        dimension="row-noise",
        description=("'Total Quality Management Fees' is a real expense account. Treating "
                     "any row containing 'total' as end-of-table truncates the ledger."),
        sheets=[("Trial Balance", rows_4col(
            [(c, n, d, cr) for c, n, d, cr in extended]) + [_grand_total(
                [(c, n, d, cr) for c, n, d, cr in extended])])],
        expect_accounts=BASE_ACCOUNTS + 1,
        expect_total_dr=BASE_DR + 60_000.0,
        expect_total_cr=BASE_CR + 60_000.0,
        # The title matches no Fifth Schedule line item, so the 60,000 sits in
        # suspense as a current asset and never touches reported profit.
        expect_total_assets=BASE_ASSETS + 60_000.0,
        expect_net_profit=BASE_NET_PROFIT,
        expect_classifications={"Total Quality Management Fees": "sofp.ca.suspense"},
    ))

    # Dormant accounts carrying no balance.
    dormant = list(BASE_LEDGER) + [
        ("1304", "Petty Cash", 0.0, 0.0),
        ("2002", "Dormant Supplier Account", 0.0, 0.0),
    ]
    cases.append(CorpusCase(
        name="noise_03_nil_balance_accounts",
        dimension="row-noise",
        description="Dormant accounts with nil balances are skipped and counted as noise.",
        sheets=[("Trial Balance", rows_4col(dormant))],
    ))

    return cases


def _naming_cases() -> List[CorpusCase]:
    abbreviated = [
        ("1001", "Capital A/C", 0.0, 1_000_000.0),
        ("1201", "P.P.E.", 800_000.0, 0.0),
        ("1202", "Accum. Dep.", 0.0, 200_000.0),
        ("1301", "Stock in Trade", 300_000.0, 0.0),
        ("1302", "Trade Recievable", 250_000.0, 0.0),      # misspelt
        ("1303", "Cash in Hand", 150_000.0, 0.0),
        ("2001", "Sundry Creditors", 0.0, 180_000.0),
        ("3001", "Sales", 0.0, 900_000.0),
        ("4001", "Purchases", 500_000.0, 0.0),
        ("4002", "Salaries Exp.", 200_000.0, 0.0),
        ("4003", "Rent Expence", 80_000.0, 0.0),           # misspelt
    ]
    cases = [CorpusCase(
        name="naming_01_abbreviations_and_typos",
        dimension="naming",
        description="Abbreviations (A/C, PPE, Accum. Dep.) and common misspellings.",
        sheets=[("Trial Balance", rows_4col(abbreviated))],
        expect_classifications={
            "Capital A/C": "sofp.eq.capitalaccount",
            "Accum. Dep.": "sofp.nca.accdep",
            "Trade Recievable": "sofp.ca.debtors",
            "Cash in Hand": "sofp.ca.cash",
            "Sundry Creditors": "sofp.cl.payables",
        },
    )]

    # Contra accounts on every statement section.
    contra = [
        ("1001", "Capital Account", 0.0, 1_200_000.0),
        ("1002", "Drawings", 100_000.0, 0.0),
        ("1201", "Plant and Machinery", 800_000.0, 0.0),
        ("1202", "Accumulated Depreciation", 0.0, 200_000.0),
        ("1302", "Trade Debtors", 300_000.0, 0.0),
        ("1304", "Allowance for Doubtful Debts", 0.0, 20_000.0),
        ("1303", "Cash in Hand", 150_000.0, 0.0),
        ("2001", "Trade Creditors", 0.0, 180_000.0),
        ("3001", "Sales", 0.0, 900_000.0),
        ("3002", "Sales Returns", 50_000.0, 0.0),
        ("4001", "Purchases", 500_000.0, 0.0),
        ("4002", "Salaries Expense", 600_000.0, 0.0),
    ]
    contra_dr = sum(r[2] for r in contra)
    contra_cr = sum(r[3] for r in contra)
    cases.append(CorpusCase(
        name="naming_02_contra_accounts",
        dimension="naming",
        description=("Drawings, accumulated depreciation, an ECL allowance and sales "
                     "returns - each must reduce the section it belongs to."),
        sheets=[("Trial Balance", rows_4col(contra))],
        expect_accounts=len(contra),
        expect_total_dr=contra_dr,
        expect_total_cr=contra_cr,
        # Assets: (800,000-200,000) + (300,000-20,000) + 150,000 = 1,030,000
        expect_total_assets=1_030_000.0,
        # Revenue net 850,000 - COS 500,000 - admin 600,000 = -250,000
        expect_net_profit=-250_000.0,
        expect_classifications={
            "Drawings": "sofp.eq.drawings",
            "Allowance for Doubtful Debts": "sofp.ca.allowance_ecl",
            "Sales Returns": "pl.salesreturns",
        },
    ))

    # Party sub-ledger accounts: unmappable by name, must land in suspense.
    party = [
        ("1001", "Capital Account", 0.0, 1_000_000.0),
        ("1303", "Cash in Hand", 700_000.0, 0.0),
        ("1401", "MR ADNAN", 150_000.0, 0.0),
        ("1402", "Al-Karam Traders", 130_000.0, 0.0),
        ("2001", "Trade Creditors", 0.0, 180_000.0),
        ("3001", "Sales", 0.0, 900_000.0),
        ("4001", "Purchases", 500_000.0, 0.0),
        ("4002", "Salaries Expense", 600_000.0, 0.0),
    ]
    cases.append(CorpusCase(
        name="naming_03_party_subledger_accounts",
        dimension="naming",
        description=("Personal and trading-name sub-ledger accounts cannot be classified "
                     "from the title and must reach suspense, not administrative expenses."),
        sheets=[("Trial Balance", rows_4col(party))],
        expect_accounts=len(party),
        expect_total_dr=sum(r[2] for r in party),
        expect_total_cr=sum(r[3] for r in party),
        # Assets: cash 700,000 + suspense 280,000 = 980,000
        expect_total_assets=980_000.0,
        # 900,000 - 500,000 - 600,000 = -200,000; suspense must not touch profit
        expect_net_profit=-200_000.0,
        expect_classifications={
            "MR ADNAN": "sofp.ca.suspense",
            "Al-Karam Traders": "sofp.ca.suspense",
        },
        enforce_health_gate=False,
    ))

    return cases


def _balance_cases() -> List[CorpusCase]:
    cases: List[CorpusCase] = []

    # Transposition with paisa intact: 150,000.75 keyed as 510,000.75.
    paisa = [list(r) for r in BASE_LEDGER]
    paisa[5] = ["1303", "Cash in Hand", 510_000.75, 0.0]
    paisa[6] = ["2001", "Trade Creditors", 0.0, 180_000.75]
    cases.append(CorpusCase(
        name="balance_01_transposition_with_paisa",
        dimension="balance",
        description=("Cash keyed as 510,000.75 instead of 150,000.75. The variance of "
                     "360,000 is divisible by 9 and the digits are a transposition."),
        sheets=[("Trial Balance", rows_4col(
            [(c, n, d, cr) for c, n, d, cr in paisa]))],
        expect_status="RECOVERED_WARNING",
        expect_total_dr=BASE_DR + 360_000.75,
        expect_total_cr=BASE_CR + 0.75,
        expect_total_assets=BASE_ASSETS + 0.75,
        expect_net_profit=BASE_NET_PROFIT,
        expect_message_contains="Heuristic 2",
    ))

    # Inverted entry: rent expense 80,000 posted to the credit side, so the
    # variance is twice the balance.
    inverted = [list(r) for r in BASE_LEDGER]
    inverted[10] = ["4003", "Rent Expense", 0.0, 80_000.0]
    cases.append(CorpusCase(
        name="balance_02_inverted_entry",
        dimension="balance",
        description=("Rent expense posted to the credit side. Only an account holding "
                     "half the variance, on the side that closes it, can be the cause."),
        sheets=[("Trial Balance", rows_4col(
            [(c, n, d, cr) for c, n, d, cr in inverted]))],
        expect_status="RECOVERED_WARNING",
        expect_total_dr=BASE_DR - 80_000.0,
        expect_total_cr=BASE_CR + 80_000.0,
        expect_total_assets=BASE_ASSETS,
        expect_net_profit=BASE_NET_PROFIT,
        expect_classifications={"Rent Expense": "pl.admin"},
        expect_message_contains="Heuristic 1",
    ))

    # An account carrying movement on both sides in one row.
    two_sided = [list(r) for r in BASE_LEDGER]
    two_sided[5] = ["1303", "Cash in Hand", 250_000.0, 100_000.0]
    cases.append(CorpusCase(
        name="balance_03_two_sided_rows",
        dimension="balance",
        description=("Cash shows both a debit and a credit in one row; the net is what "
                     "the statements and the disclosure note must both use."),
        sheets=[("Trial Balance", rows_4col(
            [(c, n, d, cr) for c, n, d, cr in two_sided]))],
        expect_total_dr=BASE_DR + 100_000.0,
        expect_total_cr=BASE_CR + 100_000.0,
    ))

    # An unexplained residual: refused by default.
    unbalanced = [list(r) for r in BASE_LEDGER]
    unbalanced[6] = ["2001", "Trade Creditors", 0.0, 133_000.0]
    unbalanced_rows = rows_4col([(c, n, d, cr) for c, n, d, cr in unbalanced])
    cases.append(CorpusCase(
        name="balance_04_unexplained_residual",
        dimension="balance",
        description=("A 47,000 residual that no heuristic explains. It must be reported, "
                     "not capitalised into working capital."),
        sheets=[("Trial Balance", unbalanced_rows)],
        expect_status="FAILED_CRITICAL",
        expect_total_dr=BASE_DR,
        expect_total_cr=BASE_CR - 47_000.0,
        expect_total_assets=None,
        expect_net_profit=None,
        expect_message_contains="does not balance",
    ))

    cases.append(CorpusCase(
        name="balance_05_residual_plug_opted_in",
        dimension="balance",
        description=("The same residual with the plug explicitly enabled: compiles, but "
                     "must be reported as an unsupported balancing entry."),
        sheets=[("Trial Balance", unbalanced_rows)],
        expect_status="RECOVERED_WARNING",
        expect_total_dr=BASE_DR,
        expect_total_cr=BASE_CR - 47_000.0,
        expect_total_assets=None,
        expect_net_profit=BASE_NET_PROFIT,
        expect_message_contains="unsupported",
        allow_plug=True,
    ))

    # Profit already appropriated to equity, P&L accounts closed.
    closed = [
        ("1001", "Capital Account", 0.0, 1_000_000.0),
        ("1002", "Current Year Profit", 0.0, 120_000.0),
        ("1201", "Plant and Machinery", 800_000.0, 0.0),
        ("1202", "Accumulated Depreciation", 0.0, 200_000.0),
        ("1301", "Stock in Trade", 300_000.0, 0.0),
        ("1302", "Trade Debtors", 250_000.0, 0.0),
        ("1303", "Cash in Hand", 150_000.0, 0.0),
        ("2001", "Trade Creditors", 0.0, 180_000.0),
    ]
    cases.append(CorpusCase(
        name="balance_06_preclosed_profit_summary",
        dimension="balance",
        description=("The result has already been appropriated to equity and the P&L "
                     "accounts are closed, so net profit for the period is nil."),
        sheets=[("Trial Balance", rows_4col(closed))],
        expect_accounts=len(closed),
        expect_total_dr=1_500_000.0,
        expect_total_cr=1_500_000.0,
        expect_total_assets=BASE_ASSETS,
        expect_net_profit=0.0,
        expect_classifications={"Current Year Profit": "sofp.eq.cy_profit_summary"},
    ))

    return cases


def _corruption_cases() -> List[CorpusCase]:
    broken = [list(r) for r in BASE_LEDGER]
    broken_rows = rows_4col([(c, n, d, cr) for c, n, d, cr in broken])
    for row in broken_rows:
        if row[1] in ("Stock in Trade", "Trade Debtors", "Sales"):
            row[2] = "#REF!" if row[2] else row[2]
            row[3] = "#REF!" if row[3] else row[3]

    cases = [CorpusCase(
        name="corrupt_01_ref_errors",
        dimension="corruption",
        description=("Broken formulas left #REF! in amount cells. Those rows cannot be "
                     "read, so the file must be refused rather than silently short."),
        sheets=[("Trial Balance", broken_rows)],
        expect_status="FAILED_CRITICAL",
        expect_accounts=BASE_ACCOUNTS - 3,
        expect_total_dr=None,
        expect_total_cr=None,
        expect_total_assets=None,
        expect_net_profit=None,
        expect_message_contains="corrupted",
    )]

    cases.append(CorpusCase(
        name="corrupt_02_single_sided_extract",
        dimension="corruption",
        description="A bank credit schedule, not a double-entry trial balance.",
        sheets=[("Sheet1", [
            ["Date", "Description", "Credit"],
            ["01-01-2025", "Cheque Deposited", 50_000.0],
            ["02-01-2025", "Cash Deposit", 25_000.0],
        ])],
        expect_status="FAILED_CRITICAL",
        expect_accounts=None,
        expect_total_dr=None,
        expect_total_cr=None,
        expect_total_assets=None,
        expect_net_profit=None,
        expect_message_contains="Single-sided",
    ))

    cases.append(CorpusCase(
        name="corrupt_03_narrative_only",
        dimension="corruption",
        description="A meeting-notes sheet with no ledger structure at all.",
        sheets=[("Sheet1", [
            ["Minutes of the finance meeting"],
            ["Attendees: A. Khan, S. Ahmed"],
            ["Action: circulate the draft accounts"],
        ])],
        expect_status="FAILED_CRITICAL",
        expect_accounts=None,
        expect_total_dr=None,
        expect_total_cr=None,
        expect_total_assets=None,
        expect_net_profit=None,
    ))

    return cases


CASES: List[CorpusCase] = (
    _layout_cases() + _sheet_cases() + _noise_cases()
    + _naming_cases() + _balance_cases() + _corruption_cases()
)


# ---------------------------------------------------------------------
# Materialisation
# ---------------------------------------------------------------------

def write_case(case: CorpusCase, out_dir: Path) -> Path:
    """Write one case to `out_dir` and return its path."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for sheet_name, rows in case.sheets:
        ws = wb.create_sheet(title=sheet_name[:31])
        for row in rows:
            ws.append(list(row))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / case.filename
    wb.save(path)
    return path


def write_manifest(out_dir: Path) -> Path:
    """Write the machine-readable description of the corpus."""
    manifest = {
        "description": "Labelled trial balance corpus for FYP-Module-3.",
        "base_ledger": {
            "total_debits": BASE_DR,
            "total_credits": BASE_CR,
            "total_assets": BASE_ASSETS,
            "net_profit": BASE_NET_PROFIT,
        },
        "cases": [c.manifest_entry() for c in CASES],
    }
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def build_corpus(out_dir: Path) -> List[Path]:
    """Write every case plus the manifest."""
    paths = [write_case(case, out_dir) for case in CASES]
    paths.append(write_manifest(out_dir))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the labelled trial balance corpus.")
    parser.add_argument("--out", default="data/generated", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out)
    paths = build_corpus(out_dir)
    by_dimension: Dict[str, int] = {}
    for case in CASES:
        by_dimension[case.dimension] = by_dimension.get(case.dimension, 0) + 1

    print(f"Wrote {len(paths) - 1} trial balances and a manifest to {out_dir}")
    for dimension, count in sorted(by_dimension.items()):
        print(f"  {dimension:16s} {count:2d} case(s)")


if __name__ == "__main__":
    main()
