from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.db.sqlite import init_db
from app.db.mssql import check_mssql_health
from app.api.router import api_router

logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager: startup and teardown routines."""
    setup_logging()
    settings = get_settings()
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)

    # 1. Initialize SQLite metadata database (WAL mode and schema)
    try:
        init_db()
        from app.db.schema import init_schema
        init_schema()
        logger.info("SQLite metadata database initialized successfully")
    except Exception as exc:
        logger.critical("Failed to initialize SQLite metadata database: %s", exc)
        raise

    # 2. Probe SQL Server connectivity (non-blocking for app startup)
    mssql_status = check_mssql_health()
    if mssql_status.get("connected"):
        logger.info(
            "SQL Server connectivity established: %s (%s)",
            mssql_status.get("server_instance"),
            mssql_status.get("version"),
        )
    else:
        logger.warning(
            "SQL Server is currently unreachable: %s. Application will start in degraded mode.",
            mssql_status.get("error"),
        )

    yield

    logger.info("Shutting down %s", settings.app_name)


def create_application() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Internal SQL Query & Excel Export Portal",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS configuration for frontend development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routes
    app.include_router(api_router)

    return app


app = create_application()

