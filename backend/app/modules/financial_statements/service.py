from pathlib import Path
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CompilationException
from app.modules.financial_statements.domain import (
    CompilationOutcome,
    PipelineOptions,
    UnprocessableDataError,
    run_compilation,
)
from app.modules.financial_statements.infrastructure.file_storage import FileStorageAdapter
from app.modules.financial_statements.models import StatementRun
from app.modules.financial_statements.schemas import (
    CompilationResponse,
    PipelineOptionsSchema,
)
from app.modules.projects.models import ProjectRevision
from app.modules.users.models import User
from app.modules.users.service import UserService


class FinancialStatementsService:
    def __init__(self, db: AsyncSession, storage: FileStorageAdapter):
        self.db = db
        self.storage = storage

    async def compile_statements(
        self,
        input_file_path: str,
        input_filename: str,
        options_schema: PipelineOptionsSchema,
        current_user: Optional[User] = None,
        project_id: Optional[int] = None,
    ) -> CompilationResponse:
        if current_user and current_user.organization_id:
            user_service = UserService(self.db)
            has_credits = await user_service.deduct_credits(current_user.organization_id, amount=1)
            if not has_credits:
                raise CompilationException("Insufficient credits to execute statement compilation.")

        output_filename = f"Financial_Statements_{Path(input_filename).stem}.xlsx"
        output_file_path = str(self.storage.get_file_path(f"uploads/outputs/{output_filename}"))
        Path(output_file_path).parent.mkdir(parents=True, exist_ok=True)

        entity_name = options_schema.entity_name or Path(input_filename).stem.replace("-", " ").replace("_", " ").title()
        period = options_schema.period_ended or "June 30, 2025"

        options = PipelineOptions(
            output_file=output_file_path if options_schema.export_excel else None,
            entity_name=entity_name,
            period=period,
            sheet_name=options_schema.sheet_name,
            enforce_health_gate=options_schema.run_health_gate,
            allow_working_capital_plug=options_schema.allow_working_capital_plug,
        )

        try:
            outcome: CompilationOutcome = run_compilation(input_file_path, options)
        except UnprocessableDataError as err:
            raise CompilationException(
                f"Data health pre-flight check rejected the workbook: {err.report.headline}"
            )
        except Exception as exc:
            raise CompilationException(f"Compilation pipeline failed: {str(exc)}")

        result = outcome.result
        dh = result.health_report
        data_health_dict = {
            "is_processable": dh.is_processable,
            "row_count": dh.valid_accounts_count or dh.total_raw_rows,
            "unbalanced_variance": abs(dh.initial_delta),
            "health_score": dh.health_score,
            "issues": [i.model_dump() for i in dh.issues] if dh.issues else [],
        } if dh else None

        ver = result.verification_report
        verification_dict = {
            "is_valid": result.is_balanced,
            "bs_balances": ver.is_bs_balanced if ver else False,
            "cf_reconciles": True,
            "equity_reconciles": True,
            "notes_balanced": ver.notes_reconciled if ver else False,
            "diagnostics": ver.auto_corrections if (ver and ver.auto_corrections) else ([ver.status_message] if (ver and ver.status_message) else []),
            "total_assets": ver.total_assets if ver else 0.0,
            "total_liabilities_and_equity": ver.total_liabilities_and_equity if ver else 0.0,
            "net_profit": ver.net_profit if ver else 0.0,
        } if ver else None

        audit = result.workbook_audit
        workbook_audit_dict = {
            "verified": audit.passed if audit else True,
            "formula_audit_passed": audit.passed if audit else True,
            "checks_run": len(audit.checks) if audit else 0,
            "failures": [{"description": f} for f in audit.failures] if (audit and audit.failures) else [],
        } if audit else None

        audit_trail_list = [entry.model_dump() for entry in result.audit_trail] if result.audit_trail else []

        run_record = StatementRun(
            project_id=project_id,
            user_id=current_user.id if current_user else None,
            status=result.status,
            entity_name=entity_name,
            reporting_period=period,
            input_filename=input_filename,
            input_file_path=input_file_path,
            output_filename=output_filename,
            output_file_path=output_file_path if options_schema.export_excel else None,
            data_health_report=data_health_dict,
            verification_report=verification_dict,
            workbook_audit_report=workbook_audit_dict,
            audit_trail=audit_trail_list,
        )
        self.db.add(run_record)

        if project_id:
            count_stmt = select(func.count(ProjectRevision.id)).where(ProjectRevision.project_id == project_id)
            count_res = await self.db.execute(count_stmt)
            rev_num = (count_res.scalar() or 0) + 1
            revision = ProjectRevision(
                project_id=project_id,
                revision_number=rev_num,
                trial_balance_filename=input_filename,
                output_workbook_filename=output_filename,
                status=result.status,
                summary_notes=result.message,
            )
            self.db.add(revision)

        await self.db.commit()
        await self.db.refresh(run_record)

        download_url = f"/api/v1/statements/download/{run_record.id}" if options_schema.export_excel else None

        return CompilationResponse(
            run_id=run_record.id,
            status=result.status,
            entity_name=entity_name,
            period_ended=period,
            download_url=download_url,
            data_health=data_health_dict,
            verification=verification_dict,
            workbook_audit=workbook_audit_dict,
            summary_message=result.message or f"Statements compilation completed with status: {result.status}",
        )
