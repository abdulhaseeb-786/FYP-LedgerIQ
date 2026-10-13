"""Tests for Module 2: Year-End Adjusting Journal Entry DAG Engine.

Author: Baqir (23I-0098)
Module: Module 2 (Year-End Adjusting Journal Entry DAG Engine)
"""

from datetime import date
from decimal import Decimal
import pytest

from backend.app.modules.module2 import (
    Accrual,
    AccrualCharge,
    Account,
    DebtorBalance,
    DepreciationCharge,
    DepreciationMethod,
    DoubtfulDebtProvision,
    Element,
    FixedAsset,
    PrepaidContract,
    PrepaymentRelease,
    TaxProvision,
    TrialBalance,
    TrialBalanceLine,
    WorkersProfitParticipation,
    ZERO,
    depreciate,
    money,
    run as run_adjustments,
    topological_order,
)


def test_topological_sorting_and_dependency_resolution():
    """Verify DAG orders upstream calculations before downstream charges."""
    dep = DepreciationCharge([], date(2024, 7, 1), date(2025, 6, 30))
    wppf = WorkersProfitParticipation()
    tax = TaxProvision()

    order = topological_order([tax, wppf, dep])
    assert order.index("AJE-01-DEP") < order.index("AJE-05-WPPF")
    assert order.index("AJE-05-WPPF") < order.index("AJE-06-TAX")


def test_circular_dependency_detection():
    """Verify circular adjustments are rejected with an explicit error."""
    class CircularA:
        ref = "A"
        title = "A"
        depends_on = ("B",)
        def build(self, w): return None

    class CircularB:
        ref = "B"
        title = "B"
        depends_on = ("A",)
        def build(self, w): return None

    with pytest.raises(ValueError, match="Circular dependency detected"):
        topological_order([CircularA(), CircularB()])


def test_depreciation_calculations():
    """Verify straight line and reducing balance depreciation math."""
    sl_asset = FixedAsset(
        ref="FA-SL",
        description="Delivery Truck",
        category="Vehicles",
        cost=money("1000000"),
        acquired=date(2024, 7, 1),
        method=DepreciationMethod.STRAIGHT_LINE,
        rate=Decimal("20"),
    )
    sl_res = depreciate(sl_asset, date(2024, 7, 1), date(2025, 6, 30))
    assert sl_res.charge_for_period == money("200000.00")
    assert sl_res.closing_carrying_amount == money("800000.00")

    rb_asset = FixedAsset(
        ref="FA-RB",
        description="CNC Machine",
        category="Machinery",
        cost=money("1000000"),
        acquired=date(2024, 7, 1),
        method=DepreciationMethod.REDUCING_BALANCE,
        rate=Decimal("10"),
        accumulated_depreciation=money("200000"),
    )
    rb_res = depreciate(rb_asset, date(2024, 7, 1), date(2025, 6, 30))
    assert rb_res.charge_for_period == money("80000.00")
    assert rb_res.closing_carrying_amount == money("720000.00")


def test_full_dag_execution_and_parity_conservation():
    """Verify adjustment DAG execution preserves exact double-entry parity."""
    tb = TrialBalance(period_label="FY2025")
    raw = [
        ("1010", "Cash", Element.ASSET, "BS.CA", "500000.00"),
        ("1400", "Machinery", Element.ASSET, "BS.NCA", "1000000.00"),
        ("3010", "Share Capital", Element.EQUITY, "BS.EQ", "-1000000.00"),
        ("4010", "Revenue", Element.INCOME, "PL.REVENUE", "-1500000.00"),
        ("5010", "Expenses", Element.EXPENSE, "PL.ADMIN", "1000000.00"),
    ]
    for code, name, elem, line_c, bal in raw:
        tb.lines.append(TrialBalanceLine(Account(code=code, name=name, element=elem, line_code=line_c), money(bal)))

    assert tb.parity_delta == ZERO

    asset = FixedAsset(
        ref="FA-1",
        description="Machine",
        category="Machinery",
        cost=money("1000000"),
        acquired=date(2024, 7, 1),
        method=DepreciationMethod.STRAIGHT_LINE,
        rate=Decimal("10"),
    )

    adjs = [
        DepreciationCharge([asset], date(2024, 7, 1), date(2025, 6, 30)),
        WorkersProfitParticipation(),
        TaxProvision(),
    ]

    res = run_adjustments(tb, adjs)
    assert len(res.entries) == 3
    assert res.adjusted.parity_delta == ZERO
    for entry in res.entries:
        dr = sum(l.amount for l in entry.lines if l.side.value == "debit")
        cr = sum(l.amount for l in entry.lines if l.side.value == "credit")
        assert dr == cr
