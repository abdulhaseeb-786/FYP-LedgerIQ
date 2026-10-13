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
    gl_file: Optional[UploadFile] = File(None, description="Optional General Ledger (.xlsx or .csv) for ISA 520 analytics"),
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
    saved_gl_path = None
    if gl_file is not None and gl_file.filename:
        saved_gl_path = await storage.save_upload(gl_file, directory="inputs")

    options_schema = PipelineOptionsSchema(
        entity_name=entity_name,
        period_ended=period_ended,
        sheet_name=sheet_name,
        run_health_gate=run_health_gate,
        allow_working_capital_plug=allow_working_capital_plug,
        export_excel=True,
        gl_file_path=saved_gl_path,
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


from app.modules.projects.models import Project


async def _verify_statement_run_access(
    run_record: StatementRun, current_user: Optional[User], db: AsyncSession
) -> None:
    if run_record.user_id is not None or run_record.project_id is not None:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access this statement run.",
            )
        if run_record.user_id and run_record.user_id != current_user.id:
            if run_record.project_id:
                stmt_p = select(Project).where(Project.id == run_record.project_id)
                res_p = await db.execute(stmt_p)
                proj = res_p.scalars().first()
                if not proj or proj.organization_id != current_user.organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have permission to access this statement run.",
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to access this statement run.",
                )


@router.get("/runs/{run_id}", response_model=ApiResponse[StatementRunResponse])
async def get_statement_run(
    run_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(StatementRun).where(StatementRun.id == run_id)
    result = await db.execute(stmt)
    run_record = result.scalars().first()
    if not run_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    await _verify_statement_run_access(run_record, current_user, db)
    return ApiResponse.ok(data=StatementRunResponse.model_validate(run_record))


@router.get("/download/{run_id}")
async def download_statement_workbook(
    run_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(StatementRun).where(StatementRun.id == run_id)
    result = await db.execute(stmt)
    run_record = result.scalars().first()
    if not run_record or not run_record.output_file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output file not found")
    await _verify_statement_run_access(run_record, current_user, db)

    file_path = Path(run_record.output_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File is no longer on disk")

    return FileResponse(
        path=file_path,
        filename=run_record.output_filename or file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
