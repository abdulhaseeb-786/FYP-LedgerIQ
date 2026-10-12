import re
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_access_token, get_password_hash, verify_password
from app.modules.users.models import CreditBalance, Organization, User
from app.modules.users.schemas import TokenPayload, UserCreate

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = (
            select(User)
            .options(
                selectinload(User.organization).selectinload(Organization.credit_balance)
            )
            .where(User.email == email)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        stmt = (
            select(User)
            .options(
                selectinload(User.organization).selectinload(Organization.credit_balance)
            )
            .where(User.id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create_user(self, user_in: UserCreate) -> User:
        existing = await self.get_by_email(user_in.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )

        org_name = user_in.organization_name or f"{user_in.email.split('@')[0]}'s Workspace"
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", org_name.lower()).strip("-")
        slug = f"{slug}-{user_in.email.split('@')[0]}"

        org = Organization(
            name=org_name,
            slug=slug,
            max_projects_quota=5,
        )
        self.db.add(org)
        await self.db.flush()

        credits = CreditBalance(
            organization_id=org.id,
            balance=100,
            lifetime_purchased=100,
            lifetime_consumed=0,
        )
        self.db.add(credits)

        user = User(
            email=user_in.email,
            hashed_password=get_password_hash(user_in.password),
            full_name=user_in.full_name,
            organization_id=org.id,
            is_active=True,
        )
        self.db.add(user)
        await self.db.commit()
        return await self.get_by_email(user_in.email)

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        user = await self.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def deduct_credits(self, organization_id: int, amount: int = 1) -> bool:
        stmt = select(CreditBalance).where(CreditBalance.organization_id == organization_id)
        result = await self.db.execute(stmt)
        credit_record = result.scalars().first()
        if not credit_record or credit_record.balance < amount:
            return False
        credit_record.balance -= amount
        credit_record.lifetime_consumed += amount
        await self.db.commit()
        return True


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    token_data = TokenPayload(**payload)
    if not token_data.sub:
        return None
    user_service = UserService(db)
    return await user_service.get_by_email(token_data.sub)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = TokenPayload(**payload)
    if not token_data.sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identifier",
        )

    user_service = UserService(db)
    user = await user_service.get_by_email(token_data.sub)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account")
    return user
