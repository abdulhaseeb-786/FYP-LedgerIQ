"""Statement Integrity Verifier and Autonomous Counter-Checking Loop."""

from typing import List, Tuple

from fyp_module3.core.models import StandardizedAccountRecord, VerificationReport
from fyp_module3.core.taxonomy import get_line_item, ELIMINATED_ID
from fyp_module3.statements.notes_compiler import NotesCompiler
from fyp_module3.statements.profit_loss import ProfitLossStatement
from fyp_module3.statements.balance_sheet import BalanceSheetStatement

TOLERANCE = 0.01


def assign_line_item(acc: StandardizedAccountRecord, line_item_id: str, reason: str) -> None:
    """Move an account to a different line item, keeping its note in step.

    Reassigning `line_item_id` without refreshing `note_number` leaves the
    account counted on one face line while still itemised inside another
    statement's note, so the two are always changed together.
    """
    acc.line_item_id = line_item_id
    item = get_line_item(line_item_id)
    acc.note_number = item.get("note_number") if item else None
    acc.is_adjusted = True
    acc.adjustment_reason = reason


class StatementVerifier:
    """Validates generated financial statements against fundamental accounting theorems:

      1. Trial Balance Parity: Sum(Dr) == Sum(Cr)
      2. Balance Sheet Identity: Total Assets == Total Liabilities + Total Equity
      3. Zero Leakage: every account reaches a line that some statement renders
      4. Note Reconciliation: each note subtotal equals the face line it supports
    """

    def __init__(self, max_retries: int = 3):
        self.max_retries = max(1, max_retries)

    # -----------------------------------------------------------------
    def verify_trial_balance(self, accounts: List[StandardizedAccountRecord]) -> Tuple[bool, float]:
        """Verify that trial balance debits equal credits."""
        total_dr = sum(a.debit for a in accounts)
        total_cr = sum(a.credit for a in accounts)
        delta = round(total_dr - total_cr, 2)
        return abs(delta) < TOLERANCE, delta

    def check_zero_leakage(
        self,
        accounts: List[StandardizedAccountRecord],
        bs: BalanceSheetStatement,
        pl: ProfitLossStatement,
    ) -> Tuple[bool, List[str], List[str]]:
        """Verify that every classified account actually reaches a statement.

        An empty line_item_id is not the only way to lose an account: a valid
        id that no statement renders disappears just as completely, and that is
        the case this check exists to catch.
        """
        rendered = set(bs.rendered_line_ids) | set(pl.rendered_line_ids)
        unassigned: List[str] = []
        unrendered: List[str] = []
        for acc in accounts:
            lid = acc.line_item_id or ""
            if not lid:
                unassigned.append(acc.account_name)
            elif lid == ELIMINATED_ID:
                continue  # deliberately eliminated during verification
            elif lid not in rendered:
                unrendered.append(f"{acc.account_name} (mapped to '{lid}', rendered nowhere)")
        return (not unassigned and not unrendered), unassigned, unrendered

    # -----------------------------------------------------------------
    def _compile_all(self, accounts, notes_compiler, pl_compiler, bs_compiler):
        """Run one full compilation pass and return the derived totals."""
        notes_compiler.compile_notes(accounts)
        pl_compiler.compile(accounts)
        bs_compiler.compile(
            accounts,
            net_profit_ref=pl_compiler.net_profit_cell_ref,
            net_profit=pl_compiler.net_profit,
        )
        return round(bs_compiler.total_assets - bs_compiler.total_equity_and_liabilities, 2)

    def run_verification_loop(
        self,
        accounts: List[StandardizedAccountRecord],
        notes_compiler: NotesCompiler,
        pl_compiler: ProfitLossStatement,
        bs_compiler: BalanceSheetStatement,
    ) -> Tuple[VerificationReport, List[StandardizedAccountRecord]]:
        """Compile, evaluate A == L + E, diagnose, self-correct, re-evaluate."""
        working = [a.model_copy() for a in accounts]
        auto_corrections: List[str] = []
        retries = 0

        is_tb_balanced, tb_delta = self.verify_trial_balance(working)
        bs_delta = self._compile_all(working, notes_compiler, pl_compiler, bs_compiler)

        while abs(bs_delta) >= TOLERANCE and retries < self.max_retries:
            retries += 1
            if not self._apply_correction(working, bs_delta, retries, auto_corrections):
                break
            bs_delta = self._compile_all(working, notes_compiler, pl_compiler, bs_compiler)

        leakage_ok, unassigned, unrendered = self.check_zero_leakage(
            working, bs_compiler, pl_compiler)

        note_errors = list(bs_compiler.reconciliation_errors) + list(pl_compiler.reconciliation_errors)
        plug_rows = [a for a in working if (a.adjustment_reason or "").startswith("Heuristic 3")]

        balanced = abs(bs_delta) < TOLERANCE
        if balanced and leakage_ok and not note_errors:
            status = ("Statement integrity verified: Total Assets exactly equals "
                      "Total Liabilities & Equity (A = L + E).")
        elif not balanced:
            status = (f"Balance Sheet integrity variance detected: Assets differ from "
                      f"Liabilities & Equity by PKR {bs_delta:,.2f}.")
        elif note_errors:
            status = "Balance sheet ties, but a disclosure note does not agree with its face line."
        else:
            status = "Balance sheet ties, but one or more accounts reach no statement."

        return VerificationReport(
            is_tb_balanced=is_tb_balanced,
            tb_delta=tb_delta,
            is_bs_balanced=balanced,
            bs_delta=0.0 if balanced else bs_delta,
            total_assets=bs_compiler.total_assets,
            total_liabilities_and_equity=bs_compiler.total_equity_and_liabilities,
            total_equity=bs_compiler.total_equity,
            total_non_current_liabilities=bs_compiler.total_non_current_liabilities,
            total_current_liabilities=bs_compiler.total_current_liabilities,
            net_profit=pl_compiler.net_profit,
            zero_leakage_passed=leakage_ok,
            unassigned_accounts=unassigned,
            unrendered_accounts=unrendered,
            notes_reconciled=not note_errors,
            note_mismatches=note_errors,
            contains_balancing_plug=bool(plug_rows),
            plug_amount=round(sum(abs(a.debit - a.credit) for a in plug_rows), 2),
            retries_attempted=retries,
            auto_corrections=auto_corrections,
            status_message=status,
        ), working

    # -----------------------------------------------------------------
    def _apply_correction(
        self,
        accounts: List[StandardizedAccountRecord],
        bs_delta: float,
        retry: int,
        log: List[str],
    ) -> bool:
        """Diagnose one cause of the imbalance and correct it. True if changed."""
        # Diagnosis A: the trial balance carries both detailed P&L accounts and
        # a pre-closing profit summary, so the summary double-counts the result.
        has_detailed_pl = any((a.line_item_id or "").startswith("pl.") for a in accounts)
        for acc in accounts:
            if has_detailed_pl and acc.line_item_id == "sofp.eq.cy_profit_summary":
                value = acc.credit - acc.debit
                assign_line_item(
                    acc, ELIMINATED_ID,
                    "Eliminated: pre-closing profit summary duplicated by the detailed P&L",
                )
                log.append(
                    f"Self-Correction (Retry {retry}): eliminated '{acc.account_name}' "
                    f"({value:,.2f}) to prevent double-counting against the Profit or Loss "
                    "statement. Its disclosure note membership was removed with it."
                )
                return True

        # Diagnosis B: a balance sitting in the wrong section. Reclassify only
        # when doing so actually closes the gap.
        for acc in accounts:
            balance = acc.credit - acc.debit
            if abs(abs(balance) - abs(bs_delta)) > TOLERANCE and \
               abs(abs(balance * 2) - abs(bs_delta)) > TOLERANCE:
                continue
            info = get_line_item(acc.line_item_id or "")
            if not info or info.get("stmt") != "SOFP":
                continue
            if acc.debit > acc.credit and "liabilit" in info.get("section", "").lower():
                assign_line_item(
                    acc, "sofp.ca.advances",
                    "Re-classified: debit balance held under liabilities",
                )
                log.append(
                    f"Self-Correction (Retry {retry}): re-classified debit balance "
                    f"'{acc.account_name}' from liabilities to Current Assets."
                )
                return True
        return False
