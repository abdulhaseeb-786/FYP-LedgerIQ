from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    entity_name: Optional[str] = Field(None, max_length=255)
    reporting_period: Optional[str] = Field(None, max_length=100)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    entity_name: Optional[str] = None
    reporting_period: Optional[str] = None
    is_archived: Optional[bool] = None


class ProjectRevisionResponse(BaseModel):
    id: int
    revision_number: int
    trial_balance_filename: str
    output_workbook_filename: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectResponse(ProjectBase):
    id: int
    organization_id: int
    is_archived: bool
    created_at: datetime
    last_accessed_at: datetime
    revisions: List[ProjectRevisionResponse] = []

    class Config:
        from_attributes = True


class ProjectQuotaStatus(BaseModel):
    active_projects_count: int
    max_projects_quota: int
    can_create_project: bool
