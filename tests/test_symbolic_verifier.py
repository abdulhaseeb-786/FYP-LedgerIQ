"""Tests for Symbolic Arithmetic Verifier & Closed-Loop Character Recovery (Module 7)."""

import pytest
from app.modules.document_digitizer.domain.models import (
    ExtractedDocument, DocumentLineItem, BoundingBox
)
from app.modules.document_digitizer.domain.symbolic_verifier import SymbolicArithmeticVerifier


def test_verifier_clean_balanced_document():
    verifier = SymbolicArithmeticVerifier()

    items = [
        DocumentLineItem(row_index=1, description="Office Supplies", amount=5000.0),
        DocumentLineItem(row_index=2, description="Printer Paper", amount=2500.0),
    ]
    doc = ExtractedDocument(
        document_id="doc-01",
        document_type="RECEIPT",
        subtotal=7500.0,
        tax=1350.0,  # 18%
        discount=0.0,
        total=8850.0,
        line_items=items,
    )

    result = verifier.verify_document(doc, auto_disambiguate=True)
    assert result.is_balanced is True
    assert result.discrepancy_delta == 0.0
    assert result.recovery_applied is False
    assert len(result.error_rows) == 0


def test_verifier_closed_loop_csp_recovery_8_vs_3():
    """
    Test scenario:
    True line 2 amount: 3,850.00.
    Simulated OCR misread: 3,350.00 (confusion between 8 and 3).
    Stated Total: 12,036.00 (Subtotal 10,200 + Tax 1,836).
    Discrepancy: 500.00.
    Closed-loop CSP solver must detect that modifying '3' to '8' in row 2 perfectly satisfies ∑ = Total.
    """
    verifier = SymbolicArithmeticVerifier()

    items = [
        DocumentLineItem(row_index=1, description="Electrical Wiring", amount=4200.0),
        DocumentLineItem(
            row_index=2,
            description="Circuit Breaker",
            amount=3350.0,  # OCR misread 3,850 as 3,350
            bbox=BoundingBox.from_pixels(50, 200, 200, 220, 800, 1000)
        ),
        DocumentLineItem(row_index=3, description="Conduit Pipe", amount=2150.0),
    ]
    doc = ExtractedDocument(
        document_id="doc-03",
        document_type="RECEIPT",
        subtotal=10200.0,
        tax=1836.0,
        discount=0.0,
        total=12036.0,
        line_items=items,
    )

    result = verifier.verify_document(doc, auto_disambiguate=True)
    assert result.is_balanced is True
    assert result.recovery_applied is True
    assert result.recovered_token_before == "3,350.00"
    assert result.recovered_token_after == "3,850.00"
    # Verify the line item was updated
    assert items[1].amount == 3850.0
    assert items[1].is_disambiguated is True
    assert "Autonomous CSP Recovery" in items[1].disambiguation_note


def test_verifier_unresolvable_error_generates_ui_crops():
    verifier = SymbolicArithmeticVerifier()

    items = [
        DocumentLineItem(
            row_index=1,
            description="Server Rack",
            amount=50000.0,
            bbox=BoundingBox.from_pixels(100, 300, 300, 330, 800, 1000)
        ),
    ]
    doc = ExtractedDocument(
        document_id="doc-bad",
        document_type="RECEIPT",
        subtotal=50000.0,
        tax=0.0,
        discount=0.0,
        total=99999.0,  # Arbitrary massive discrepancy
        line_items=items,
    )

    result = verifier.verify_document(doc, auto_disambiguate=True)
    assert result.is_balanced is False
    assert result.recovery_applied is False
    assert abs(result.discrepancy_delta) > 1000.0
    assert len(result.disputed_crops) > 0
    # Must contain bounding box for UI Pane 3 visual crop
    assert "bbox_pixels" in result.disputed_crops[0]


def test_verifier_scanned_trial_balance_parity():
    verifier = SymbolicArithmeticVerifier()

    items = [
        DocumentLineItem(row_index=1, description="Cash", debit=100000.0, credit=0.0, amount=100000.0),
        DocumentLineItem(row_index=2, description="Capital", debit=0.0, credit=100000.0, amount=100000.0),
    ]
    doc = ExtractedDocument(
        document_id="tb-01",
        document_type="SCANNED_TRIAL_BALANCE",
        debits_total=100000.0,
        credits_total=100000.0,
        line_items=items,
    )

    result = verifier.verify_document(doc)
    assert result.is_balanced is True
    assert result.discrepancy_delta == 0.0

