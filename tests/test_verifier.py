"""Unit and integration tests for the StatementVerifier and counter-checking loop."""

from fyp_module3.core.models import StandardizedAccountRecord
from fyp_module3.core.verifier import StatementVerifier
from fyp_module3.statements.notes_compiler import NotesCompiler
from fyp_module3.statements.profit_loss import ProfitLossStatement
from fyp_module3.statements.balance_sheet import BalanceSheetStatement


def test_verifier_perfect_balance():
    """Verify that a standard balanced trial balance passes all theorems with 0 retries."""
    accounts = [
        StandardizedAccountRecord(account_code="101", account_name="Share Capital", debit=0.0, credit=100000.0, line_item_id="sofp.eq.sharecapital"),
        StandardizedAccountRecord(account_code="201", account_name="Bank Borrowing", debit=0.0, credit=50000.0, line_item_id="sofp.ncl.ltborrow"),
        StandardizedAccountRecord(account_code="301", account_name="Trade Creditors", debit=0.0, credit=20000.0, line_item_id="sofp.cl.payables", note_number=10),
        StandardizedAccountRecord(account_code="401", account_name="Sales Revenue", debit=0.0, credit=80000.0, line_item_id="pl.revenue"),
        StandardizedAccountRecord(account_code="501", account_name="Plant and Machinery", debit=120000.0, credit=0.0, line_item_id="sofp.nca.ppe", note_number=4),
        StandardizedAccountRecord(account_code="601", account_name="Cash at Bank", debit=80000.0, credit=0.0, line_item_id="sofp.ca.cash", note_number=8),
        StandardizedAccountRecord(account_code="701", account_name="Administrative Salaries", debit=50000.0, credit=0.0, line_item_id="pl.admin", note_number=11),
    ]
    # Total Dr = 120k + 80k + 50k = 250k
    # Total Cr = 100k + 50k + 20k + 80k = 250k
    # Net Profit = Revenue (80k) - Admin (50k) = 30k
    # Total Equity = Capital (100k) + Net Profit (30k) = 130k
    # Liabilities = Borrowings (50k) + Creditors (20k) = 70k
    # L + E = 130k + 70k = 200k
    # Total Assets = PPE (120k) + Cash (80k) = 200k
    # Assets == Liab + Equity -> Delta = 0.00!

    notes = NotesCompiler()
    pl = ProfitLossStatement(notes)
    bs = BalanceSheetStatement(notes)
    verifier = StatementVerifier()

    report, verified_accs = verifier.run_verification_loop(accounts, notes, pl, bs)

    assert report.is_tb_balanced is True
    assert report.tb_delta == 0.0
    assert report.is_bs_balanced is True
    assert report.bs_delta == 0.0
    assert report.total_assets == 200000.0
    assert report.total_liabilities_and_equity == 200000.0
    assert report.net_profit == 30000.0
    assert report.retries_attempted == 0
    assert report.zero_leakage_passed is True


def test_verifier_preclosed_profit_deduplication():
    """Verify that a trial balance with BOTH detailed P&L accounts AND a pre-closed summary line self-corrects."""
    accounts = [
        StandardizedAccountRecord(account_code="101", account_name="Share Capital", debit=0.0, credit=100000.0, line_item_id="sofp.eq.sharecapital"),
        StandardizedAccountRecord(account_code="102", account_name="Current Year Profit", debit=0.0, credit=30000.0, line_item_id="sofp.eq.cy_profit_summary"),
        StandardizedAccountRecord(account_code="201", account_name="Bank Borrowing", debit=0.0, credit=50000.0, line_item_id="sofp.ncl.ltborrow"),
        StandardizedAccountRecord(account_code="301", account_name="Trade Creditors", debit=0.0, credit=20000.0, line_item_id="sofp.cl.payables", note_number=10),
        StandardizedAccountRecord(account_code="401", account_name="Sales Revenue", debit=0.0, credit=80000.0, line_item_id="pl.revenue"),
        StandardizedAccountRecord(account_code="501", account_name="Plant and Machinery", debit=120000.0, credit=0.0, line_item_id="sofp.nca.ppe", note_number=4),
        StandardizedAccountRecord(account_code="601", account_name="Cash at Bank", debit=80000.0, credit=0.0, line_item_id="sofp.ca.cash", note_number=8),
        StandardizedAccountRecord(account_code="701", account_name="Administrative Salaries", debit=50000.0, credit=0.0, line_item_id="pl.admin", note_number=11),
    ]
    # Without de-duplication:
    # Assets = 120k + 80k = 200k
    # Liab = 50k + 20k = 70k
    # Equity = Capital (100k) + CY Profit (30k) + Net Profit (30k) = 160k
    # Total Liab + Eq = 230k != 200k (Delta = -30k)
    # The verifier identifies that detailed P&L exists, de-duplicates 'Current Year Profit',
    # reducing Equity back to 130k -> Total Liab + Eq = 200k = Assets!

    notes = NotesCompiler()
    pl = ProfitLossStatement(notes)
    bs = BalanceSheetStatement(notes)
    verifier = StatementVerifier()

    report, verified_accs = verifier.run_verification_loop(accounts, notes, pl, bs)
    assert report.is_bs_balanced is True
    assert report.bs_delta == 0.0
    assert report.total_assets == 200000.0
    assert report.total_liabilities_and_equity == 200000.0
    assert len(report.auto_corrections) >= 1
    assert "eliminated" in report.auto_corrections[0].lower()

    # The eliminated account must also lose its note membership, or it would
    # still be itemised inside a disclosure note it no longer feeds.
    summary = next(a for a in verified_accs if a.account_name == "Current Year Profit")
    assert summary.note_number is None
    assert report.zero_leakage_passed is True
