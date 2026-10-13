"""Pydantic v2 schemas for Audit Analytics API endpoints."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.modules.audit_analytics.domain.models import AuditRiskReport


class GLAuditOptionsSchema(BaseModel):
    """Execution options for running General Ledger audit procedures."""
    entity_name: Optional[str] = Field(None, description="Company or reporting entity name")
    reporting_period: Optional[str] = Field(None, description="Fiscal year or period (e.g. FY2024-25)")
    contamination_rate: float = Field(0.03, ge=0.01, le=0.15, description="Expected proportion of outliers")
    project_id: Optional[int] = Field(None, description="Associated Project ID")


class AuditAnalyticsRunResponse(BaseModel):
    """Response DTO for an audit analytics database run."""
    id: int
    project_id: Optional[int]
    user_id: Optional[int]
    entity_name: Optional[str]
    reporting_period: Optional[str]
    input_filename: str
    risk_score: float
    risk_classification: str
    benford_mad: float
    benford_conformity: str
    flagged_entries_count: int
    created_at: datetime
    report: Dict[str, Any]

    class Config:
        from_attributes = True


class GLAuditResponse(BaseModel):
    """Direct API response from General Ledger analysis endpoint."""
    run_id: int
    status: str = "SUCCESS"
    entity_name: str
    reporting_period: str
    risk_score: float
    risk_classification: str
    report: AuditRiskReport
    summary_message: str
