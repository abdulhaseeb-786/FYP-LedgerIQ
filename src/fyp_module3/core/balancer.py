"""Intelligent Parity Balancer implementing Section 4 auditor heuristics.

Every heuristic here follows the same contract: propose a change, apply it,
and keep it only if it strictly reduces the absolute trial balance variance.
A heuristic that cannot be shown to improve parity is rolled back, because a
speculative "correction" that leaves the ledger worse off is indistinguishable
from data corruption once it reaches a financial statement.
"""

from typing import List, Tuple, Optional, Set
from fyp_module3.core.models import StandardizedAccountRecord, AuditEntry
from fyp_module3.core.taxonomy import get_line_item, SUSPENSE_IDS

PLUG_HEURISTIC = "Heuristic 3 (Working Capital Absorption)"
PLUG_ACCOUNT_CODES = ("9998", "9999")

TOLERANCE = 0.01


class IrreconcilableTrialBalanceError(ValueError):
    """Raised when the ledger cannot be balanced without fabricating an entry."""

    def __init__(self, residual: float, ratio: float, plug_allowed: bool):
        self.residual = residual
        self.ratio = ratio
        hint = (
            "Reconcile the source ledger, or re-run with the working capital "
            "absorption plug explicitly enabled if you accept an unsupported "
            "balancing entry in the statements."
        ) if not plug_allowed else (
            "The variance exceeds the materiality ceiling, so it cannot be absorbed."
        )
        super().__init__(
            f"Trial balance does not balance: residual variance of PKR {abs(residual):,.2f} "
            f"({ratio * 100:.2f}% of total volume) could not be explained by any auditor "
            f"heuristic. {hint}"
        )


def _to_cents(amount: float) -> int:
    return int(round(amount * 100))


def _from_cents(cents: int) -> float:
    return cents / 100.0


def _adjacent_swap_variants(cents: int) -> Set[int]:
    """All values reachable by swapping one adjacent digit pair."""
    digits = str(abs(cents))
    variants: Set[int] = set()
    for i in range(len(digits) - 1):
        if digits[i] == digits[i + 1]:
            continue
        swapped = list(digits)
        swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
        variants.add(int("".join(swapped)))
    return variants


def _slide_variants(cents: int) -> Set[int]:
    """Decimal-point slide errors: the same digits shifted one place."""
    magnitude = abs(cents)
    variants = {magnitude * 10}
    if magnitude % 10 == 0:
        variants.add(magnitude // 10)
    return variants


def is_transposition_of(amount: float, candidate: float) -> bool:
    """True when `candidate` is `amount` with one adjacent digit pair swapped,
    or with the decimal point slid by one place."""
    a, b = _to_cents(amount), _to_cents(candidate)
    if a == b or a == 0 or b == 0:
        return False
    if (a < 0) != (b < 0):
        return False
    magnitude = abs(a)
    target = abs(b)
    return target in _adjacent_swap_variants(magnitude) or target in _slide_variants(magnitude)


def find_transposition_candidate(amount: float, target_diff: float) -> Tuple[bool, float]:
    """Find a digit-swap of `amount` that differs from it by `target_diff`.

    Retained for callers that only know the size of the discrepancy. Works in
    integer cents so that amounts carrying paisa are not silently rounded away.
    """
    cents = _to_cents(amount)
    if len(str(abs(cents))) < 2:
        return False, amount
    target_cents = abs(_to_cents(target_diff))
    for variant in sorted(_adjacent_swap_variants(abs(cents))):
        if abs(abs(cents) - variant) == target_cents:
            return True, _from_cents(variant)
    return False, amount


def _totals(accounts: List[StandardizedAccountRecord]) -> Tuple[float, float, float]:
    total_dr = sum(a.debit for a in accounts)
    total_cr = sum(a.credit for a in accounts)
    return total_dr, total_cr, round(total_dr - total_cr, 2)


class IntelligentParityBalancer:
    """Reconciles trial balance discrepancies while maintaining mathematical integrity.

    `allow_working_capital_plug` defaults to False: an unexplained residual is
    reported rather than capitalised into trade debtors or creditors. Callers
    that genuinely want the plug must ask for it, and the resulting statements
    are flagged as containing an unsupported entry.
    """

    def __init__(
        self,
        allow_working_capital_plug: bool = False,
        materiality_ratio: float = 0.05,
        materiality_amount: float = 500_000.0,
    ):
        self.allow_working_capital_plug = allow_working_capital_plug
        self.materiality_ratio = materiality_ratio
        self.materiality_amount = materiality_amount
        self.plug_applied = False
        self.plug_amount = 0.0

    # -----------------------------------------------------------------
    # Heuristic 1: Inverted balance polarity
    # -----------------------------------------------------------------
    def _try_polarity_flip(
        self, accounts: List[StandardizedAccountRecord], delta: float
    ) -> Optional[AuditEntry]:
        """Flip a single account posted on the wrong side of the ledger.

        Moving a balance of `b` from credit to debit raises the variance by
        `2b`; moving it the other way lowers it by `2b`. So only an account
        holding exactly |delta| / 2, on the side that moves the variance toward
        zero, can fix the ledger. Matching against |delta| itself - as an
        earlier revision did - inverts the variance instead of clearing it.
        """
        required = abs(delta) / 2.0
        if required < TOLERANCE:
            return None

        for acc in accounts:
            if acc.debit > 0 and acc.credit > 0:
                continue  # two-sided rows are not simple polarity errors
            balance = acc.debit if acc.debit > 0 else acc.credit
            if abs(balance - required) > TOLERANCE:
                continue

            is_currently_dr = acc.debit > 0
            # A debit-side balance can only help when debits are in surplus.
            if is_currently_dr and delta <= 0:
                continue
            if not is_currently_dr and delta >= 0:
                continue

            # An account parked in suspense has no meaningful natural side: the
            # classifier put it there precisely because its title and its side
            # disagreed, which is the posting error this heuristic looks for.
            # Reading a natural side off the suspense line item would hide it.
            if (acc.line_item_id or "") in SUSPENSE_IDS:
                expected_side = None
            else:
                line_item = get_line_item(acc.line_item_id or "")
                expected_side = line_item.get("natural", "DR") if line_item else None

            # Only correct accounts sitting opposite their natural side.
            if expected_side is not None:
                if expected_side == "DR" and is_currently_dr:
                    continue
                if expected_side == "CR" and not is_currently_dr:
                    continue

            before_dr, before_cr = acc.debit, acc.credit
            acc.debit, acc.credit = acc.credit, acc.debit
            acc.net_balance = acc.debit - acc.credit

            _, _, new_delta = _totals(accounts)
            if abs(new_delta) >= abs(delta) - TOLERANCE:
                # Did not improve parity: roll back rather than leave a
                # half-applied "correction" behind.
                acc.debit, acc.credit = before_dr, before_cr
                acc.net_balance = acc.debit - acc.credit
                continue

            acc.is_adjusted = True
            acc.side_changed = True
            acc.adjustment_reason = "Heuristic 1: Inverted balance polarity reversed"
            return AuditEntry(
                account_name=acc.account_name,
                account_code=acc.account_code,
                action="Inverted Polarity Correction",
                before_dr=before_dr,
                before_cr=before_cr,
                after_dr=acc.debit,
                after_cr=acc.credit,
                delta=delta,
                heuristic="Heuristic 1 (Exact Balance Offset)",
                explanation=(
                    f"Account '{acc.account_name}' held {balance:,.2f} on the side opposite its "
                    f"natural {expected_side or 'expected'} classification. Reversing the polarity "
                    f"moved the trial balance variance from {delta:,.2f} to {new_delta:,.2f}."
                ),
            )
        return None

    # -----------------------------------------------------------------
    # Heuristic 2: Transposition and slide errors
    # -----------------------------------------------------------------
    def _try_transposition(
        self, accounts: List[StandardizedAccountRecord], delta: float
    ) -> Optional[AuditEntry]:
        """Correct a digit transposition or decimal slide.

        The required correction is derived from the direction of the variance
        rather than matched on its magnitude, so a fix can never push the
        ledger further out of balance. Amounts are compared in integer cents,
        which keeps paisa intact.
        """
        delta_cents = _to_cents(delta)
        if delta_cents == 0 or delta_cents % 9 != 0:
            return None

        for acc in accounts:
            if acc.debit > 0 and acc.credit > 0:
                continue
            on_debit = acc.debit > 0
            amount = acc.debit if on_debit else acc.credit
            if abs(amount) < TOLERANCE:
                continue

            # Reducing a debit lowers the variance; reducing a credit raises it.
            required = amount - delta if on_debit else amount + delta
            if required <= 0 or not is_transposition_of(amount, required):
                continue

            before_dr, before_cr = acc.debit, acc.credit
            if on_debit:
                acc.debit = required
            else:
                acc.credit = required
            acc.net_balance = acc.debit - acc.credit

            _, _, new_delta = _totals(accounts)
            if abs(new_delta) >= abs(delta) - TOLERANCE:
                acc.debit, acc.credit = before_dr, before_cr
                acc.net_balance = acc.debit - acc.credit
                continue

            acc.is_adjusted = True
            acc.adjustment_reason = "Heuristic 2: Digit transposition corrected"
            return AuditEntry(
                account_name=acc.account_name,
                account_code=acc.account_code,
                action="Transposition Correction",
                before_dr=before_dr,
                before_cr=before_cr,
                after_dr=acc.debit,
                after_cr=acc.credit,
                delta=delta,
                heuristic="Heuristic 2 (Transposition Detection)",
                explanation=(
                    f"Variance of {delta:,.2f} is divisible by 9 and '{acc.account_name}' at "
                    f"{amount:,.2f} is a digit transposition of {required:,.2f}. Correcting it "
                    f"moved the variance from {delta:,.2f} to {new_delta:,.2f}."
                ),
            )
        return None

    # -----------------------------------------------------------------
    # Heuristic 3: Working capital absorption (opt-in)
    # -----------------------------------------------------------------
    def _absorb_residual(
        self, accounts: List[StandardizedAccountRecord], delta: float, total_volume: float
    ) -> AuditEntry:
        """Insert an explicit balancing entry for an unexplained residual."""
        abs_delta = abs(delta)
        if delta > 0:
            row = StandardizedAccountRecord(
                account_name="Trade Creditors - Unreconciled Timing Difference",
                account_code="9999",
                debit=0.0,
                credit=abs_delta,
                net_balance=-abs_delta,
                line_item_id="sofp.cl.payables",
                note_number=10,
                confidence=0.0,
                is_adjusted=True,
                adjustment_reason="Heuristic 3: Unsupported balancing entry (credit deficit)",
                classification_source="manual",
            )
        else:
            row = StandardizedAccountRecord(
                account_name="Trade Debtors - Unreconciled Timing Difference",
                account_code="9998",
                debit=abs_delta,
                credit=0.0,
                net_balance=abs_delta,
                line_item_id="sofp.ca.debtors",
                note_number=7,
                confidence=0.0,
                is_adjusted=True,
                adjustment_reason="Heuristic 3: Unsupported balancing entry (debit deficit)",
                classification_source="manual",
            )

        accounts.append(row)
        self.plug_applied = True
        self.plug_amount = abs_delta
        return AuditEntry(
            account_name=row.account_name,
            account_code=row.account_code,
            action="Working Capital Absorption",
            before_dr=0.0,
            before_cr=0.0,
            after_dr=row.debit,
            after_cr=row.credit,
            delta=delta,
            heuristic=PLUG_HEURISTIC,
            explanation=(
                f"UNSUPPORTED ENTRY: a residual variance of PKR {abs_delta:,.2f} "
                f"({abs_delta / total_volume * 100:.2f}% of total volume) could not be "
                "explained by any heuristic and was posted to working capital solely to "
                "force parity. The resulting statements are not supported by the ledger."
            ),
        )

    # -----------------------------------------------------------------
    def balance_trial_balance(
        self, accounts: List[StandardizedAccountRecord]
    ) -> Tuple[List[StandardizedAccountRecord], List[AuditEntry]]:
        """Run the heuristic balancer over a copy of the supplied accounts."""
        self.plug_applied = False
        self.plug_amount = 0.0

        audit_trail: List[AuditEntry] = []
        working = [acc.model_copy() for acc in accounts]

        total_dr, total_cr, delta = _totals(working)
        if abs(delta) < TOLERANCE:
            return working, audit_trail

        entry = self._try_polarity_flip(working, delta)
        if entry is not None:
            audit_trail.append(entry)
            total_dr, total_cr, delta = _totals(working)
            if abs(delta) < TOLERANCE:
                return working, audit_trail

        entry = self._try_transposition(working, delta)
        if entry is not None:
            audit_trail.append(entry)
            total_dr, total_cr, delta = _totals(working)
            if abs(delta) < TOLERANCE:
                return working, audit_trail

        total_volume = max(total_dr, total_cr, 1.0)
        ratio = abs(delta) / total_volume

        over_materiality = ratio > self.materiality_ratio and abs(delta) > self.materiality_amount
        if not self.allow_working_capital_plug or over_materiality:
            raise IrreconcilableTrialBalanceError(
                residual=delta, ratio=ratio, plug_allowed=self.allow_working_capital_plug
            )

        audit_trail.append(self._absorb_residual(working, delta, total_volume))
        return working, audit_trail
