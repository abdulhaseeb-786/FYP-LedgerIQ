"""Deterministic Symbolic Arithmetic Verifier & Closed-Loop Character Disambiguator (Module 7).

Seoul Accord CCP GA-4 Core:
1. Enforces accounting conservation laws:
   - Invoices/Receipts: ∑ Line Items + Tax - Discount = Total
   - Trial Balances: ∑ Debits - ∑ Credits = 0.00
2. When Δ ≠ 0.00, executes character-level CSP hypothesis testing (e.g., 8 ↔ 3, 0 ↔ 6)
   to recover misread digits, or isolates pixel bounding boxes for UI Pane 3 auditor verification.
"""

from typing import List, Dict, Any, Optional, Tuple
from app.modules.document_digitizer.domain.models import (
    ExtractedDocument, DocumentLineItem, ArithmeticVerificationResult, BoundingBox
)

TOLERANCE = 0.02

# Standard OCR character confusion substitution pairs and their signed delta
# (char_from, char_to): difference = (char_to - char_from)
OCR_CONFUSION_PAIRS = [
    ("3", "8"),
    ("8", "3"),
    ("0", "6"),
    ("6", "0"),
    ("0", "8"),
    ("8", "0"),
    ("1", "7"),
    ("7", "1"),
    ("5", "6"),
    ("6", "5"),
    ("1", "4"),
    ("4", "1"),
]


class SymbolicArithmeticVerifier:
    """Closed-loop mathematical constraint solver enforcing non-negotiable accounting invariants."""

    def __init__(self, tolerance: float = TOLERANCE):
        self.tolerance = tolerance

    def verify_document(self, doc: ExtractedDocument, auto_disambiguate: bool = True) -> ArithmeticVerificationResult:
        """
        Verify document arithmetic. If imbalance occurs and auto_disambiguate is enabled,
        runs closed-loop CSP recovery.
        """
        if doc.document_type == "SCANNED_TRIAL_BALANCE":
            return self._verify_trial_balance(doc, auto_disambiguate)
        else:
            return self._verify_invoice_or_receipt(doc, auto_disambiguate)

    def _verify_invoice_or_receipt(self, doc: ExtractedDocument, auto_disambiguate: bool) -> ArithmeticVerificationResult:
        """Verifies: ∑ Line Items + Tax - Discount = Total."""
        items_sum = sum(item.amount for item in doc.line_items)
        tax_val = doc.tax or 0.0
        disc_val = doc.discount or 0.0
        calculated_total = items_sum + tax_val - disc_val

        target = doc.total if doc.total is not None else (doc.subtotal if doc.subtotal is not None else calculated_total)
        delta = calculated_total - target

        if abs(delta) <= self.tolerance:
            return ArithmeticVerificationResult(
                is_balanced=True,
                equation_checked="∑ Line Items + Tax - Discount = Grand Total",
                calculated_sum=round(calculated_total, 2),
                target_total=round(target, 2),
                discrepancy_delta=0.0,
                error_rows=[],
                diagnosis="Document is mathematically balanced. Zero arithmetic leakage detected.",
                recovery_applied=False,
            )

        # Imbalance detected (Δ ≠ 0.00). Run closed-loop CSP disambiguation
        if auto_disambiguate and doc.line_items:
            recovered, item_idx, old_val, new_val = self._attempt_character_recovery(
                doc.line_items, tax_val, disc_val, target
            )
            if recovered:
                # Apply recovery to line item
                target_item = doc.line_items[item_idx]
                target_item.amount = new_val
                target_item.is_disambiguated = True
                target_item.disambiguation_note = (
                    f"Autonomous CSP Recovery: Corrected OCR misread '{old_val:,.2f}' to '{new_val:,.2f}' "
                    f"to satisfy total conservation law (Δ = {delta:+,.2f})"
                )

                new_calculated = sum(i.amount for i in doc.line_items) + tax_val - disc_val
                return ArithmeticVerificationResult(
                    is_balanced=True,
                    equation_checked="∑ Line Items + Tax - Discount = Grand Total",
                    calculated_sum=round(new_calculated, 2),
                    target_total=round(target, 2),
                    discrepancy_delta=0.0,
                    error_rows=[target_item.row_index],
                    diagnosis=f"Closed-loop CSP solver autonomously recovered character confusion on row {target_item.row_index}.",
                    recovery_applied=True,
                    recovered_token_before=f"{old_val:,.2f}",
                    recovered_token_after=f"{new_val:,.2f}",
                )

        # Unresolved error: isolate candidate disputed row and produce spatial crops for UI Pane 3
        crops = []
        error_rows = []
        if doc.line_items:
            # Row with amount closest to delta or largest amount is suspect
            suspect_idx = min(range(len(doc.line_items)), key=lambda i: abs(abs(doc.line_items[i].amount) - abs(delta)))
            suspect_item = doc.line_items[suspect_idx]
            error_rows.append(suspect_item.row_index)
            if suspect_item.bbox:
                crops.append({
                    "row_index": suspect_item.row_index,
                    "description": suspect_item.description,
                    "disputed_amount": suspect_item.amount,
                    "bbox_pixels": [suspect_item.bbox.x1, suspect_item.bbox.y1, suspect_item.bbox.x2, suspect_item.bbox.y2],
                    "bbox_normalized": [suspect_item.bbox.ymin, suspect_item.bbox.xmin, suspect_item.bbox.ymax, suspect_item.bbox.xmax],
                })

        return ArithmeticVerificationResult(
            is_balanced=False,
            equation_checked="∑ Line Items + Tax - Discount = Grand Total",
            calculated_sum=round(calculated_total, 2),
            target_total=round(target, 2),
            discrepancy_delta=round(delta, 2),
            error_rows=error_rows,
            diagnosis=f"Arithmetic mismatch: Line items sum ({calculated_total:,.2f}) differs from stated total ({target:,.2f}) by PKR {delta:+,.2f}.",
            recovery_applied=False,
            disputed_crops=crops,
        )

    def _verify_trial_balance(self, doc: ExtractedDocument, auto_disambiguate: bool) -> ArithmeticVerificationResult:
        """Verifies: ∑ Debits - ∑ Credits = 0.00."""
        calc_dr = sum(i.debit for i in doc.line_items)
        calc_cr = sum(i.credit for i in doc.line_items)

        target_dr = doc.debits_total if doc.debits_total is not None else calc_dr
        target_cr = doc.credits_total if doc.credits_total is not None else calc_cr

        delta = calc_dr - calc_cr
        if abs(delta) <= self.tolerance:
            return ArithmeticVerificationResult(
                is_balanced=True,
                equation_checked="∑ Debits - ∑ Credits = 0.00",
                calculated_sum=round(calc_dr, 2),
                target_total=round(calc_cr, 2),
                discrepancy_delta=0.0,
                error_rows=[],
                diagnosis="Trial balance is strictly balanced. Zero debit/credit leakage.",
                recovery_applied=False,
            )

        return ArithmeticVerificationResult(
            is_balanced=False,
            equation_checked="∑ Debits - ∑ Credits = 0.00",
            calculated_sum=round(calc_dr, 2),
            target_total=round(calc_cr, 2),
            discrepancy_delta=round(delta, 2),
            error_rows=[i.row_index for i in doc.line_items if abs(i.debit - abs(delta)) < 1.0 or abs(i.credit - abs(delta)) < 1.0],
            diagnosis=f"Trial balance imbalance: Debits ({calc_dr:,.2f}) exceed Credits ({calc_cr:,.2f}) by PKR {delta:+,.2f}.",
            recovery_applied=False,
        )

    def _attempt_character_recovery(
        self,
        line_items: List[DocumentLineItem],
        tax_val: float,
        disc_val: float,
        target_total: float
    ) -> Tuple[bool, int, float, float]:
        """
        Formulate character confusion hypothesis testing over candidate lines.
        Returns:
            (success: bool, line_index: int, original_amount: float, recovered_amount: float)
        """
        base_sum = sum(i.amount for i in line_items) + tax_val - disc_val
        discrepancy = base_sum - target_total  # we want new_sum - target_total = 0 => change in item = -discrepancy

        for idx, item in enumerate(line_items):
            orig_amt = item.amount
            s_val = f"{orig_amt:.2f}"

            # 1. Test digit substitutions based on OCR confusion matrix
            for c_from, c_to in OCR_CONFUSION_PAIRS:
                if c_from in s_val:
                    # Try substituting each occurrence
                    for pos in range(len(s_val)):
                        if s_val[pos] == c_from:
                            candidate_str = s_val[:pos] + c_to + s_val[pos + 1:]
                            try:
                                candidate_amt = float(candidate_str)
                                change = candidate_amt - orig_amt
                                # If this candidate perfectly eliminates the discrepancy
                                if abs(change + discrepancy) <= self.tolerance or abs((base_sum + change) - target_total) <= self.tolerance:
                                    return True, idx, orig_amt, candidate_amt
                            except ValueError:
                                continue

            # 2. Test dropped decimal point (e.g. 1000.00 vs 10.00)
            if orig_amt >= 100.0:
                cand_decimal = orig_amt / 100.0
                change = cand_decimal - orig_amt
                if abs((base_sum + change) - target_total) <= self.tolerance:
                    return True, idx, orig_amt, cand_decimal

        return False, -1, 0.0, 0.0

