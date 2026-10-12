"""Tests for the Intelligent Parity Balancer (Section 4 Heuristics 1, 2, 3)."""

import pytest

from fyp_module3.core.models import StandardizedAccountRecord
from fyp_module3.core.balancer import (
    IntelligentParityBalancer,
    IrreconcilableTrialBalanceError,
    find_transposition_candidate,
    is_transposition_of,
)


def _delta(accounts):
    return round(sum(a.debit for a in accounts) - sum(a.credit for a in accounts), 2)


def test_find_transposition_candidate():
    found, corrected = find_transposition_candidate(54000.0, 9000.0)
    assert found is True
    assert corrected == 45000.0

    found, corrected = find_transposition_candidate(980000.0, 90000.0)
    assert found is True
    assert corrected == 890000.0


def test_transposition_detection_preserves_paisa():
    # Working in integer cents keeps the fractional part intact.
    assert is_transposition_of(540000.75, 450000.75) is True
    assert is_transposition_of(540000.75, 450000.00) is False


def test_balancer_already_balanced(sample_balanced_accounts):
    balancer = IntelligentParityBalancer()
    balanced_accs, audit = balancer.balance_trial_balance(sample_balanced_accounts)
    assert len(audit) == 0
    assert abs(_delta(balanced_accs)) < 0.01


def test_heuristic_1_inverted_balance():
    """A balance on the wrong side moves the variance by twice its value."""
    # Correct ledger: Cash 100,000 Dr, Rent 25,000 Dr, Capital 125,000 Cr.
    # Rent has been posted to the credit side, so Dr = 100,000, Cr = 150,000.
    accounts = [
        StandardizedAccountRecord(account_name="Cash at Bank", debit=100000.0, credit=0.0,
                                  line_item_id="sofp.ca.cash"),
        StandardizedAccountRecord(account_name="Rent Expense", debit=0.0, credit=25000.0,
                                  line_item_id="pl.admin"),
        StandardizedAccountRecord(account_name="Share Capital", debit=0.0, credit=125000.0,
                                  line_item_id="sofp.eq.sharecapital"),
    ]
    assert _delta(accounts) == -50000.0

    balanced_accs, audit = IntelligentParityBalancer().balance_trial_balance(accounts)
    assert any("Heuristic 1" in a.heuristic for a in audit)
    assert abs(_delta(balanced_accs)) < 0.01

    rent = next(a for a in balanced_accs if a.account_name == "Rent Expense")
    assert rent.debit == 25000.0 and rent.credit == 0.0


def test_heuristic_1_does_not_fire_when_flip_would_worsen_variance():
    """Regression: matching |delta| instead of |delta| / 2 inverts the variance.

    Flipping a 50,000 credit when debits are already 50,000 in surplus moves
    the variance to 150,000. The balancer must decline rather than "correct".
    """
    accounts = [
        StandardizedAccountRecord(account_name="Share Capital", debit=0.0, credit=1000000.0,
                                  line_item_id="sofp.eq.sharecapital"),
        StandardizedAccountRecord(account_name="Bank Account", debit=1200000.0, credit=0.0,
                                  line_item_id="sofp.ca.cash"),
        StandardizedAccountRecord(account_name="Cash in hand", debit=0.0, credit=50000.0,
                                  line_item_id="sofp.ca.cash"),
        StandardizedAccountRecord(account_name="Sales", debit=0.0, credit=200000.0,
                                  line_item_id="pl.revenue"),
        StandardizedAccountRecord(account_name="Salaries Expense", debit=100000.0, credit=0.0,
                                  line_item_id="pl.admin"),
    ]
    assert _delta(accounts) == 50000.0

    with pytest.raises(IrreconcilableTrialBalanceError):
        IntelligentParityBalancer().balance_trial_balance(accounts)

    # The rejected flip must not have been left applied.
    cash = next(a for a in accounts if a.account_name == "Cash in hand")
    assert cash.credit == 50000.0 and cash.debit == 0.0


def test_heuristic_2_transposition_error():
    accounts = [
        StandardizedAccountRecord(account_name="Cash at Bank", debit=54000.0, credit=0.0,
                                  line_item_id="sofp.ca.cash"),
        StandardizedAccountRecord(account_name="Capital", debit=0.0, credit=45000.0,
                                  line_item_id="sofp.eq.sharecapital"),
    ]
    balanced_accs, audit = IntelligentParityBalancer().balance_trial_balance(accounts)
    assert any("Heuristic 2" in a.heuristic for a in audit)
    assert abs(_delta(balanced_accs)) < 0.01


def test_heuristic_2_survives_fractional_amounts():
    """Rounding to whole rupees used to hide genuine transpositions."""
    # Cash was keyed as 540,000.75 instead of 450,000.75, leaving debits
    # 90,000 in surplus - a variance divisible by 9.
    accounts = [
        StandardizedAccountRecord(account_name="Cash in hand", debit=540000.75, credit=0.0,
                                  line_item_id="sofp.ca.cash"),
        StandardizedAccountRecord(account_name="Stock in trade", debit=459999.25, credit=0.0,
                                  line_item_id="sofp.ca.stock"),
        StandardizedAccountRecord(account_name="Salaries Expense", debit=290000.0, credit=0.0,
                                  line_item_id="pl.admin"),
        StandardizedAccountRecord(account_name="Share Capital", debit=0.0, credit=1000000.0,
                                  line_item_id="sofp.eq.sharecapital"),
        StandardizedAccountRecord(account_name="Sales", debit=0.0, credit=200000.0,
                                  line_item_id="pl.revenue"),
    ]
    assert _delta(accounts) == 90000.0

    balanced_accs, audit = IntelligentParityBalancer().balance_trial_balance(accounts)
    assert any("Heuristic 2" in a.heuristic for a in audit)
    assert abs(_delta(balanced_accs)) < 0.01

    cash = next(a for a in balanced_accs if a.account_name == "Cash in hand")
    assert cash.debit == 450000.75  # paisa preserved


def test_heuristic_3_plug_is_refused_by_default():
    """An unexplained residual must not be capitalised without consent."""
    accounts = [
        StandardizedAccountRecord(account_name="Cash at Bank", debit=101450.0, credit=0.0,
                                  line_item_id="sofp.ca.cash"),
        StandardizedAccountRecord(account_name="Share Capital", debit=0.0, credit=100000.0,
                                  line_item_id="sofp.eq.sharecapital"),
    ]
    with pytest.raises(IrreconcilableTrialBalanceError, match="1,450.00"):
        IntelligentParityBalancer().balance_trial_balance(accounts)


def test_heuristic_3_working_capital_absorption_when_opted_in():
    accounts = [
        StandardizedAccountRecord(account_name="Cash at Bank", debit=101450.0, credit=0.0,
                                  line_item_id="sofp.ca.cash"),
        StandardizedAccountRecord(account_name="Share Capital", debit=0.0, credit=100000.0,
                                  line_item_id="sofp.eq.sharecapital"),
    ]
    balancer = IntelligentParityBalancer(allow_working_capital_plug=True)
    balanced_accs, audit = balancer.balance_trial_balance(accounts)

    assert any("Heuristic 3" in a.heuristic for a in audit)
    assert any("Unreconciled Timing Difference" in a.account_name for a in balanced_accs)
    assert abs(_delta(balanced_accs)) < 0.01
    assert balancer.plug_applied is True
    assert balancer.plug_amount == 1450.0

    plug = next(a for a in balanced_accs if "Unreconciled" in a.account_name)
    assert plug.confidence == 0.0  # never presented as a confident classification


def test_materiality_ceiling_rejects_plug_even_when_opted_in():
    accounts = [
        StandardizedAccountRecord(account_name="Cash at Bank", debit=105000000.0, credit=0.0,
                                  line_item_id="sofp.ca.cash"),
        StandardizedAccountRecord(account_name="Share Capital", debit=0.0, credit=5000000.0,
                                  line_item_id="sofp.eq.sharecapital"),
    ]
    with pytest.raises(IrreconcilableTrialBalanceError):
        IntelligentParityBalancer(allow_working_capital_plug=True).balance_trial_balance(accounts)
