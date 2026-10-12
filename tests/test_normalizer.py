"""Tests for text normalization, abbreviation expansion, and token similarity."""

from fyp_module3.core.normalizer import (
    normalize_name, tokenize, jaccard_similarity, bigram_dice_similarity
)


def test_abbreviation_expansion():
    assert normalize_name("A/R") == "receivable"
    assert normalize_name("A/P") == "payable"
    assert normalize_name("Accum. Dep.") == "accumulated depreciation"
    assert normalize_name("PPE") == "property plant and equipment"
    assert normalize_name("Rent Exp.") == "rent expense"


def test_code_stripping():
    assert normalize_name("1001 - Cash in Hand") == "cash in hand"
    assert normalize_name("1006-3 · Honda Civic ACX-058") == "honda civic acx 058"
    assert normalize_name("2004: Trade Creditors") == "trade creditors"


def test_tokenization_and_stopwords():
    tokens = tokenize(normalize_name("Cash and Bank Balances"))
    assert "cash" in tokens
    assert "bank" in tokens
    assert "balances" in tokens
    assert "and" not in tokens  # Stopword


def test_similarity_metrics():
    s1 = "trade debtors"
    s2 = "trade debts"
    assert bigram_dice_similarity(s1, s2) > 0.70
    assert jaccard_similarity(tokenize(s1), tokenize(s2)) > 0.30

