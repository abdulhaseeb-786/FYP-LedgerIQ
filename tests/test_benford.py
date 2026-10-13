"""Unit tests for ISA 240 Benford's Law distribution analysis."""

import math
import random
import pytest
from app.modules.audit_analytics.domain.benford import (
    BenfordAnalyzer,
    extract_leading_digit,
    BENFORD_THEORETICAL,
)


def test_theoretical_probabilities_sum_to_one():
    """Verify that theoretical Benford probabilities sum strictly to 1.0."""
    total = sum(BENFORD_THEORETICAL.values())
    assert abs(total - 1.0) < 1e-9


def test_leading_digit_extraction():
    """Verify first non-zero leading digit extraction across diverse formats."""
    assert extract_leading_digit(1234.56) == 1
    assert extract_leading_digit(0.00543) == 5
    assert extract_leading_digit(987654.0) == 9
    assert extract_leading_digit(-7250.0) == 7
    assert extract_leading_digit(0.0) is None
    assert extract_leading_digit(-0.0) is None


def test_clean_log_distribution_conforms_to_benford():
    """Verify that geometric/log-uniform series achieves Close or Acceptable conformity."""
    random.seed(42)
    # Generate 1500 amounts conforming to Benford
    amounts = [10 ** random.uniform(1.0, 5.5) for _ in range(1500)]

    analyzer = BenfordAnalyzer()
    res = analyzer.analyze(amounts)

    assert res.total_evaluated == 1500
    assert res.excluded_zeros_or_negatives == 0
    assert res.mad < 0.012  # Must be Acceptable or Close Conformity
    assert res.conformity_status in ("Close Conformity", "Acceptable Conformity")
    assert not res.is_suspicious
    assert len(res.digits) == 9


def test_uniform_distribution_violates_benford():
    """Verify that uniform random numbers (unnatural accounting numbers) are rejected."""
    random.seed(42)
    # Uniformly distributed amounts in [1000, 9999] have flat ~11% per digit, violating Benford
    amounts = [float(random.randint(1000, 9999)) for _ in range(2000)]

    analyzer = BenfordAnalyzer()
    res = analyzer.analyze(amounts)

    assert res.mad > 0.015
    assert res.conformity_status == "Non-Conforming (Audit Alert)"
    assert res.is_suspicious
    assert res.chi_square_stat > 30.0
    assert res.p_value < 0.01


def test_small_sample_size_returns_guard_warning():
    """Verify that fewer than 50 transactions safely returns Sample Too Small warning."""
    amounts = [100.0, 250.0, 310.0, 450.0]  # Only 4 transactions
    analyzer = BenfordAnalyzer()
    res = analyzer.analyze(amounts)

    assert res.conformity_status == "Sample Too Small"
    assert not res.is_suspicious
    assert "minimum 50 required" in res.summary.lower()


def test_digit_spike_flagging():
    """Verify that a deliberate spike on digit 7 is isolated and reported."""
    random.seed(42)
    base = [10 ** random.uniform(1.0, 5.0) for _ in range(500)]
    # Inject 250 fake numbers starting with 7
    spikes = [75000.0 + i for i in range(250)]
    combined = base + spikes

    analyzer = BenfordAnalyzer(critical_z_threshold=2.0)
    res = analyzer.analyze(combined)

    digit_7_stat = next(d for d in res.digits if d.digit == 7)
    assert digit_7_stat.is_anomaly
    assert digit_7_stat.z_score > 2.0
    assert res.is_suspicious
