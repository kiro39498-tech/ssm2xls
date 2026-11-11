from datetime import datetime, timezone
from fastapi import APIRouter, status
from app.core.config import get_settings
from app.db.sqlite import check_sqlite_health
from app.db.mssql import check_mssql_health
from app.schemas.health import (
    LivenessResponse,
    ReadinessResponse,
    DatabaseHealthResponse,
)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=LivenessResponse, status_code=status.HTTP_200_OK)
def get_liveness() -> LivenessResponse:
    """
    Liveness check: Indicates that the FastAPI application is alive and responding.
    Does not depend on external services.
    """
    settings = get_settings()
    return LivenessResponse(
        status="healthy",
        app_name=settings.app_name,
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/ready", response_model=ReadinessResponse, status_code=status.HTTP_200_OK)
def get_readiness() -> ReadinessResponse:
    """
    Readiness check: Evaluates application subsystems (SQLite metadata and SQL Server target).
    Status is 'ready' when both are available, or 'degraded' if SQL Server target is unreachable.
    """
    settings = get_settings()
    sqlite_status = check_sqlite_health()
    mssql_status = check_mssql_health()

    overall_status = (
        "ready"
        if sqlite_status.get("connected") and mssql_status.get("connected")
        else "degraded"
    )

    return ReadinessResponse(
        status=overall_status,
        app=LivenessResponse(
            status="healthy",
            app_name=settings.app_name,
            environment=settings.app_env,
            timestamp=datetime.now(timezone.utc),
        ),
        databases=DatabaseHealthResponse(
            timestamp=datetime.now(timezone.utc),
            sqlite=sqlite_status,
            sql_server=mssql_status,
        ),
    )


@router.get("/db", response_model=DatabaseHealthResponse, status_code=status.HTTP_200_OK)
def get_database_health() -> DatabaseHealthResponse:
    """
    Database health check: Provides detailed connectivity diagnostics for both
    the local SQLite metadata database and the target Microsoft SQL Server instance.
    """
    sqlite_status = check_sqlite_health()
    mssql_status = check_mssql_health()

    return DatabaseHealthResponse(
        timestamp=datetime.now(timezone.utc),
        sqlite=sqlite_status,
        sql_server=mssql_status,
    )

