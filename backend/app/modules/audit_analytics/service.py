"""Business Service Layer for General Ledger Audit Analytics."""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.modules.financial_statements.infrastructure.file_storage import FileStorageAdapter
from app.modules.users.models import User
from app.modules.users.service import UserService
from app.modules.projects.models import Project
from app.modules.audit_analytics.domain.models import AuditRiskReport
from app.modules.audit_analytics.domain.pipeline import AuditAnalyticsPipeline
from app.modules.audit_analytics.infrastructure.gl_parser import GeneralLedgerParser, GLParserException
from app.modules.audit_analytics.models import AuditAnalyticsRun
from app.modules.audit_analytics.schemas import (
    GLAuditOptionsSchema,
    GLAuditResponse,
    AuditAnalyticsRunResponse,
)


class AuditAnalyticsException(AppException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=400)


class AuditAnalyticsService:
    def __init__(self, db: AsyncSession, storage: Optional[FileStorageAdapter] = None):
        self.db = db
        self.storage = storage
        self.parser = GeneralLedgerParser()
        self.pipeline = AuditAnalyticsPipeline()

    async def execute_gl_audit(
        self,
        input_file_path: str,
        input_filename: str,
        options: GLAuditOptionsSchema,
        current_user: Optional[User] = None,
        current_tb_balances: Optional[Dict[str, float]] = None,
        prior_tb_balances: Optional[Dict[str, float]] = None,
    ) -> GLAuditResponse:
        # Credit check
        if current_user and current_user.organization_id:
            user_service = UserService(self.db)
            has_credits = await user_service.deduct_credits(current_user.organization_id, amount=1)
            if not has_credits:
                raise AuditAnalyticsException("Insufficient credits to execute audit analytics.")

        # Ingestion (CPU-bound: run in worker thread)
        try:
            transactions = await asyncio.to_thread(self.parser.parse_file, input_file_path)
        except GLParserException as err:
            raise AuditAnalyticsException(f"Failed to parse General Ledger: {str(err)}")
        except Exception as exc:
            raise AuditAnalyticsException(f"Error reading General Ledger file: {str(exc)}")

        entity_name = options.entity_name or Path(input_filename).stem.replace("-", " ").replace("_", " ").title()
        period = options.reporting_period or "FY2024-25"

        # Execution (CPU-bound: Isolation Forest + Benford in worker thread)
        pipeline = AuditAnalyticsPipeline(ml_contamination=options.contamination_rate)
        report: AuditRiskReport = await asyncio.to_thread(
            pipeline.execute_audit,
            transactions=transactions,
            entity_name=entity_name,
            reporting_period=period,
            current_tb_balances=current_tb_balances,
            prior_tb_balances=prior_tb_balances,
        )

        # Persistence
        run_record = AuditAnalyticsRun(
            project_id=options.project_id,
            user_id=current_user.id if current_user else None,
            entity_name=entity_name,
            reporting_period=period,
            input_filename=input_filename,
            input_file_path=input_file_path,
            risk_score=report.overall_risk_score,
            risk_classification=report.risk_classification,
            benford_mad=report.benford_analysis.mad,
            benford_conformity=report.benford_analysis.conformity_status,
            flagged_entries_count=report.ml_anomalies.total_flagged,
            report_payload=report.model_dump(mode="json"),
        )
        self.db.add(run_record)
        await self.db.commit()
        await self.db.refresh(run_record)

        summary_msg = (
            f"Audit analytics completed. Evaluated {len(transactions)} transactions. "
            f"Overall risk classification: {report.risk_classification} (Risk Score: {report.overall_risk_score}/100)."
        )

        return GLAuditResponse(
            run_id=run_record.id,
            status="SUCCESS",
            entity_name=entity_name,
            reporting_period=period,
            risk_score=report.overall_risk_score,
            risk_classification=report.risk_classification,
            report=report,
            summary_message=summary_msg,
        )

    async def get_run_by_id(
        self, run_id: int, current_user: Optional[User] = None
    ) -> AuditAnalyticsRunResponse:
        stmt = select(AuditAnalyticsRun).where(AuditAnalyticsRun.id == run_id)
        result = await self.db.execute(stmt)
        record = result.scalars().first()
        if not record:
            raise AuditAnalyticsException(f"Audit run #{run_id} not found.")

        # IDOR Protection: Enforce tenant and owner isolation
        if record.user_id is not None or record.project_id is not None:
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required to access this audit run.",
                )
            if record.user_id and record.user_id != current_user.id:
                if record.project_id:
                    stmt_proj = select(Project).where(Project.id == record.project_id)
                    proj_res = await self.db.execute(stmt_proj)
                    proj = proj_res.scalars().first()
                    if not proj or proj.organization_id != current_user.organization_id:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have permission to access this audit run.",
                        )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have permission to access this audit run.",
                    )

        return AuditAnalyticsRunResponse(
            id=record.id,
            project_id=record.project_id,
            user_id=record.user_id,
            entity_name=record.entity_name,
            reporting_period=record.reporting_period,
            input_filename=record.input_filename,
            risk_score=record.risk_score,
            risk_classification=record.risk_classification,
            benford_mad=record.benford_mad,
            benford_conformity=record.benford_conformity,
            flagged_entries_count=record.flagged_entries_count,
            created_at=record.created_at,
            report=record.report_payload,
        )
