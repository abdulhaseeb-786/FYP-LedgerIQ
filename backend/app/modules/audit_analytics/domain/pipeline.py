"""Audit Analytics Pipeline: Orchestrates Benford, Isolation Forest, and ISA 520 Ratios."""

from typing import List, Dict, Any, Optional
from datetime import datetime

from app.modules.audit_analytics.domain.models import (
    GLTransactionRecord,
    AuditRiskReport,
)
from app.modules.audit_analytics.domain.benford import BenfordAnalyzer
from app.modules.audit_analytics.domain.isolation_forest import GLIsolationForestDetector
from app.modules.audit_analytics.domain.ratios import FinancialRatioAnalyzer


class AuditAnalyticsPipeline:
    """Unified coordinator for forensic audit procedures and anomaly detection."""

    def __init__(
        self,
        benford_z_threshold: float = 2.576,
        ml_contamination: float = 0.03,
        ratio_variance_threshold_pct: float = 15.0,
    ):
        self.benford_analyzer = BenfordAnalyzer(critical_z_threshold=benford_z_threshold)
        self.ml_detector = GLIsolationForestDetector(contamination=ml_contamination)
        self.ratio_analyzer = FinancialRatioAnalyzer(variance_threshold_pct=ratio_variance_threshold_pct)

    def execute_audit(
        self,
        transactions: List[GLTransactionRecord],
        entity_name: str = "Client Entity",
        reporting_period: str = "FY2024-25",
        current_tb_balances: Optional[Dict[str, float]] = None,
        prior_tb_balances: Optional[Dict[str, float]] = None,
    ) -> AuditRiskReport:
        """Run all analytical procedures and synthesize an integrated audit risk report."""
        # 1. Benford First-Digit Analysis
        amounts = [
            abs(tx.net_amount) if tx.net_amount != 0.0 else max(tx.debit, tx.credit)
            for tx in transactions
        ]
        benford_res = self.benford_analyzer.analyze(amounts)

        # 2. Unsupervised Isolation Forest Anomaly Detection
        ml_res = self.ml_detector.detect_anomalies(transactions)

        # 3. ISA 520 Financial Ratios (if TB balances provided)
        ratios_res = None
        if current_tb_balances:
            ratios_res = self.ratio_analyzer.compute_ratios(
                current_data=current_tb_balances,
                prior_data=prior_tb_balances,
                period_current=reporting_period,
                period_prior="Prior Fiscal Year" if prior_tb_balances else None,
            )

        # 4. Composite Risk Score Synthesis (0 - 100 scale)
        risk_score = 0.0
        findings: List[str] = []
        recommendations: List[str] = []

        # A. Benford Component (Max 35 points)
        if benford_res.conformity_status == "Non-Conforming (Audit Alert)":
            risk_score += 35.0
            findings.append(f"Benford's Law non-conformity detected (MAD = {benford_res.mad:.4f}, Chi^2 = {benford_res.chi_square_stat:.2f}).")
            recommendations.append("Perform manual substantive testing on accounts driving leading-digit frequency spikes.")
        elif benford_res.conformity_status == "Marginally Non-Conforming":
            risk_score += 18.0
            findings.append(f"Benford distribution shows marginal divergence (MAD = {benford_res.mad:.4f}).")
        else:
            findings.append(f"Benford's Law distribution conforms to normal operational patterns ({benford_res.conformity_status}).")

        # B. Machine Learning Component (Max 40 points)
        critical_count = sum(1 for e in ml_res.high_risk_entries if e.risk_level == "CRITICAL")
        high_count = sum(1 for e in ml_res.high_risk_entries if e.risk_level == "HIGH")
        total_high = critical_count + high_count

        if critical_count > 0 or high_count > 3:
            ml_penalty = min(40.0, (critical_count * 8.0) + (max(0, high_count - 3) * 2.0))
            risk_score += ml_penalty
            findings.append(f"Isolated {total_high} high-severity transaction anomalies via Isolation Forest.")
            recommendations.append("Inspect voucher attachments and managerial approval authorizations for flagged high-risk entries.")
        else:
            findings.append("No critical multi-attribute journal entry anomalies detected by Isolation Forest.")

        # C. Ratio Component (Max 25 points)
        if ratios_res and ratios_res.total_alerts > 0:
            ratio_penalty = min(25.0, ratios_res.total_alerts * 6.0)
            risk_score += ratio_penalty
            findings.append(f"ISA 520 Analytical Procedures triggered {ratios_res.total_alerts} material ratio variance alerts.")
            recommendations.append("Obtain management representation explaining material period-over-period financial ratio shifts.")

        risk_score = min(100.0, max(0.0, risk_score))

        if risk_score >= 65.0:
            classification = "HIGH_RISK_AUDIT_REQUIRED"
            recommendations.append("Escalate findings to Senior Audit Partner. Broaden substantive sample testing under ISA 240.")
        elif risk_score >= 30.0:
            classification = "MODERATE_RISK"
            recommendations.append("Perform targeted analytical inquiries on specific flagged items before sign-off.")
        else:
            classification = "LOW_RISK"
            recommendations.append("Standard statutory audit procedures are sufficient. No abnormal fraud risks identified.")

        return AuditRiskReport(
            entity_name=entity_name,
            reporting_period=reporting_period,
            overall_risk_score=round(risk_score, 1),
            risk_classification=classification,
            benford_analysis=benford_res,
            isa_520_ratios=ratios_res,
            ml_anomalies=ml_res,
            key_findings=findings,
            audit_recommendations=recommendations,
            generated_at=datetime.now(),
        )
