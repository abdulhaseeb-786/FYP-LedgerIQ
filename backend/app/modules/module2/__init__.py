"""Module 2: Year-End Adjusting Journal Entry (AJE) & Working Paper Engine.

Author: Baqir (23I-0098)
Module: Module 2 (Year-End Adjustments DAG Engine)

Provides:
- Non-circular DAG dependency ordering with NetworkX topological scheduling.
- Fixed Asset Depreciation (Straight Line and Reducing Balance).
- Prepayment Amortisation and Accrual recognition.
- Doubtful debt provisions (IFRS 9 Expected Credit Loss).
- Companies Act statutory charges (Workers' Profit Participation Fund 5% and Corporate Tax 29%).
- Exact fixed-point Decimal arithmetic and Trial Balance parity conservation.
"""

from .engine import Adjustment, AdjustmentRun, run, topological_order
from .models import (
    CENTS,
    ZERO,
    Account,
    Draft,
    Element,
    JournalEntry,
    JournalLine,
    Posting,
    Side,
    TrialBalance,
    TrialBalanceLine,
    WorkingSet,
    money,
    parse_amount,
    quantise,
    total,
)
from .rules import (
    AccrualCharge,
    DepreciationCharge,
    DoubtfulDebtProvision,
    ManualAdjustment,
    PrepaymentRelease,
    TaxProvision,
    WorkersProfitParticipation,
)
from .schedules import (
    DEFAULT_AGEING,
    Accrual,
    AgeBand,
    DebtorBalance,
    DepreciationMethod,
    DepreciationSchedule,
    FixedAsset,
    PrepaidContract,
    age_debtors,
    amortise_prepayment,
    depreciate,
    provision_required,
    straight_line_rate,
)
from .service import export_working_papers_to_excel, load_trial_balance_from_csv

__all__ = [
    "Adjustment",
    "AdjustmentRun",
    "run",
    "topological_order",
    "Account",
    "Draft",
    "Element",
    "JournalEntry",
    "JournalLine",
    "Posting",
    "Side",
    "TrialBalance",
    "TrialBalanceLine",
    "WorkingSet",
    "money",
    "quantise",
    "total",
    "ZERO",
    "CENTS",
    "AccrualCharge",
    "DepreciationCharge",
    "DoubtfulDebtProvision",
    "ManualAdjustment",
    "PrepaymentRelease",
    "TaxProvision",
    "WorkersProfitParticipation",
    "Accrual",
    "DebtorBalance",
    "DepreciationMethod",
    "DepreciationSchedule",
    "FixedAsset",
    "PrepaidContract",
    "age_debtors",
    "amortise_prepayment",
    "depreciate",
    "provision_required",
    "straight_line_rate",
    "export_working_papers_to_excel",
    "load_trial_balance_from_csv",
]
