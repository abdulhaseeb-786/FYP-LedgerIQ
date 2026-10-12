from fastapi import APIRouter
from app.common.responses import ApiResponse
from app.core.config import settings
from app.modules.users.router import router as auth_router
from app.modules.projects.router import router as projects_router
from app.modules.financial_statements.router import router as statements_router

api_router = APIRouter(prefix=settings.API_V1_PREFIX)


@api_router.get("/health", tags=["System Health"])
async def health_check():
    return ApiResponse.ok(
        data={
            "status": "healthy",
            "app_name": settings.APP_NAME,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
        },
        message="System is operating normally",
    )


api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(statements_router)
