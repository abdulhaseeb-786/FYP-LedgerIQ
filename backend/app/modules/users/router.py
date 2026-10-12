from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ApiResponse
from app.core.database import get_db
from app.core.security import create_access_token
from app.modules.users.models import User
from app.modules.users.schemas import Token, UserCreate, UserLogin, UserResponse
from app.modules.users.service import UserService, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication & Users"])


@router.post("/register", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    user = await service.create_user(user_in)
    credits = user.organization.credit_balance.balance if user.organization and user.organization.credit_balance else 100
    user_resp = UserResponse.model_validate(user)
    user_resp.credit_balance = credits
    return ApiResponse.ok(data=user_resp, message="User registered successfully with trial credits")


@router.post("/login", response_model=ApiResponse[Token])
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    user = await service.authenticate(credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token(
        subject=user.email,
        extra_claims={"org_id": user.organization_id},
    )
    return ApiResponse.ok(data=Token(access_token=token), message="Login successful")


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    user = await service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        subject=user.email,
        extra_claims={"org_id": user.organization_id},
    )
    return Token(access_token=access_token)


@router.get("/me", response_model=ApiResponse[UserResponse])
async def read_users_me(current_user: User = Depends(get_current_user)):
    credits = current_user.organization.credit_balance.balance if current_user.organization and current_user.organization.credit_balance else 0
    resp = UserResponse.model_validate(current_user)
    resp.credit_balance = credits
    return ApiResponse.ok(data=resp)
