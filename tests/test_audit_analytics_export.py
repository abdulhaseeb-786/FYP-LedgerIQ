"""Tests for OpenXML Export with Audit Analytics Tab (Module 8 & 9 Integration)."""

import os
from datetime import datetime
import openpyxl
import pytest

from fyp_module3.core.models import StandardizedAccountRecord, AuditEntry
from fyp_module3.exporter.excel_writer import ExcelWorkbookCompiler
from fyp_module3.core.workbook_audit import FormulaEvaluator
from app.modules.audit_analytics.domain.models import (
    AuditRiskReport, BenfordAnalysisResult, BenfordDigitStat,
    ISARatiosReport, RatioValue, IsolationForestReport, FlaggedTransaction
)


@pytest.fixture
def sample_accounts():
    return [
        StandardizedAccountRecord(
            account_name="Share Capital",
            line_item_id="BS_EQUITY_SHARE_CAPITAL",
            note_number=1,
            debit=0.0,
            credit=100000.0,
            confidence=1.0
        ),
        StandardizedAccountRecord(
            account_name="Cash and Bank Balances",
            line_item_id="BS_CA_CASH_EQUIVALENTS",
            note_number=8,
            debit=100000.0,
            credit=0.0,
            confidence=1.0
        ),
    ]


@pytest.fixture
def mock_audit_report():
    benford_stats = [
        BenfordDigitStat(
            digit=d,
            observed_count=100 // d,
            observed_freq=(100 // d) / 100.0,
            expected_freq=0.301 if d == 1 else 0.08,
            difference=0.02,
            z_score=1.45 if d != 9 else 3.12,
            is_anomaly=(d == 9)
        )
        for d in range(1, 10)
    ]
    benford = BenfordAnalysisResult(
        total_evaluated=100,
        excluded_zeros_or_negatives=5,
        mad=0.0125,
        conformity_status="Acceptable Conformity",
        chi_square_stat=14.2,
        p_value=0.08,
        digits=benford_stats,
        is_suspicious=False,
        summary="Ledger exhibits acceptable conformity with Benford distribution."
    )

    ratios = [
        RatioValue(
            code="CR",
            name="Current Ratio",
            category="Liquidity",
            formula_desc="Current Assets / Current Liabilities",
            current_value=2.10,
            prior_value=1.85,
            delta_percentage=13.5,
            benchmark_min=1.1,
            benchmark_max=3.0,
            is_alert=False
        ),
        RatioValue(
            code="DE",
            name="Debt-to-Equity Ratio",
            category="Solvency",
            formula_desc="Total Debt / Total Equity",
            current_value=0.95,
            prior_value=0.50,
            delta_percentage=90.0,
            benchmark_min=None,
            benchmark_max=1.5,
            is_alert=True,
            alert_message="90% surge in leverage"
        ),
    ]
    isa_rep = ISARatiosReport(
        period_current="FY2025",
        period_prior="FY2024",
        ratios=ratios,
        total_alerts=1,
        summary_verdict="1 statutory ratio triggered audit alert."
    )

    flagged = [
        FlaggedTransaction(
            row_index=14,
            voucher_no="JV-9901",
            date=datetime(2025, 6, 28, 23, 15),
            account_code="8099",
            account_name="Suspense Clearing",
            amount=450000.0,
            anomaly_score=0.89,
            risk_level="CRITICAL",
            reasons=["Weekend posting (Saturday)", "Suspense account manipulation"],
            user_id="root_override"
        )
    ]
    ml = IsolationForestReport(
        total_evaluated=500,
        total_flagged=1,
        contamination_rate=0.02,
        high_risk_entries=flagged,
        summary_verdict="1 critical anomaly detected."
    )

    return AuditRiskReport(
        entity_name="Alpha Tech Ltd.",
        reporting_period="FY2025",
        overall_risk_score=72.5,
        risk_classification="HIGH_RISK_AUDIT_REQUIRED",
        benford_analysis=benford,
        isa_520_ratios=isa_rep,
        ml_anomalies=ml,
        key_findings=[
            "Critical suspense account manipulation detected on weekend.",
            "Debt-to-Equity ratio surged by 90.0% YoY."
        ]
    )


def test_export_without_analytics_sheet(tmp_path, sample_accounts):
    out_file = str(tmp_path / "regular_export.xlsx")
    compiler = ExcelWorkbookCompiler(entity_name="Alpha Tech Ltd.", period="June 30, 2025")
    compiler.export_workbook(sample_accounts, [], out_file, audit_risk_report=None)

    wb = openpyxl.load_workbook(out_file)
    assert "Audit Analytics" not in wb.sheetnames
    assert "TB" in wb.sheetnames
    assert "Balance Sheet" in wb.sheetnames


def test_export_with_analytics_sheet(tmp_path, sample_accounts, mock_audit_report):
    out_file = str(tmp_path / "audited_export.xlsx")
    compiler = ExcelWorkbookCompiler(entity_name="Alpha Tech Ltd.", period="June 30, 2025")
    compiler.export_workbook(sample_accounts, [], out_file, audit_risk_report=mock_audit_report)

    wb = openpyxl.load_workbook(out_file, data_only=False)
    assert "Audit Analytics" in wb.sheetnames
    assert len(wb.sheetnames) == 8

    ws = wb["Audit Analytics"]
    # Verify Title & KPI block
    assert "Alpha Tech Ltd." in str(ws.cell(row=1, column=1).value)
    assert "AUDIT ANALYTICAL PROCEDURES" in str(ws.cell(row=2, column=1).value)

    # Check that Risk Score and Classification are written
    found_score = False
    found_benford = False
    found_ratio = False
    found_flagged_jv = False

    for r in range(1, ws.max_row + 1):
        row_vals = [str(ws.cell(row=r, column=c).value) for c in range(1, ws.max_column + 1)]
        row_str = " ".join(row_vals)
        if "72.5 / 100.0" in row_str:
            found_score = True
        if "Acceptable Conformity" in row_str:
            found_benford = True
        if "Debt-to-Equity Ratio" in row_str:
            found_ratio = True
        if "JV-9901" in row_str:
            found_flagged_jv = True

    assert found_score, "Composite risk score was not found on Audit Analytics tab"
    assert found_benford, "Benford conformity was not found on Audit Analytics tab"
    assert found_ratio, "ISA 520 Debt-to-Equity ratio was not found on Audit Analytics tab"
    assert found_flagged_jv, "Flagged journal entry JV-9901 was not found on Audit Analytics tab"

    # Verify Formula Evaluator can process formulas in workbook without error
    evaluator = FormulaEvaluator(wb)
    # Total count formula should be evaluated
    # Locate formula cell
    sum_cell = None
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=2).value
        if v and str(v).startswith("=SUM(B"):
            sum_cell = (r, 2)
            break
    assert sum_cell is not None, "Benford sum formula not found"
    val = evaluator.evaluate("Audit Analytics", ws.cell(row=sum_cell[0], column=2).value)
    assert val > 0, "Benford sum formula evaluated to zero or error"


def test_pipeline_run_compilation_with_audit_analytics(tmp_path, mock_audit_report):
    """Verify that run_compilation passes audit_risk_report through to final exported workbook."""
    from fyp_module3.core.pipeline import run_compilation, PipelineOptions
    tb_file = "data/sample_tbs/TB 1.xlsx"
    if not os.path.exists(tb_file):
        pytest.skip("Sample TB file not found")

    out_file = str(tmp_path / "compiled_with_analytics.xlsx")
    options = PipelineOptions(
        output_file=out_file,
        entity_name="Pipeline Analytics Test Co.",
        period="June 30, 2025",
        audit_risk_report=mock_audit_report,
    )
    outcome = run_compilation(tb_file, options)
    assert outcome.result.status in ("SUCCESS", "RECOVERED_WARNING")
    assert outcome.result.audit_risk_report is not None
    assert outcome.result.audit_risk_report.overall_risk_score == 72.5

    wb = openpyxl.load_workbook(outcome.result.output_file, data_only=False)
    assert "Audit Analytics" in wb.sheetnames
    assert len(wb.sheetnames) == 8


