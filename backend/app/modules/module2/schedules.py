"""Module 2: Schedules and Supporting Working Papers.

Provides deterministic arithmetic for:
1. Fixed Asset Depreciation (Straight Line and Reducing Balance).
2. Prepayment Amortisation.
3. Debtor Ageing and Expected Credit Loss (ECL) Allowance.
4. Unrecorded Expense Accruals.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .models import CENTS, ZERO, quantise, total


class DepreciationMethod(enum.StrEnum):
    STRAIGHT_LINE = "straight_line"
    REDUCING_BALANCE = "reducing_balance"


@dataclass(frozen=True, slots=True)
class FixedAsset:
    ref: str
    description: str
    category: str
    cost: Decimal
    acquired: date
    method: DepreciationMethod
    rate: Decimal  # e.g. Decimal("10") means 10%
    residual_value: Decimal = ZERO
    accumulated_depreciation: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class DepreciationSchedule:
    asset: FixedAsset
    period_start: date
    period_end: date
    opening_carrying_amount: Decimal
    charge_for_period: Decimal
    closing_accumulated_depreciation: Decimal
    closing_carrying_amount: Decimal


def straight_line_rate(useful_life_years: int) -> Decimal:
    if useful_life_years <= 0:
        raise ValueError("useful life must be greater than zero")
    return quantise(Decimal(100) / Decimal(useful_life_years))


def depreciate(asset: FixedAsset, period_start: date, period_end: date) -> DepreciationSchedule:
    """Compute period depreciation charge with full day/month exactness."""
    if asset.acquired > period_end:
        return DepreciationSchedule(
            asset=asset,
            period_start=period_start,
            period_end=period_end,
            opening_carrying_amount=asset.cost - asset.accumulated_depreciation,
            charge_for_period=ZERO,
            closing_accumulated_depreciation=asset.accumulated_depreciation,
            closing_carrying_amount=asset.cost - asset.accumulated_depreciation,
        )

    opening_accum = asset.accumulated_depreciation
    opening_nbv = asset.cost - opening_accum
    depreciable_base = asset.cost - asset.residual_value

    effective_start = max(period_start, asset.acquired)
    days_in_period = (period_end - effective_start).days + 1
    total_year_days = 365
    fraction = Decimal(days_in_period) / Decimal(total_year_days)

    if asset.method == DepreciationMethod.STRAIGHT_LINE:
        annual_charge = depreciable_base * (asset.rate / Decimal(100))
        charge = quantise(annual_charge * fraction)
    elif asset.method == DepreciationMethod.REDUCING_BALANCE:
        annual_charge = opening_nbv * (asset.rate / Decimal(100))
        charge = quantise(annual_charge * fraction)
    else:
        raise ValueError(f"Unknown depreciation method: {asset.method}")

    # Cannot depreciate below residual value
    max_charge = max(ZERO, opening_nbv - asset.residual_value)
    final_charge = min(charge, max_charge)

    closing_accum = quantise(opening_accum + final_charge)
    closing_nbv = quantise(asset.cost - closing_accum)

    return DepreciationSchedule(
        asset=asset,
        period_start=period_start,
        period_end=period_end,
        opening_carrying_amount=opening_nbv,
        charge_for_period=final_charge,
        closing_accumulated_depreciation=closing_accum,
        closing_carrying_amount=closing_nbv,
    )


@dataclass(frozen=True, slots=True)
class PrepaidContract:
    ref: str
    description: str
    amount: Decimal
    covers_from: date
    covers_to: date
    expense_line: str = "PL.ADMIN"


def amortise_prepayment(contract: PrepaidContract, period_start: date, period_end: date) -> Decimal:
    """Calculate expense release for prepayment during the active period."""
    total_days = (contract.covers_to - contract.covers_from).days + 1
    if total_days <= 0:
        return ZERO

    active_start = max(period_start, contract.covers_from)
    active_end = min(period_end, contract.covers_to)

    if active_start > active_end:
        return ZERO

    days_in_scope = (active_end - active_start).days + 1
    daily_rate = contract.amount / Decimal(total_days)
    return quantise(daily_rate * Decimal(days_in_scope))


@dataclass(frozen=True, slots=True)
class Accrual:
    ref: str
    description: str
    amount: Decimal
    expense_line: str = "PL.ADMIN"
    document_ref: str = ""


@dataclass(frozen=True, slots=True)
class DebtorBalance:
    customer: str
    amount: Decimal
    invoice_date: date


@dataclass(frozen=True, slots=True)
class AgeBand:
    label: str
    min_days: int
    max_days: int | None
    provision_rate: Decimal  # e.g. Decimal("5") means 5%


DEFAULT_AGEING: tuple[AgeBand, ...] = (
    AgeBand("0-30 days", 0, 30, Decimal("0")),
    AgeBand("31-60 days", 31, 60, Decimal("2")),
    AgeBand("61-90 days", 61, 90, Decimal("5")),
    AgeBand("91-180 days", 91, 180, Decimal("20")),
    AgeBand("181+ days", 181, None, Decimal("50")),
)


def age_debtors(
    balances: list[DebtorBalance], as_at: date, bands: tuple[AgeBand, ...] = DEFAULT_AGEING
) -> dict[str, list[DebtorBalance]]:
    buckets: dict[str, list[DebtorBalance]] = {band.label: [] for band in bands}
    for debtor in balances:
        age = (as_at - debtor.invoice_date).days
        matched = False
        for b in bands:
            if b.max_days is None:
                if age >= b.min_days:
                    buckets[b.label].append(debtor)
                    matched = True
                    break
            elif b.min_days <= age <= b.max_days:
                buckets[b.label].append(debtor)
                matched = True
                break
        if not matched and bands:
            buckets[bands[-1].label].append(debtor)
    return buckets


def provision_required(
    balances: list[DebtorBalance], as_at: date, bands: tuple[AgeBand, ...] = DEFAULT_AGEING
) -> Decimal:
    aged = age_debtors(balances, as_at, bands)
    charge = Decimal(0)
    for band in bands:
        total_in_band = total(d.amount for d in aged.get(band.label, []))
        charge += total_in_band * (band.rate / Decimal(100) if hasattr(band, 'rate') else band.provision_rate / Decimal(100))
    return quantise(charge)
