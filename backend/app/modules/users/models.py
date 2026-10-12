from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    max_projects_quota: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan", lazy="selectin")
    credit_balance = relationship("CreditBalance", back_populates="organization", uselist=False, cascade="all, delete-orphan", lazy="selectin")


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    organization = relationship("Organization", back_populates="users", lazy="selectin")


class CreditBalance(Base):
    __tablename__ = "credit_balances"

    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    balance: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    lifetime_purchased: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    lifetime_consumed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    organization = relationship("Organization", back_populates="credit_balance")
