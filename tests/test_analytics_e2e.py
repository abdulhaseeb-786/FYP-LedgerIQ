"""End-to-End integration test suite for Audit Analytics Engine."""

import pytest
from datetime import datetime
from app.modules.audit_analytics.domain.models import GLTransactionRecord
from app.modules.audit_analytics.domain.pipeline import AuditAnalyticsPipeline


def generate_mixed_ledger_dataset() -> list[GLTransactionRecord]:
    """Build a realistic mini general ledger with clean entries and injected anomalies."""
    records = []
    # 1. Routine operations: 150 normal entries
    for i in range(1, 151):
        dt = datetime(2025, 2, (i % 25) + 1, 10, 30)
        amt = round(150.0 + (i * 28.75), 2)
        records.append(
            GLTransactionRecord(
                row_index=i,
                voucher_no=f"JV-2025-{i:04d}",
                date=dt,
                account_code="5010",
                account_name="Cost of Goods Sold",
                narration="Standard operational cost",
                debit=amt,
                credit=0.0,
                net_amount=amt,
                user_id="junior_acc",
            )
        )

    # 2. Injected Anomalies:
    # A. Weekend round-amount managerial override
    records.append(
        GLTransactionRecord(
            row_index=151,
            voucher_no="JV-2025-OVERRIDE",
            date=datetime(2025, 2, 23, 23, 45),  # Sunday midnight
            account_code="9999",
            account_name="Suspense Clearing Account",
            narration="Late night manual balancing transfer",
            debit=500000.0,
            credit=0.0,
            net_amount=500000.0,
            user_id="mgr_override",
        )
    )
    # B. Split transaction just below 50k limit
    records.append(
        GLTransactionRecord(
            row_index=152,
            voucher_no="JV-2025-SPLIT-01",
            date=datetime(2025, 2, 14, 15, 0),
            account_code="5070",
            account_name="Legal & Professional Fees",
            narration="Advisory invoice split tranche A",
            debit=49800.0,
            credit=0.0,
            net_amount=49800.0,
            user_id="senior_acc",
        )
    )
    return records


def test_pipeline_end_to_end():
    """Verify execution of full audit analytics pipeline from records to report."""
    dataset = generate_mixed_ledger_dataset()
    pipeline = AuditAnalyticsPipeline()

    tb_current = {
        "current_assets": 2000000.0,
        "current_liabilities": 1000000.0,
        "revenue": 8000000.0,
        "gross_profit": 2400000.0,
        "operating_profit": 900000.0,
        "net_profit": 650000.0,
        "total_assets": 5000000.0,
        "total_liabilities": 2000000.0,
        "total_equity": 3000000.0,
    }
    tb_prior = {
        "current_assets": 1800000.0,
        "current_liabilities": 950000.0,
        "revenue": 7000000.0,
        "gross_profit": 2200000.0,
        "operating_profit": 850000.0,
        "net_profit": 600000.0,
        "total_assets": 4500000.0,
        "total_liabilities": 1900000.0,
        "total_equity": 2600000.0,
    }

    report = pipeline.execute_audit(
        transactions=dataset,
        entity_name="Prime Textile Mills Ltd",
        reporting_period="FY2024-25",
        current_tb_balances=tb_current,
        prior_tb_balances=tb_prior,
    )

    assert report.entity_name == "Prime Textile Mills Ltd"
    assert 0.0 <= report.overall_risk_score <= 100.0
    assert report.risk_classification in ("LOW_RISK", "MODERATE_RISK", "HIGH_RISK_AUDIT_REQUIRED")

    # Benford checks
    assert report.benford_analysis.total_evaluated == len(dataset)
    assert len(report.benford_analysis.digits) == 9

    # ML checks: Overrides should be detected
    assert report.ml_anomalies.total_flagged >= 1
    flagged_vouchers = [f.voucher_no for f in report.ml_anomalies.high_risk_entries]
    assert "JV-2025-OVERRIDE" in flagged_vouchers

    # ISA 520 Ratio checks
    assert report.isa_520_ratios is not None
    assert len(report.isa_520_ratios.ratios) >= 10

    # Key findings & recommendations
    assert len(report.key_findings) > 0
    assert len(report.audit_recommendations) > 0
