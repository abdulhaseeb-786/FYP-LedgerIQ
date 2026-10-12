from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ApiResponse
from app.core.database import get_db
from app.modules.financial_statements.infrastructure.file_storage import FileStorageAdapter, get_file_storage
from app.modules.financial_statements.models import StatementRun
from app.modules.financial_statements.schemas import (
    CompilationResponse,
    PipelineOptionsSchema,
    StatementRunResponse,
)
from app.modules.financial_statements.service import FinancialStatementsService
from app.modules.users.models import User
from app.modules.users.service import get_current_user_optional

router = APIRouter(prefix="/statements", tags=["Financial Statements"])


@router.post("/compile", response_model=ApiResponse[CompilationResponse], status_code=status.HTTP_200_OK)
async def compile_trial_balance(
    file: UploadFile = File(..., description="Trial Balance Excel workbook (.xlsx)"),
    entity_name: Optional[str] = Form(None),
    period_ended: Optional[str] = Form(None),
    sheet_name: Optional[str] = Form(None),
    run_health_gate: bool = Form(True),
    allow_working_capital_plug: bool = Form(False),
    project_id: Optional[int] = Form(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    storage: FileStorageAdapter = Depends(get_file_storage),
):
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be an Excel workbook (.xlsx or .xlsm)",
        )

    saved_input_path = await storage.save_upload(file, directory="inputs")

    options_schema = PipelineOptionsSchema(
        entity_name=entity_name,
        period_ended=period_ended,
        sheet_name=sheet_name,
        run_health_gate=run_health_gate,
        allow_working_capital_plug=allow_working_capital_plug,
        export_excel=True,
    )

    service = FinancialStatementsService(db, storage)
    response = await service.compile_statements(
        input_file_path=saved_input_path,
        input_filename=file.filename,
        options_schema=options_schema,
        current_user=current_user,
        project_id=project_id,
    )

    return ApiResponse.ok(data=response, message="Statements successfully generated and audited")


@router.get("/runs/{run_id}", response_model=ApiResponse[StatementRunResponse])
async def get_statement_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(StatementRun).where(StatementRun.id == run_id)
    result = await db.execute(stmt)
    run_record = result.scalars().first()
    if not run_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return ApiResponse.ok(data=StatementRunResponse.model_validate(run_record))


@router.get("/download/{run_id}")
async def download_statement_workbook(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(StatementRun).where(StatementRun.id == run_id)
    result = await db.execute(stmt)
    run_record = result.scalars().first()
    if not run_record or not run_record.output_file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output file not found")

    file_path = Path(run_record.output_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File is no longer on disk")

    return FileResponse(
        path=file_path,
        filename=run_record.output_filename or file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
