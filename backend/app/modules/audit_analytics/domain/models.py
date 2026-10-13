"""Domain Data Contracts and Pydantic Schemas for Audit Analytics (ISA 520 / 240)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


class GLTransactionRecord(BaseModel):
    """Normalized single transaction row in a General Ledger log."""
    row_index: int
    voucher_no: str
    date: datetime
    account_code: Optional[str] = None
    account_name: str
    narration: Optional[str] = ""
    debit: float = 0.0
    credit: float = 0.0
    net_amount: float = 0.0
    user_id: Optional[str] = "system"


class BenfordDigitStat(BaseModel):
    """Statistical metric for a single digit (1-9) in first-digit Benford test."""
    digit: int
    observed_count: int
    observed_freq: float
    expected_freq: float
    difference: float
    z_score: float
    is_anomaly: bool


class BenfordAnalysisResult(BaseModel):
    """Result of ISA 240 Benford's Law distribution analysis."""
    total_evaluated: int
    excluded_zeros_or_negatives: int
    mad: float = Field(..., description="Mean Absolute Deviation")
    conformity_status: Literal[
        "Close Conformity",
        "Acceptable Conformity",
        "Marginally Non-Conforming",
        "Non-Conforming (Audit Alert)",
        "Sample Too Small"
    ]
    chi_square_stat: float
    p_value: float
    digits: List[BenfordDigitStat]
    is_suspicious: bool
    summary: str


class RatioValue(BaseModel):
    """Single financial ratio with YoY comparative variance and benchmark thresholds."""
    code: str
    name: str
    category: Literal["Liquidity", "Solvency", "Profitability", "Activity"]
    formula_desc: str
    current_value: Optional[float] = None
    prior_value: Optional[float] = None
    delta_percentage: Optional[float] = None
    benchmark_min: Optional[float] = None
    benchmark_max: Optional[float] = None
    is_alert: bool = False
    alert_message: Optional[str] = None


class ISARatiosReport(BaseModel):
    """ISA 520 Analytical Procedures financial ratio report."""
    period_current: str = "Current Year"
    period_prior: Optional[str] = None
    ratios: List[RatioValue]
    total_alerts: int = 0
    summary_verdict: str


class FlaggedTransaction(BaseModel):
    """Specific transaction isolated by Isolation Forest or heuristic rules."""
    row_index: int
    voucher_no: str
    date: datetime
    account_code: Optional[str] = None
    account_name: str
    amount: float
    anomaly_score: float
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    reasons: List[str]
    user_id: Optional[str] = None


class IsolationForestReport(BaseModel):
    """Result of unsupervised Isolation Forest anomaly detection on GL entries."""
    total_evaluated: int
    total_flagged: int
    contamination_rate: float
    high_risk_entries: List[FlaggedTransaction]
    summary_verdict: str


class AuditRiskReport(BaseModel):
    """Comprehensive composite audit risk report combining all procedures."""
    entity_name: str = "Client Entity"
    reporting_period: str = "FY2024-25"
    overall_risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_classification: Literal["LOW_RISK", "MODERATE_RISK", "HIGH_RISK_AUDIT_REQUIRED"]
    benford_analysis: BenfordAnalysisResult
    isa_520_ratios: Optional[ISARatiosReport] = None
    ml_anomalies: IsolationForestReport
    key_findings: List[str] = Field(default_factory=list)
    audit_recommendations: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)

