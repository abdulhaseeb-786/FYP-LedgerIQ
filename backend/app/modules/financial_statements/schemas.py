from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PipelineOptionsSchema(BaseModel):
    entity_name: Optional[str] = Field(None, description="Legal entity name for statement headers")
    period_ended: Optional[str] = Field(None, description="Reporting period end date (e.g. 'June 30, 2025')")
    sheet_name: Optional[str] = Field(None, description="Specific Excel sheet to parse")
    run_health_gate: bool = Field(True, description="Enforce pre-flight data sanity checks")
    allow_working_capital_plug: bool = Field(False, description="Permit unsupported balancing plug")
    export_excel: bool = Field(True, description="Generate recalculating OpenXML workbook")
    gl_file_path: Optional[str] = Field(None, description="Optional General Ledger path for ISA 520 analytics")


class DataHealthResponse(BaseModel):
    is_processable: bool
    row_count: int
    unbalanced_variance: float
    issues: List[Dict[str, Any]] = []


class VerificationResponse(BaseModel):
    is_valid: bool
    bs_balances: bool
    cf_reconciles: bool
    equity_reconciles: bool
    notes_balanced: bool
    diagnostics: List[str] = []


class WorkbookAuditResponse(BaseModel):
    verified: bool
    formula_audit_passed: bool
    checks_run: int
    failures: List[Dict[str, Any]] = []


class CompilationResponse(BaseModel):
    run_id: Optional[int] = None
    status: str
    entity_name: Optional[str] = None
    period_ended: Optional[str] = None
    download_url: Optional[str] = None
    data_health: Optional[Dict[str, Any]] = None
    verification: Optional[Dict[str, Any]] = None
    workbook_audit: Optional[Dict[str, Any]] = None
    audit_analytics: Optional[Dict[str, Any]] = None
    summary_message: str


class StatementRunResponse(BaseModel):
    id: int
    project_id: Optional[int]
    status: str
    entity_name: Optional[str]
    reporting_period: Optional[str]
    input_filename: str
    output_filename: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
