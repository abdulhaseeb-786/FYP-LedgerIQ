from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=True)
    reporting_period: Mapped[str] = mapped_column(String(100), nullable=True)

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    revisions = relationship("ProjectRevision", back_populates="project", cascade="all, delete-orphan", lazy="selectin")


class ProjectRevision(Base):
    __tablename__ = "project_revisions"

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    trial_balance_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    output_workbook_filename: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    summary_notes: Mapped[str] = mapped_column(Text, nullable=True)

    project = relationship("Project", back_populates="revisions")
