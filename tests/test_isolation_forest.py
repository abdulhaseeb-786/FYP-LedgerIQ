"""Unit tests for unsupervised Isolation Forest anomaly detection on GL transactions."""

import pytest
from datetime import datetime
from app.modules.audit_analytics.domain.models import GLTransactionRecord
from app.modules.audit_analytics.domain.feature_extractor import GLFeatureExtractor
from app.modules.audit_analytics.domain.isolation_forest import GLIsolationForestDetector


def create_synthetic_transaction(
    row_idx: int,
    voucher: str,
    amount: float,
    dt: datetime,
    acc_name: str = "Operating Expense",
    acc_code: str = "5010",
    user_id: str = "junior_acc",
) -> GLTransactionRecord:
    return GLTransactionRecord(
        row_index=row_idx,
        voucher_no=voucher,
        date=dt,
        account_code=acc_code,
        account_name=acc_name,
        narration="Test transaction",
        debit=amount,
        credit=0.0,
        net_amount=amount,
        user_id=user_id,
    )


def test_feature_extractor_matrix_dimensions():
    """Verify that feature extractor outputs correct 2D matrix shape."""
    txs = [
        create_synthetic_transaction(1, "JV-01", 1250.0, datetime(2025, 1, 15, 10, 30)),
        create_synthetic_transaction(2, "JV-02", 50000.0, datetime(2025, 1, 18, 22, 00)),  # Weekend & off hours
    ]
    extractor = GLFeatureExtractor()
    matrix, metadata = extractor.extract_features(txs)

    assert len(matrix) == 2
    assert len(matrix[0]) == len(extractor.FEATURE_NAMES)
    assert len(metadata) == 2
    assert "Weekend Posting (Saturday/Sunday)" in metadata[1]["tags"]


def test_isolation_forest_small_sample_guard():
    """Verify that fewer than 10 transactions safely returns graceful report."""
    txs = [
        create_synthetic_transaction(i, f"JV-{i:02d}", 100.0 * i, datetime(2025, 1, 10, 10, 0))
        for i in range(1, 5)
    ]
    detector = GLIsolationForestDetector()
    report = detector.detect_anomalies(txs)

    assert report.total_evaluated == 4
    assert report.total_flagged == 0
    assert "insufficient transactions" in report.summary_verdict.lower()


def test_isolation_forest_detects_and_ranks_outliers():
    """Verify that injected weekend round-amount anomalies rank at top of risk score."""
    # 1. Generate 100 regular inlier transactions on weekdays with varied non-round amounts
    txs = []
    for i in range(1, 101):
        dt = datetime(2025, 1, (i % 20) + 1, 11, 0)  # Weekdays
        amt = 250.0 + (i * 37.15)
        txs.append(create_synthetic_transaction(i, f"JV-NORM-{i:03d}", amt, dt))

    # 2. Inject 3 severe outliers:
    # Outlier 1: Round 500,000 weekend posting by admin to Suspense account
    txs.append(
        create_synthetic_transaction(
            101, "JV-FRAUD-01", 500000.0, datetime(2025, 1, 19, 23, 30),  # Sunday night
            acc_name="Suspense Clearing Account", acc_code="9999", user_id="mgr_override"
        )
    )
    # Outlier 2: Round 250,000 weekend posting
    txs.append(
        create_synthetic_transaction(
            102, "JV-FRAUD-02", 250000.0, datetime(2025, 1, 18, 22, 15),  # Saturday night
            user_id="mgr_override"
        )
    )

    detector = GLIsolationForestDetector(contamination=0.03, random_state=42)
    report = detector.detect_anomalies(txs)

    assert report.total_evaluated == 102
    assert report.total_flagged >= 2

    # Verify that the injected fraud voucher is among the top flagged entries
    flagged_vouchers = [f.voucher_no for f in report.high_risk_entries]
    assert "JV-FRAUD-01" in flagged_vouchers[:3]

    top_entry = report.high_risk_entries[0]
    assert top_entry.risk_level in ("CRITICAL", "HIGH")
    assert len(top_entry.reasons) >= 2
