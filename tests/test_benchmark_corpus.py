"""Benchmark evaluation suite validating against both synthetic and public online datasets."""

import json
from pathlib import Path
import pytest
from app.modules.audit_analytics.infrastructure.gl_parser import GeneralLedgerParser
from app.modules.audit_analytics.domain.pipeline import AuditAnalyticsPipeline

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SYNTHETIC_DIR = DATA_DIR / "synthetic_gl"
PUBLIC_DIR = DATA_DIR / "public_gl"


def test_synthetic_manifest_benchmark():
    """Verify detection accuracy across all 5 synthetic benchmark scenarios against manifest.json."""
    manifest_file = SYNTHETIC_DIR / "manifest.json"
    assert manifest_file.exists(), "Synthetic manifest.json must exist"

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    parser = GeneralLedgerParser()
    pipeline = AuditAnalyticsPipeline()

    # 1. Clean Scenario: Should exhibit close conformity
    clean_file = SYNTHETIC_DIR / "gl_01_clean_benford.xlsx"
    clean_txs = parser.parse_file(str(clean_file))
    clean_report = pipeline.execute_audit(clean_txs)
    assert clean_report.benford_analysis.conformity_status in ("Close Conformity", "Acceptable Conformity")
    assert clean_report.risk_classification == "LOW_RISK"

    # 2. Benford Spike Scenario: Must detect non-conformity on digits 5 or 7
    spike_file = SYNTHETIC_DIR / "gl_02_benford_spike.xlsx"
    spike_txs = parser.parse_file(str(spike_file))
    spike_report = pipeline.execute_audit(spike_txs)
    assert spike_report.benford_analysis.is_suspicious
    flagged_digits = [d.digit for d in spike_report.benford_analysis.digits if d.is_anomaly]
    assert (5 in flagged_digits) or (7 in flagged_digits)

    # 3. Round Numbers Scenario: Must flag large year-end round sums
    round_file = SYNTHETIC_DIR / "gl_03_round_numbers.xlsx"
    round_txs = parser.parse_file(str(round_file))
    round_report = pipeline.execute_audit(round_txs)
    assert round_report.ml_anomalies.total_flagged > 0
    reasons_corpus = " ".join(" ".join(e.reasons) for e in round_report.ml_anomalies.high_risk_entries)
    assert "Round Amount" in reasons_corpus

    # 4. Weekend Override Scenario: Must flag weekend postings
    weekend_file = SYNTHETIC_DIR / "gl_04_weekend_override.xlsx"
    weekend_txs = parser.parse_file(str(weekend_file))
    weekend_report = pipeline.execute_audit(weekend_txs)
    assert weekend_report.ml_anomalies.total_flagged > 0
    reasons_corpus = " ".join(" ".join(e.reasons) for e in weekend_report.ml_anomalies.high_risk_entries)
    assert "Weekend Posting" in reasons_corpus

    # 5. Threshold Splits Scenario: Must flag proximity to approval limit
    splits_file = SYNTHETIC_DIR / "gl_05_threshold_splits.xlsx"
    splits_txs = parser.parse_file(str(splits_file))
    splits_report = pipeline.execute_audit(splits_txs)
    assert splits_report.ml_anomalies.total_flagged > 0
    reasons_corpus = " ".join(" ".join(e.reasons) for e in splits_report.ml_anomalies.high_risk_entries)
    assert "Approval Limit" in reasons_corpus


def test_public_sap_fi_benchmark():
    """Verify ingestion and execution on real SAP FI enterprise schema (500 items)."""
    sap_file = PUBLIC_DIR / "sap_fi_gl_faglflexa.xlsx"
    assert sap_file.exists(), "Public SAP FI benchmark must exist"

    parser = GeneralLedgerParser()
    txs = parser.parse_file(str(sap_file))
    assert len(txs) == 500

    pipeline = AuditAnalyticsPipeline()
    report = pipeline.execute_audit(txs, entity_name="Enterprise SAP FI Client")
    assert report.benford_analysis.total_evaluated == 500
    assert 0.0 <= report.overall_risk_score <= 100.0


def test_public_kaggle_journal_log_benchmark():
    """Verify ingestion and execution on Kaggle multi-column financial journal log (500 entries)."""
    kaggle_file = PUBLIC_DIR / "kaggle_enterprise_journal_log.csv"
    assert kaggle_file.exists(), "Public Kaggle benchmark must exist"

    parser = GeneralLedgerParser()
    txs = parser.parse_file(str(kaggle_file))
    assert len(txs) == 500

    pipeline = AuditAnalyticsPipeline()
    report = pipeline.execute_audit(txs, entity_name="Kaggle Enterprise Benchmark")
    assert report.benford_analysis.total_evaluated == 500
    assert 0.0 <= report.overall_risk_score <= 100.0
