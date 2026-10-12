"""Tests for the account classification engine."""

from fyp_module3.core.models import StandardizedAccountRecord
from fyp_module3.core.classifier import AccountClassifier


def test_classifier_exact_matches():
    classifier = AccountClassifier()

    cases = [
        ("Cash in hand", 50000.0, 0.0, "sofp.ca.cash", 8),
        ("Plant and Machinery", 1200000.0, 0.0, "sofp.nca.ppe", 4),
        ("Accumulated Depreciation", 0.0, 300000.0, "sofp.nca.accdep", 4),
        ("Trade Debtors", 450000.0, 0.0, "sofp.ca.debtors", 7),
        ("Trade Creditors", 0.0, 250000.0, "sofp.cl.payables", 10),
        ("Salaries and Wages", 180000.0, 0.0, "pl.admin", 12),
        ("Purchases", 750000.0, 0.0, "pl.cos", 11),
        ("Sales Revenue", 0.0, 1500000.0, "pl.revenue", None),
        ("Share Capital", 0.0, 1000000.0, "sofp.eq.sharecapital", 9),
    ]

    for name, dr, cr, expected_line, expected_note in cases:
        acc = StandardizedAccountRecord(account_name=name, debit=dr, credit=cr)
        res = classifier.classify_account(acc)
        assert res.line_item_id == expected_line, f"Failed for {name}: got {res.line_item_id}"
        if expected_note:
            assert res.note_number == expected_note, f"Wrong note for {name}: got {res.note_number}"
        assert res.confidence >= 0.85


def test_classifier_side_disambiguation():
    classifier = AccountClassifier()

    # Loan with Credit -> Liability (sofp.ncl.directorloan or sofp.ncl.ltborrow)
    acc_cr = StandardizedAccountRecord(account_name="Loan Account", debit=0.0, credit=500000.0)
    res_cr = classifier.classify_account(acc_cr)
    assert res_cr.statement == "SOFP"
    assert "liabilit" in res_cr.section.lower() or "borrow" in res_cr.line_item_id.lower() or "director" in res_cr.line_item_id.lower()

    # Advance with Debit -> Current Asset (sofp.ca.advances)
    acc_dr = StandardizedAccountRecord(account_name="Advance to Supplier", debit=120000.0, credit=0.0)
    res_dr = classifier.classify_account(acc_dr)
    assert res_dr.line_item_id == "sofp.ca.advances"
    assert res_dr.statement == "SOFP"

