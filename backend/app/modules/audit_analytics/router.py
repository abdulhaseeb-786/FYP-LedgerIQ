"""FastAPI API Router for Audit Analytics and Anomaly Detection."""

from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ApiResponse
from app.core.database import get_db
from app.modules.financial_statements.infrastructure.file_storage import FileStorageAdapter, get_file_storage
from app.modules.users.models import User
from app.modules.users.service import get_current_user_optional
from app.modules.audit_analytics.schemas import (
    GLAuditOptionsSchema,
    GLAuditResponse,
    AuditAnalyticsRunResponse,
)
from app.modules.audit_analytics.service import AuditAnalyticsService

router = APIRouter(prefix="/analytics", tags=["Audit Analytics & Anomaly Detection"])


@router.post("/gl-audit", response_model=ApiResponse[GLAuditResponse], status_code=status.HTTP_200_OK)
async def execute_general_ledger_audit(
    file: UploadFile = File(..., description="General Ledger spreadsheet (.xlsx or .csv)"),
    entity_name: Optional[str] = Form(None),
    reporting_period: Optional[str] = Form(None),
    contamination_rate: float = Form(0.03),
    project_id: Optional[int] = Form(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    storage: FileStorageAdapter = Depends(get_file_storage),
):
    """
    Execute ISA 520 / ISA 240 Audit Analytics & Anomaly Detection on an uploaded General Ledger.
    Runs Benford's Law distribution analysis, Isolation Forest ML anomaly detection, and ratio checks.
    """
    if not file.filename.endswith((".xlsx", ".xlsm", ".csv")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a spreadsheet or CSV (.xlsx, .xlsm, .csv)",
        )

    saved_input_path = await storage.save_upload(file, directory="inputs")

    options = GLAuditOptionsSchema(
        entity_name=entity_name,
        reporting_period=reporting_period,
        contamination_rate=contamination_rate,
        project_id=project_id,
    )

    service = AuditAnalyticsService(db, storage)
    response = await service.execute_gl_audit(
        input_file_path=saved_input_path,
        input_filename=file.filename,
        options=options,
        current_user=current_user,
    )

    return ApiResponse.ok(data=response, message="Audit procedures completed successfully.")


@router.get("/runs/{run_id}", response_model=ApiResponse[AuditAnalyticsRunResponse])
async def get_audit_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve report and metrics of a previous General Ledger audit run."""
    service = AuditAnalyticsService(db)
    result = await service.get_run_by_id(run_id)
    return ApiResponse.ok(data=result)
