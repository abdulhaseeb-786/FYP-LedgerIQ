"""Regression tests for the defects found in the compilation pipeline.

The theme running through most of these: the workbook ships Excel formulas,
so an integrity claim is only meaningful if it is made about the formulas in
the saved file. Every balance assertion here therefore goes through
`audit_workbook`, which re-reads the exported .xlsx and evaluates it.
"""

from pathlib import Path

import openpyxl

from fyp_module3.core.parser import parse_trial_balance, try_parse_numeric, is_total_label
from fyp_module3.core.pipeline import PipelineOptions, run_compilation
from fyp_module3.core.workbook_audit import audit_workbook


def compile_tb(path, tmp_path, name="out.xlsx", **kwargs):
    """Run the pipeline and return (result, audit)."""
    out = str(tmp_path / name)
    outcome = run_compilation(path, PipelineOptions(output_file=out, entity_name="Test Co", **kwargs))
    return outcome


# ---------------------------------------------------------------- exported file

def test_drawings_do_not_vanish_from_the_exported_workbook(make_tb, tmp_path):
    """Drawings were absent from Note 9, so the capital line understated by their value.

    The in-memory check reported a nil variance while the saved workbook was
    out by the whole drawings balance.
    """
    tb = make_tb("drawings.xlsx", [
        [1, "Capital Account", None, 1000000],
        [2, "Drawings", 200000, None],
        [3, "Cash in hand", 900000, None],
        [4, "Sales", None, 500000],
        [5, "Salaries Expense", 400000, None],
    ])
    outcome = compile_tb(tb, tmp_path)
    assert outcome.result.status == "SUCCESS"

    audit = audit_workbook(outcome.result.output_file)
    assert audit.passed, audit.failures
    assert audit.balance_sheet_variance == 0.0

    # The drawings balance must actually appear somewhere on the face.
    ws = openpyxl.load_workbook(outcome.result.output_file)["Notes"]
    names = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    assert any(n and "Drawings" in str(n) for n in names)


def test_account_with_both_debit_and_credit_ties_out(make_tb, tmp_path):
    """Notes took `abs(debit)` while the face line took `debit - credit`."""
    tb = make_tb("bothsides.xlsx", [
        [1, "Share Capital", None, 1000000],
        [2, "Cash in hand", 900000, 100000],
        [3, "Stock in trade", 400000, None],
        [4, "Sales", None, 500000],
        [5, "Salaries Expense", 300000, None],
    ])
    outcome = compile_tb(tb, tmp_path)
    audit = audit_workbook(outcome.result.output_file)
    assert audit.passed, audit.failures
    assert audit.balance_sheet_variance == 0.0


def test_dividend_account_is_rendered_rather_than_leaked(make_tb, tmp_path):
    """`sofp.eq.dividend` was classified but no statement rendered it."""
    tb = make_tb("dividend.xlsx", [
        [1, "Share Capital", None, 1000000],
        [2, "Cash in hand", 900000, None],
        [3, "Dividend", 150000, None],
        [4, "Sales", None, 500000],
        [5, "Salaries Expense", 450000, None],
    ])
    outcome = compile_tb(tb, tmp_path)
    assert outcome.result.status == "SUCCESS", outcome.result.message

    report = outcome.result.verification_report
    assert report.zero_leakage_passed is True
    assert report.unrendered_accounts == []

    audit = audit_workbook(outcome.result.output_file)
    assert audit.passed, audit.failures


def test_every_classified_line_item_is_rendered_by_some_statement():
    """A leakage check that only looks for an empty id cannot catch a real leak."""
    from fyp_module3.core.taxonomy import LINE_ITEMS, ELIMINATED_ID
    from fyp_module3.statements.balance_sheet import RENDERED_LINE_IDS as BS_IDS
    from fyp_module3.statements.profit_loss import RENDERED_LINE_IDS as PL_IDS

    rendered = BS_IDS | PL_IDS | {ELIMINATED_ID}
    missing = [item["id"] for item in LINE_ITEMS if item["id"] not in rendered]
    assert missing == [], f"taxonomy line items no statement renders: {missing}"


def test_cash_flow_statement_reconciles_to_balance_sheet_cash(make_tb, tmp_path):
    """Closing cash was profit-derived and unrelated to the balance sheet figure."""
    tb = make_tb("cashflow.xlsx", [
        [1, "Share Capital", None, 100000],
        [2, "Cash in hand", 100000, None],
        [3, "Audit Fee", 30000, None],
        [4, "Audit Fee Payable", None, 30000],
        [5, "Sales", None, 200000],
        [6, "Salaries Expense", 200000, None],
    ])
    outcome = compile_tb(tb, tmp_path)
    audit = audit_workbook(outcome.result.output_file)
    assert audit.cash_flow_variance == 0.0
    assert audit.passed, audit.failures


def test_equity_statement_ties_to_the_balance_sheet(make_tb, tmp_path):
    """The equity statement counted a different set of line items than the SOFP."""
    tb = make_tb("equity.xlsx", [
        [1, "Share Capital", None, 500000],
        [2, "Retained Earnings", None, 200000],
        [3, "Drawings", 50000, None],
        [4, "Cash in hand", 750000, None],
        [5, "Sales", None, 300000],
        [6, "Salaries Expense", 200000, None],
    ])
    outcome = compile_tb(tb, tmp_path)
    audit = audit_workbook(outcome.result.output_file)
    assert audit.equity_variance == 0.0
    assert audit.passed, audit.failures


def test_note_subtotals_agree_with_the_face_lines_they_feed(make_tb, tmp_path):
    tb = make_tb("notes.xlsx", [
        [1, "Share Capital", None, 600000],
        [2, "Plant and Machinery", 500000, None],
        [3, "Accumulated Depreciation", None, 100000],
        [4, "Trade Debtors", 300000, None],
        [5, "Allowance for Doubtful Debts", None, 20000],
        [6, "Cash in hand", 120000, None],
        [7, "Sales", None, 400000],
        [8, "Salaries Expense", 200000, None],
    ])
    outcome = compile_tb(tb, tmp_path)
    assert outcome.result.verification_report.notes_reconciled is True
    assert outcome.result.verification_report.note_mismatches == []

    audit = audit_workbook(outcome.result.output_file)
    assert audit.passed, audit.failures


# ---------------------------------------------------------------- parsing

def test_account_containing_the_word_total_is_not_treated_as_end_of_table(make_tb, tmp_path):
    """"Total Quality Management Fees" used to truncate the ledger silently."""
    tb = make_tb("totalword.xlsx", [
        [1, "Share Capital", None, 500000],
        [2, "Cash in hand", 300000, None],
        [3, "Stock in trade", 200000, None],
        [4, "Total Quality Management Fees", 100000, None],
        [5, "Sales", None, 600000],
        [6, "Rent Expense", 500000, None],
    ])
    payload = parse_trial_balance(tb)
    assert len(payload.accounts) == 6
    assert any(a.account_name == "Total Quality Management Fees" for a in payload.accounts)


def test_genuine_total_captions_still_end_the_table():
    assert is_total_label("Total") is True
    assert is_total_label("Grand Total") is True
    assert is_total_label("Total Assets") is True
    assert is_total_label("Checksum") is True
    assert is_total_label("Total Quality Management Fees") is False


def test_headerless_sheet_does_not_read_account_codes_as_money(make_tb, tmp_path):
    """Positional detection summed the code column as debits (1001+1002+...)."""
    tb = make_tb("noheader.xlsx", [
        [1001, "Share Capital", None, 500000],
        [1002, "Cash in hand", 500000, None],
        [1003, "Sales", None, 300000],
        [1004, "Salaries", 300000, None],
    ], header=None, title=None)

    payload = parse_trial_balance(tb)
    total_dr = sum(a.debit for a in payload.accounts)
    assert total_dr == 800000.0     # not 4,010 from the code column
    assert abs(payload.delta) < 0.01


def test_multiple_amount_column_pairs_selects_the_balancing_pair(tmp_path):
    """Branch / adjustment / adjusted layouts: the leftmost pair is one branch."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([None, "Branch A", None, "Adjusted Trial", None])
    ws.append(["Account Name", "Debit", "Credit", "Debit", "Credit"])
    ws.append(["Cash in hand", 100000, None, 500000, None])
    ws.append(["Share Capital", None, 20000, None, 500000])
    path = tmp_path / "multipair.xlsx"
    wb.save(path)

    payload = parse_trial_balance(str(path))
    assert sum(a.debit for a in payload.accounts) == 500000.0
    assert abs(payload.delta) < 0.01


def test_unreadable_amounts_are_reported_not_silently_zeroed():
    assert try_parse_numeric("1.234.567") is None    # ambiguous separators
    assert try_parse_numeric("#REF!") is None
    assert try_parse_numeric("abc") is None
    assert try_parse_numeric("(1,234.56)") == -1234.56
    assert try_parse_numeric("5,000 Dr") == 5000.0
    assert try_parse_numeric(None) == 0.0
    assert try_parse_numeric("-") == 0.0


def test_ingestion_statistics_are_measured_not_inferred(make_tb):
    """`junk_rows_count` was the length of a log message list, always 1."""
    tb = make_tb("stats.xlsx", [
        [1, "Share Capital", None, 500000],
        [2, "Cash in hand", 500000, None],
        [3, "Dormant Account", None, None],
        [4, "Another Dormant", 0, 0],
    ])
    payload = parse_trial_balance(tb)
    assert payload.junk_rows_skipped == 2
    assert payload.total_raw_rows >= 4
    assert payload.accounts[0].tb_row_index is not None


# ---------------------------------------------------------------- classification

def test_unrecognised_account_goes_to_suspense_not_administrative_expenses(make_tb, tmp_path):
    """An unknown debit used to land in pl.admin and quietly reduce profit."""
    tb = make_tb("suspense.xlsx", [
        [1, "Share Capital", None, 500000],
        [2, "Cash in hand", 400000, None],
        [3, "XYZQWERTY ZZZ", 100000, None],
        [4, "Sales", None, 300000],
        [5, "Salaries Expense", 300000, None],
    ])
    outcome = compile_tb(tb, tmp_path, enforce_health_gate=False)

    mystery = next(a for a in outcome.accounts if a.account_name == "XYZQWERTY ZZZ")
    assert mystery.line_item_id == "sofp.ca.suspense"
    assert mystery.classification_source == "default"

    # Profit reflects the real expenses only.
    assert outcome.result.verification_report.net_profit == 0.0

    audit = audit_workbook(outcome.result.output_file)
    assert audit.passed, audit.failures


def test_wrong_side_expense_is_not_silently_booked_as_a_liability(make_tb, tmp_path):
    """A credit-side "Salaries Expense" became an accrual and overstated profit."""
    from fyp_module3.core.classifier import AccountClassifier
    from fyp_module3.core.models import StandardizedAccountRecord

    result = AccountClassifier().classify_account(
        StandardizedAccountRecord(account_name="Salaries Expense", debit=0.0, credit=50000.0))
    assert result.line_item_id == "sofp.cl.suspense"
    assert result.source == "default"
    assert result.unclassified_reason


# ---------------------------------------------------------------- balancing

def test_unbalanced_ledger_is_refused_rather_than_plugged(make_tb, tmp_path):
    tb = make_tb("unbalanced.xlsx", [
        [1, "Share Capital", None, 500000],
        [2, "Cash in hand", 400000, None],
        [3, "Stock in trade", 150000, None],
        [4, "Sales", None, 300000],
        [5, "Salaries Expense", 300000, None],
    ])
    outcome = compile_tb(tb, tmp_path)
    assert outcome.result.status == "FAILED_CRITICAL"
    assert "does not balance" in outcome.result.message.lower()
    assert outcome.result.output_file is None


def test_opt_in_plug_is_reported_as_unsupported(make_tb, tmp_path):
    tb = make_tb("plug.xlsx", [
        [1, "Share Capital", None, 500000],
        [2, "Cash in hand", 400000, None],
        [3, "Stock in trade", 150000, None],
        [4, "Sales", None, 300000],
        [5, "Salaries Expense", 300000, None],
    ])
    outcome = compile_tb(tb, tmp_path, allow_working_capital_plug=True)
    assert outcome.result.status == "RECOVERED_WARNING"
    assert "unsupported" in outcome.result.message.lower()
    assert outcome.result.verification_report.contains_balancing_plug is True

    audit = audit_workbook(outcome.result.output_file)
    assert audit.passed, audit.failures


# ---------------------------------------------------------------- reporting

def test_a_workbook_that_does_not_verify_is_marked_unverified(make_tb, tmp_path, monkeypatch):
    """A failed integrity check must not yield a file that looks finished."""
    import fyp_module3.core.pipeline as pipeline_module
    from fyp_module3.core.models import WorkbookAuditResult

    tb = make_tb("marked.xlsx", [
        [1, "Share Capital", None, 500000],
        [2, "Cash in hand", 500000, None],
        [3, "Sales", None, 300000],
        [4, "Salaries Expense", 300000, None],
    ])
    monkeypatch.setattr(
        pipeline_module, "audit_workbook",
        lambda path: WorkbookAuditResult(passed=False, failures=["synthetic failure"]))

    outcome = compile_tb(tb, tmp_path)
    assert outcome.result.status == "FAILED_CRITICAL"
    assert outcome.result.output_file.endswith("_UNVERIFIED.xlsx")
    assert Path(outcome.result.output_file).exists()


def test_workbook_audit_detects_a_corrupted_workbook(make_tb, tmp_path):
    """The audit must actually fail when the file is wrong, not just pass everything."""
    tb = make_tb("corrupt.xlsx", [
        [1, "Share Capital", None, 500000],
        [2, "Cash in hand", 500000, None],
        [3, "Sales", None, 300000],
        [4, "Salaries Expense", 300000, None],
    ])
    outcome = compile_tb(tb, tmp_path)
    assert audit_workbook(outcome.result.output_file).passed is True

    # Break one TB balance; every downstream formula should now disagree.
    path = outcome.result.output_file
    wb = openpyxl.load_workbook(path)
    wb["TB"]["E7"] = 123456.0
    wb.save(path)

    broken = audit_workbook(path)
    assert broken.passed is False
    assert broken.failures


def test_health_gate_runs_for_every_entry_point():
    """The Streamlit app once skipped the gate; all callers share one pipeline now.

    Read as source rather than imported: `app.py` is a Streamlit script that
    runs its whole body on import.
    """
    import fyp_module3

    package_dir = Path(fyp_module3.__file__).parent
    for entry_point in ("app.py", "cli.py", "desktop_bridge.py"):
        source = (package_dir / entry_point).read_text(encoding="utf-8")
        assert "run_compilation" in source, f"{entry_point} does not use the shared pipeline"
        assert "PipelineOptions" in source
        # None of them may re-implement the orchestration locally.
        assert "IntelligentParityBalancer(" not in source, \
            f"{entry_point} re-implements the pipeline instead of calling it"
