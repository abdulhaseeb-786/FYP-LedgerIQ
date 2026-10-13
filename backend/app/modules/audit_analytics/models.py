"""SQLAlchemy ORM model for storing Audit Analytics and Anomaly Detection runs."""

from sqlalchemy import ForeignKey, Integer, Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditAnalyticsRun(Base):
    __tablename__ = "audit_analytics_runs"

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    entity_name: Mapped[str] = mapped_column(String(255), nullable=True)
    reporting_period: Mapped[str] = mapped_column(String(100), nullable=True)

    input_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    input_file_path: Mapped[str] = mapped_column(String(500), nullable=False)

    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_classification: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    benford_mad: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    benford_conformity: Mapped[str] = mapped_column(String(100), nullable=False)
    flagged_entries_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    report_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

