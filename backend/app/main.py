from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.api_router import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.exceptions import register_exception_handlers
from app.core.logging import logger, setup_logging
from app.core.middleware import register_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} in [{settings.ENVIRONMENT}] mode...")

    if settings.ENVIRONMENT in ("development", "testing"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schemas verified.")

    yield

    logger.info(f"Shutting down {settings.APP_NAME}...")
    await engine.dispose()


def create_application() -> FastAPI:
    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        description="Scalable Statutory Financial Statement Compiler & Accounting Engine",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    register_middleware(app)
    register_exception_handlers(app)
    app.include_router(api_router)

    test_client_dir = Path(__file__).resolve().parents[2] / "frontend" / "test-client"
    if test_client_dir.exists():
        app.mount("/test-assets", StaticFiles(directory=str(test_client_dir)), name="test-assets")

        @app.get("/test", include_in_schema=False)
        async def serve_test_ui():
            index_path = test_client_dir / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return RedirectResponse(url="/docs")

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/test" if test_client_dir.exists() else "/docs")

    return app


app = create_application()
