"""Module 2: Year-End Adjusting Journal Entry (AJE) & Working Paper Engine.

Core Types and Data Models.
Deterministic accounting arithmetic using exact fixed-point Decimals.
Debits are signed positive (+), Credits are signed negative (-).
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable, Sequence

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")
PARITY_TOLERANCE = Decimal("0.01")

_STRIP = re.compile(r"[\s, '`]|(?:PKR|RS\.?|USD|\$|€|£)", re.IGNORECASE)
_TRAILING_SIGN = re.compile(r"(CR|DR)\.?$", re.IGNORECASE)
_DASHES = {"-", "--", "‐", "‑", "‒", "–", "—", ""}


def quantise(value: Decimal, places: Decimal = CENTS) -> Decimal:
    """Round to 2 decimal places using standard ROUND_HALF_UP."""
    return value.quantize(places, rounding=ROUND_HALF_UP)


def money(value: Any) -> Decimal:
    """Coerce to a 2dp Decimal. Accepts Decimal, int, str -- never float."""
    if isinstance(value, float):
        raise TypeError("floats are not accepted as money; pass a str or Decimal")
    if isinstance(value, Decimal):
        return quantise(value)
    if isinstance(value, int):
        return quantise(Decimal(value))
    return parse_amount(str(value))


def total(items) -> Decimal:
    """Sum an iterable of Decimals, returning exact 0.00 if empty."""
    acc = Decimal(0)
    for it in items:
        acc += it
    return quantise(acc)


def parse_amount(raw: str) -> Decimal:
    """Parse amount strings like '1,250.00', '(500.00)', '500.00 CR'."""
    s = raw.strip()
    if s in _DASHES:
        return ZERO

    is_parenthesised = s.startswith("(") and s.endswith(")")
    if is_parenthesised:
        s = s[1:-1].strip()

    trailing_sign = None
    m = _TRAILING_SIGN.search(s)
    if m:
        trailing_sign = m.group(1).upper()
        s = s[: m.start()].strip()

    cleaned = _STRIP.sub("", s)
    if not cleaned:
        return ZERO

    val = Decimal(cleaned)
    if is_parenthesised or trailing_sign == "CR":
        val = -val

    return quantise(val)


class Element(enum.StrEnum):
    """Five core IFRS / Companies Act accounting elements."""

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"

    @property
    def natural_side(self) -> Side:
        return _NATURAL_SIDE[self]

    @property
    def is_balance_sheet(self) -> bool:
        return self in (Element.ASSET, Element.LIABILITY, Element.EQUITY)


class Side(enum.StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"

    @property
    def opposite(self) -> Side:
        return Side.CREDIT if self is Side.DEBIT else Side.DEBIT


_NATURAL_SIDE = {
    Element.ASSET: Side.DEBIT,
    Element.EXPENSE: Side.DEBIT,
    Element.LIABILITY: Side.CREDIT,
    Element.EQUITY: Side.CREDIT,
    Element.INCOME: Side.CREDIT,
}


@dataclass(frozen=True, slots=True)
class Account:
    """Chart of Accounts line representation."""

    code: str
    name: str
    element: Element | None = None
    line_code: str | None = None
    note_ref: str | None = None

    @property
    def is_classified(self) -> bool:
        return self.element is not None and self.line_code is not None


@dataclass(slots=True)
class TrialBalanceLine:
    """A single row in the Trial Balance."""

    account: Account
    balance: Decimal  # Signed: debit > 0, credit < 0
    is_subtotal: bool = False

    @property
    def debit(self) -> Decimal:
        return self.balance if self.balance > 0 else ZERO

    @property
    def credit(self) -> Decimal:
        return -self.balance if self.balance < 0 else ZERO

    @property
    def side(self) -> Side:
        return Side.DEBIT if self.balance >= 0 else Side.CREDIT


@dataclass(slots=True)
class TrialBalance:
    """Trial balance state before or after adjustments."""

    period_label: str
    lines: list[TrialBalanceLine] = field(default_factory=list)
    currency: str = "PKR"

    def __iter__(self):
        return iter(self.lines)

    def __len__(self) -> int:
        return len(self.lines)

    def by_code(self, code: str) -> TrialBalanceLine | None:
        return next((ln for ln in self.lines if ln.account.code == code), None)

    @property
    def postable(self) -> list[TrialBalanceLine]:
        return [ln for ln in self.lines if not ln.is_subtotal]

    @property
    def total_debits(self) -> Decimal:
        return total(ln.debit for ln in self.postable)

    @property
    def total_credits(self) -> Decimal:
        return total(ln.credit for ln in self.postable)

    @property
    def parity_delta(self) -> Decimal:
        return quantise(self.total_debits - self.total_credits)

    def of_element(self, element: Element) -> list[TrialBalanceLine]:
        return [ln for ln in self.postable if ln.account.element is element]

    def copy(self) -> TrialBalance:
        return TrialBalance(
            period_label=self.period_label,
            currency=self.currency,
            lines=[replace(ln) for ln in self.lines],
        )


@dataclass(frozen=True, slots=True)
class JournalLine:
    account_code: str
    side: Side
    amount: Decimal
    narration: str = ""

    @property
    def signed(self) -> Decimal:
        return self.amount if self.side is Side.DEBIT else -self.amount


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """A balanced double entry. Invariant: Sum(Signed Lines) == 0.00."""

    ref: str
    date: str
    narration: str
    lines: tuple[JournalLine, ...]
    source_module: str = "module2"
    workings: str = ""

    def __post_init__(self) -> None:
        if len(self.lines) < 2:
            raise ValueError(f"{self.ref}: an entry requires at least two legs")
        drift = total(ln.signed for ln in self.lines)
        if drift != ZERO:
            raise ValueError(f"{self.ref}: double-entry out of balance by {drift}")


@dataclass(frozen=True, slots=True)
class Posting:
    """One leg of an adjusting entry addressed by line code."""

    account_code: str
    account_name: str
    line_code: str
    side: Side
    amount: Decimal


@dataclass(frozen=True, slots=True)
class Draft:
    """Adjusting entry draft returned by an adjustment rule."""

    narration: str
    postings: tuple[Posting, ...]
    workings: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.postings or all(p.amount == ZERO for p in self.postings)


class WorkingSet:
    """Dynamic working paper trial balance during topological adjustment execution."""

    def __init__(self, trial_balance: TrialBalance):
        self.period_label = trial_balance.period_label
        self._lines: dict[str, TrialBalanceLine] = {
            line.account.code: line for line in trial_balance.copy().postable
        }

    def balance(self, account_code: str) -> Decimal:
        line = self._lines.get(account_code)
        return line.balance if line else ZERO

    def line_total(self, line_code: str) -> Decimal:
        return total(
            line.balance for line in self._lines.values() if line.account.line_code == line_code
        )

    def element_total(self, element: Element) -> Decimal:
        return total(
            line.balance for line in self._lines.values() if line.account.element is element
        )

    @property
    def profit_before_tax(self) -> Decimal:
        """Profit = - (Income [negative] + Expenses [positive])."""
        pnl_lines = [
            ln.balance
            for ln in self._lines.values()
            if ln.account.element in (Element.INCOME, Element.EXPENSE)
            and ln.account.line_code != "PL.TAXATION"
        ]
        return quantise(-total(pnl_lines))

    def apply(self, entry: JournalEntry, postings: tuple[Posting, ...]) -> None:
        """Post adjusting journal entries into the active working set."""
        for posting, j_line in zip(postings, entry.lines):
            if posting.account_code not in self._lines:
                # Infer element from line code prefix
                element = (
                    Element.EXPENSE
                    if posting.line_code.startswith("PL.")
                    else Element.ASSET
                    if posting.line_code.startswith("BS.CA")
                    else Element.LIABILITY
                )
                self._lines[posting.account_code] = TrialBalanceLine(
                    Account(
                        code=posting.account_code,
                        name=posting.account_name,
                        element=element,
                        line_code=posting.line_code,
                    ),
                    ZERO,
                )
            target = self._lines[posting.account_code]
            target.balance = quantise(target.balance + j_line.signed)

    def to_trial_balance(self) -> TrialBalance:
        return TrialBalance(
            period_label=self.period_label,
            lines=list(self._lines.values()),
        )
