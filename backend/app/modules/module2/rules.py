"""Module 2: Standard Adjusting Journal Entry Rules.

Each adjustment rule implements:
- `ref`: unique adjustment identifier
- `title`: human-readable title
- `depends_on`: tuple of prerequisite adjustment references (DAG edges)
- `build(working: WorkingSet)`: returns Draft with balanced debit/credit postings
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .models import Draft, Posting, Side, WorkingSet, ZERO, quantise, total
from .schedules import (
    DEFAULT_AGEING,
    Accrual,
    AgeBand,
    DebtorBalance,
    FixedAsset,
    PrepaidContract,
    amortise_prepayment,
    depreciate,
    provision_required,
)

DEPRECIATION_EXPENSE = ("AJE-DEP-EXP", "Depreciation for the year", "PL.ADMIN")
ACCUMULATED_DEPRECIATION = ("AJE-ACC-DEP", "Accumulated depreciation", "BS.NCA.ACC_DEP")
PREPAYMENTS = ("AJE-PREPAID", "Prepayments", "BS.CA.ADVANCES")
ACCRUED_LIABILITIES = ("AJE-ACCRUED", "Accrued liabilities", "BS.CL.TRADE_PAYABLES")
DOUBTFUL_DEBT_EXPENSE = ("AJE-ECL-EXP", "Provision for doubtful debts", "PL.OTHER_EXPENSE")
DOUBTFUL_DEBT_PROVISION = ("AJE-ECL-PROV", "Provision for doubtful debts", "BS.CA.PROV_DOUBTFUL")
WPPF_EXPENSE = ("AJE-WPPF-EXP", "Workers' profit participation fund", "PL.OTHER_EXPENSE")
WPPF_PAYABLE = ("AJE-WPPF-PAY", "Workers' profit participation fund payable", "BS.CL.TRADE_PAYABLES")
TAX_EXPENSE = ("AJE-TAX-EXP", "Provision for taxation", "PL.TAXATION")
TAX_PAYABLE = ("AJE-TAX-PAY", "Provision for taxation", "BS.CL.TAX_PAYABLE")


def _pair(debit: tuple[str, str, str], credit: tuple[str, str, str], amount: Decimal) -> tuple[Posting, ...]:
    return (
        Posting(debit[0], debit[1], debit[2], Side.DEBIT, amount),
        Posting(credit[0], credit[1], credit[2], Side.CREDIT, amount),
    )


@dataclass(slots=True)
class DepreciationCharge:
    """Fixed asset depreciation adjustment."""

    assets: list[FixedAsset]
    period_start: date
    period_end: date
    ref: str = "AJE-01-DEP"
    title: str = "Depreciation charge"
    depends_on: tuple[str, ...] = ()

    def build(self, working: WorkingSet) -> Draft | None:
        schedules = [depreciate(a, self.period_start, self.period_end) for a in self.assets]
        amount = total(s.charge_for_period for s in schedules)
        if amount == ZERO:
            return None
        workings = "\n".join(
            f"{s.asset.description}: {s.asset.method.value} @ {s.asset.rate}% -> PKR {s.charge_for_period:,.2f}"
            for s in schedules
        )
        return Draft(
            narration=f"To record depreciation charge for period ending {self.period_end}",
            postings=_pair(DEPRECIATION_EXPENSE, ACCUMULATED_DEPRECIATION, amount),
            workings=workings,
        )


@dataclass(slots=True)
class PrepaymentRelease:
    """Expense recognition from advance prepayments."""

    contracts: list[PrepaidContract]
    period_start: date
    period_end: date
    ref: str = "AJE-02-PRE"
    title: str = "Prepayment amortisation"
    depends_on: tuple[str, ...] = ()

    def build(self, working: WorkingSet) -> Draft | None:
        releases = [(c, amortise_prepayment(c, self.period_start, self.period_end)) for c in self.contracts]
        amount = total(rel for _, rel in releases)
        if amount == ZERO:
            return None
        workings = "\n".join(
            f"{c.description}: {c.covers_from} to {c.covers_to} -> PKR {rel:,.2f}"
            for c, rel in releases
        )
        exp_target = ("AJE-PRE-EXP", "Prepayment expense release", self.contracts[0].expense_line if self.contracts else "PL.ADMIN")
        return Draft(
            narration=f"To amortise prepaid expenses for period ending {self.period_end}",
            postings=_pair(exp_target, PREPAYMENTS, amount),
            workings=workings,
        )


@dataclass(slots=True)
class AccrualCharge:
    """Accrue unbilled period expenses."""

    accruals: list[Accrual]
    ref: str = "AJE-03-ACR"
    title: str = "Expense accruals"
    depends_on: tuple[str, ...] = ()

    def build(self, working: WorkingSet) -> Draft | None:
        amount = total(a.amount for a in self.accruals)
        if amount == ZERO:
            return None
        workings = "\n".join(f"{a.description}: PKR {a.amount:,.2f} ({a.document_ref})" for a in self.accruals)
        exp_target = ("AJE-ACR-EXP", "Accrued operating expenses", self.accruals[0].expense_line if self.accruals else "PL.ADMIN")
        return Draft(
            narration="To accrue unbilled operating expenses incurred during the period",
            postings=_pair(exp_target, ACCRUED_LIABILITIES, amount),
            workings=workings,
        )


@dataclass(slots=True)
class DoubtfulDebtProvision:
    """IFRS 9 Expected Credit Loss / Bad debt allowance."""

    balances: list[DebtorBalance]
    as_at: date
    bands: tuple[AgeBand, ...] = DEFAULT_AGEING
    ref: str = "AJE-04-ECL"
    title: str = "Provision for doubtful debts"
    depends_on: tuple[str, ...] = ()

    def build(self, working: WorkingSet) -> Draft | None:
        req = provision_required(self.balances, self.as_at, self.bands)
        existing = abs(working.balance(DOUBTFUL_DEBT_PROVISION[0]))
        charge = quantise(req - existing)
        if charge <= ZERO:
            return None
        return Draft(
            narration=f"To adjust provision for doubtful debts to required allowance PKR {req:,.2f}",
            postings=_pair(DOUBTFUL_DEBT_EXPENSE, DOUBTFUL_DEBT_PROVISION, charge),
            workings=f"Required provision: PKR {req:,.2f}, existing allowance: PKR {existing:,.2f}",
        )


@dataclass(slots=True)
class WorkersProfitParticipation:
    """Companies Act statutory Workers' Profit Participation Fund (WPPF 5%)."""

    rate: Decimal = field(default_factory=lambda: Decimal("5"))
    ref: str = "AJE-05-WPPF"
    title: str = "Workers' Profit Participation Fund"
    depends_on: tuple[str, ...] = ("AJE-01-DEP", "AJE-02-PRE", "AJE-03-ACR", "AJE-04-ECL")

    def build(self, working: WorkingSet) -> Draft | None:
        pbt = working.profit_before_tax
        if pbt <= ZERO:
            return None
        charge = quantise(pbt * (self.rate / Decimal(100)))
        return Draft(
            narration=f"To provide for WPPF @ {self.rate}% on profit before tax of PKR {pbt:,.2f}",
            postings=_pair(WPPF_EXPENSE, WPPF_PAYABLE, charge),
            workings=f"PBT: PKR {pbt:,.2f} * {self.rate}% = PKR {charge:,.2f}",
        )


@dataclass(slots=True)
class TaxProvision:
    """Statutory Corporate Income Tax (CIT 29%). Runs after WPPF in DAG."""

    rate: Decimal = field(default_factory=lambda: Decimal("29"))
    ref: str = "AJE-06-TAX"
    title: str = "Provision for taxation"
    depends_on: tuple[str, ...] = ("AJE-05-WPPF",)

    def build(self, working: WorkingSet) -> Draft | None:
        pbt = working.profit_before_tax
        if pbt <= ZERO:
            return None
        charge = quantise(pbt * (self.rate / Decimal(100)))
        return Draft(
            narration=f"To provide for corporate income tax @ {self.rate}% on net taxable profit PKR {pbt:,.2f}",
            postings=_pair(TAX_EXPENSE, TAX_PAYABLE, charge),
            workings=f"Taxable profit: PKR {pbt:,.2f} * {self.rate}% = PKR {charge:,.2f}",
        )


@dataclass(slots=True)
class ManualAdjustment:
    """Manual ad-hoc adjusting entry specified by an auditor."""

    ref: str
    title: str
    debit_code: str
    debit_name: str
    debit_line: str
    credit_code: str
    credit_name: str
    credit_line: str
    amount: Decimal
    narration: str
    depends_on: tuple[str, ...] = ()

    def build(self, working: WorkingSet) -> Draft | None:
        if self.amount <= ZERO:
            return None
        return Draft(
            narration=self.narration,
            postings=_pair(
                (self.debit_code, self.debit_name, self.debit_line),
                (self.credit_code, self.credit_name, self.credit_line),
                self.amount,
            ),
            workings=f"Manual auditor journal entry: PKR {self.amount:,.2f}",
        )
