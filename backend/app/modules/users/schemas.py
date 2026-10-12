from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None
    org_id: Optional[int] = None


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(min_length=6, description="Minimum 6 characters")
    organization_name: Optional[str] = Field(None, description="Optional organization name")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class OrganizationResponse(BaseModel):
    id: int
    name: str
    slug: str
    max_projects_quota: int
    is_active: bool

    class Config:
        from_attributes = True


class CreditBalanceResponse(BaseModel):
    balance: int
    lifetime_purchased: int
    lifetime_consumed: int

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    id: int
    is_active: bool
    organization_id: Optional[int] = None
    organization: Optional[OrganizationResponse] = None
    credit_balance: Optional[int] = None

    class Config:
        from_attributes = True
