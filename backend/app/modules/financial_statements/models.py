from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StatementRun(Base):
    __tablename__ = "statement_runs"

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=True)
    reporting_period: Mapped[str] = mapped_column(String(100), nullable=True)

    input_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    input_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    output_filename: Mapped[str] = mapped_column(String(255), nullable=True)
    output_file_path: Mapped[str] = mapped_column(String(500), nullable=True)

    data_health_report: Mapped[dict] = mapped_column(JSON, nullable=True)
    verification_report: Mapped[dict] = mapped_column(JSON, nullable=True)
    workbook_audit_report: Mapped[dict] = mapped_column(JSON, nullable=True)
    audit_trail: Mapped[list] = mapped_column(JSON, nullable=True)
