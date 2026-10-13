"""Unit tests for ISA 520 statutory financial ratios and comparative variance engine."""

import pytest
from app.modules.audit_analytics.domain.ratios import FinancialRatioAnalyzer


@pytest.fixture
def baseline_financials():
    return {
        "current_assets": 1500000.0,
        "current_liabilities": 750000.0,
        "cash": 300000.0,
        "inventory": 450000.0,
        "trade_debtors": 600000.0,
        "total_assets": 4000000.0,
        "total_liabilities": 1800000.0,
        "total_equity": 2200000.0,
        "revenue": 5000000.0,
        "gross_profit": 1500000.0,
        "operating_profit": 600000.0,
        "net_profit": 420000.0,
        "finance_costs": 120000.0,
    }


def test_standard_ratio_calculations(baseline_financials):
    """Verify standard formula calculations for liquidity, solvency, profitability."""
    analyzer = FinancialRatioAnalyzer()
    res = analyzer.compute_ratios(baseline_financials)

    r_map = {r.code: r for r in res.ratios}

    # CR: 1500000 / 750000 = 2.0
    assert r_map["CR"].current_value == 2.0
    assert not r_map["CR"].is_alert

    # QR: (1500000 - 450000) / 750000 = 1050000 / 750000 = 1.4
    assert r_map["QR"].current_value == 1.4
    assert not r_map["QR"].is_alert

    # GPM: (1500000 / 5000000) * 100 = 30.0%
    assert r_map["GPM"].current_value == 30.0

    # NPM: (420000 / 5000000) * 100 = 8.4%
    assert r_map["NPM"].current_value == 8.4

    # DE: 1800000 / 2200000 = 0.818
    assert abs(r_map["DE"].current_value - 0.818) < 0.005

    # IC: 600000 / 120000 = 5.0
    assert r_map["IC"].current_value == 5.0


def test_division_by_zero_resilience():
    """Verify that zero liabilities or revenues return None without crashing."""
    empty_financials = {
        "current_assets": 50000.0,
        "current_liabilities": 0.0,  # Zero denominator
        "revenue": 0.0,
        "total_equity": 0.0,
    }
    analyzer = FinancialRatioAnalyzer()
    res = analyzer.compute_ratios(empty_financials)

    r_map = {r.code: r for r in res.ratios}
    assert r_map["CR"].current_value is None
    assert r_map["GPM"].current_value is None
    assert r_map["DE"].current_value is None


def test_yoy_variance_alert_trigger(baseline_financials):
    """Verify that YoY changes >= 15% trigger ISA 520 audit alerts."""
    prior_financials = dict(baseline_financials)
    # Simulate prior year with higher profitability
    prior_financials["net_profit"] = 700000.0  # 420k current vs 700k prior = -40% drop

    analyzer = FinancialRatioAnalyzer(variance_threshold_pct=15.0)
    res = analyzer.compute_ratios(current_data=baseline_financials, prior_data=prior_financials)

    npm = next(r for r in res.ratios if r.code == "NPM")
    assert npm.is_alert
    assert "Significant YoY drop" in npm.alert_message
    assert res.total_alerts >= 1


def test_benchmark_boundary_alerts(baseline_financials):
    """Verify that values violating min/max benchmarks are flagged."""
    distressed = dict(baseline_financials)
    distressed["current_assets"] = 500000.0
    distressed["current_liabilities"] = 1000000.0  # CR = 0.5 (below 1.10 min)

    analyzer = FinancialRatioAnalyzer()
    res = analyzer.compute_ratios(distressed)

    cr = next(r for r in res.ratios if r.code == "CR")
    assert cr.is_alert
    assert "falls below benchmark min" in cr.alert_message
