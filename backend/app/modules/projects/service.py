from datetime import datetime, timezone
from typing import List
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import EntityNotFoundException, QuotaExceededException
from app.modules.projects.models import Project
from app.modules.projects.schemas import ProjectCreate, ProjectQuotaStatus, ProjectUpdate
from app.modules.users.models import Organization


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_count(self, organization_id: int) -> int:
        stmt = (
            select(func.count(Project.id))
            .where(Project.organization_id == organization_id)
            .where(Project.is_archived.is_(False))
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_quota_status(self, organization_id: int) -> ProjectQuotaStatus:
        org_stmt = select(Organization).where(Organization.id == organization_id)
        org_res = await self.db.execute(org_stmt)
        org = org_res.scalars().first()
        max_quota = org.max_projects_quota if org else 5

        active_count = await self.get_active_count(organization_id)
        return ProjectQuotaStatus(
            active_projects_count=active_count,
            max_projects_quota=max_quota,
            can_create_project=active_count < max_quota,
        )

    async def create_project(
        self,
        project_in: ProjectCreate,
        organization_id: int,
        user_id: int,
    ) -> Project:
        quota_status = await self.get_quota_status(organization_id)
        if not quota_status.can_create_project:
            raise QuotaExceededException(
                f"Organization limit of {quota_status.max_projects_quota} active projects reached. "
                f"Please archive an existing project to continue."
            )

        project = Project(
            name=project_in.name,
            description=project_in.description,
            entity_name=project_in.entity_name,
            reporting_period=project_in.reporting_period,
            organization_id=organization_id,
            user_id=user_id,
            is_archived=False,
            last_accessed_at=datetime.now(timezone.utc),
        )
        self.db.add(project)
        await self.db.commit()
        return await self.get_project(project.id, organization_id)

    async def list_projects(
        self,
        organization_id: int,
        include_archived: bool = True,
    ) -> List[Project]:
        stmt = (
            select(Project)
            .options(selectinload(Project.revisions))
            .where(Project.organization_id == organization_id)
        )
        if not include_archived:
            stmt = stmt.where(Project.is_archived.is_(False))
        stmt = stmt.order_by(Project.last_accessed_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_project(self, project_id: int, organization_id: int) -> Project:
        stmt = (
            select(Project)
            .options(selectinload(Project.revisions))
            .where(Project.id == project_id, Project.organization_id == organization_id)
        )
        result = await self.db.execute(stmt)
        project = result.scalars().first()
        if not project:
            raise EntityNotFoundException("Project", project_id)

        project.last_accessed_at = datetime.now(timezone.utc)
        await self.db.commit()
        return project

    async def update_project(
        self,
        project_id: int,
        organization_id: int,
        project_update: ProjectUpdate,
    ) -> Project:
        project = await self.get_project(project_id, organization_id)
        update_data = project_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)
        await self.db.commit()
        return await self.get_project(project.id, organization_id)
