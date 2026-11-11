from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    """Response model for application liveness check."""
    status: str = Field(default="healthy", description="Application status")
    app_name: str = Field(description="Name of the application")
    environment: str = Field(description="Active environment")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the check",
    )


class ComponentStatus(BaseModel):
    """Status details for an individual subsystem."""
    status: str
    connected: bool
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class DatabaseHealthResponse(BaseModel):
    """Detailed response for all database dependencies."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sqlite: Dict[str, Any]
    sql_server: Dict[str, Any]


class ReadinessResponse(BaseModel):
    """Response model for application readiness."""
    status: str = Field(description="Overall readiness: ready or degraded")
    app: LivenessResponse
    databases: DatabaseHealthResponse

