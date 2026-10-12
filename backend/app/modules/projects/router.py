from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ApiResponse
from app.core.database import get_db
from app.modules.projects.schemas import ProjectCreate, ProjectQuotaStatus, ProjectResponse, ProjectUpdate
from app.modules.projects.service import ProjectService
from app.modules.users.models import User
from app.modules.users.service import get_current_user

router = APIRouter(prefix="/projects", tags=["Projects & Workspaces"])


@router.get("/quota", response_model=ApiResponse[ProjectQuotaStatus])
async def get_project_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    status_info = await service.get_quota_status(current_user.organization_id)
    return ApiResponse.ok(data=status_info)


@router.post("", response_model=ApiResponse[ProjectResponse], status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.create_project(
        project_in=project_in,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )
    return ApiResponse.ok(data=ProjectResponse.model_validate(project), message="Project created successfully")


@router.get("", response_model=ApiResponse[List[ProjectResponse]])
async def list_projects(
    include_archived: bool = Query(True, description="Include archived projects"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    projects = await service.list_projects(
        organization_id=current_user.organization_id,
        include_archived=include_archived,
    )
    return ApiResponse.ok(data=[ProjectResponse.model_validate(p) for p in projects])


@router.get("/{project_id}", response_model=ApiResponse[ProjectResponse])
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.get_project(project_id, current_user.organization_id)
    return ApiResponse.ok(data=ProjectResponse.model_validate(project))


@router.patch("/{project_id}", response_model=ApiResponse[ProjectResponse])
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.update_project(project_id, current_user.organization_id, project_update)
    return ApiResponse.ok(data=ProjectResponse.model_validate(project), message="Project updated")
