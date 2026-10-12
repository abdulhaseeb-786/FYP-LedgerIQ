"""Automated tests for Data Health & Pre-flight Quality Guard on synthetic test cases."""

from pathlib import Path
from fyp_module3.desktop_bridge import process_trial_balance


SYNTHETIC_DIR = Path(__file__).parent.parent / "data" / "synthetic_tbs"


def test_synthetic_extreme_rubbish():
    """Verify that a corrupted, non-accounting sheet with meeting notes is rejected."""
    rubbish_file = SYNTHETIC_DIR / "synthetic_extreme_rubbish.xlsx"
    result = process_trial_balance(str(rubbish_file))

    assert result.status == "FAILED_CRITICAL"
    assert result.health_report.is_processable is False
    assert result.health_report.health_score < 50.0
    assert result.health_report.severity == "CRITICAL_UNPROCESSABLE"
    assert ("data quality gate failed" in result.message.lower()
            or "parsing error" in result.message.lower())


def test_synthetic_massive_imbalance():
    """Verify that an extreme 100M out-of-balance sheet triggers critical health guard."""
    imbalance_file = SYNTHETIC_DIR / "synthetic_massive_imbalance.xlsx"
    result = process_trial_balance(str(imbalance_file))

    assert result.status == "FAILED_CRITICAL"
    assert result.health_report.is_processable is False
    assert result.health_report.severity == "CRITICAL_UNPROCESSABLE"
    # Verify specific critical issue flagged
    crit_issues = [i for i in result.health_report.issues if i.severity == "CRITICAL"]
    assert len(crit_issues) >= 1
    assert any("imbalance" in i.description.lower() or "insufficient" in i.description.lower() for i in crit_issues)


def test_synthetic_gibberish_accounts():
    """Verify that accounts with random symbol-only names and no taxonomy match are rejected."""
    gibberish_file = SYNTHETIC_DIR / "synthetic_gibberish_accounts.xlsx"
    result = process_trial_balance(str(gibberish_file))

    assert result.status == "FAILED_CRITICAL"
    assert result.health_report.is_processable is False
    assert result.health_report.severity == "CRITICAL_UNPROCESSABLE"
    crit_issues = [i for i in result.health_report.issues if i.severity == "CRITICAL"]
    assert any("invalid" in i.description.lower() or "numeric-only" in i.description.lower()
               for i in crit_issues)


def test_synthetic_messy_recoverable(tmp_path):
    """Verify that a messy real-world trial balance with noise, abbreviations, and trailing zeros recovers cleanly."""
    messy_file = SYNTHETIC_DIR / "synthetic_messy_recoverable.xlsx"
    # Never write into the data corpus: a generated workbook left there is
    # picked up as an input file on the next run.
    out_file = tmp_path / "synthetic_messy_recoverable_Compiled.xlsx"

    result = process_trial_balance(str(messy_file), output_file=str(out_file))

    assert result.status == "SUCCESS"
    assert result.health_report.is_processable is True
    assert result.health_report.health_score >= 80.0
    assert result.verification_report is not None
    assert result.verification_report.is_tb_balanced is True
    assert result.verification_report.is_bs_balanced is True
    assert result.verification_report.bs_delta == 0.0
    # Check that Assets == Liabilities + Equity
    assert result.verification_report.total_assets == 26000000.0  # PPE 18M + Dep 0.5M + Stock 2.8M + Debts 3.2M + Cash 1.5M = 26M
    assert result.verification_report.total_liabilities_and_equity == 26000000.0
    assert Path(out_file).exists()

