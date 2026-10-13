"""SQLAlchemy ORM model for storing Document Digitization and Closed-Loop Verification runs."""

from sqlalchemy import ForeignKey, Integer, Float, Boolean, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DigitizationRunRecord(Base):
    __tablename__ = "digitization_run_records"

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    document_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    document_no: Mapped[str] = mapped_column(String(100), nullable=True)

    is_balanced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    calculated_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discrepancy_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recovery_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    execution_profile: Mapped[str] = mapped_column(String(50), nullable=False, default="CPU_HIGH_PRECISION_PARSER")
    result_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

