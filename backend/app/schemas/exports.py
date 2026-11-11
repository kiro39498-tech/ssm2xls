from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreateExportJobRequest(BaseModel):
    """Payload to create an asynchronous Excel export job."""
    report_title: str = Field(default="SQL Report Export", max_length=200, description="Title for the export report")
    sql: str = Field(..., description="SQL query to execute and export")
    database: Optional[str] = Field(None, description="Target database name")
    parameters: Optional[List[Any]] = Field(default=None, description="Optional positional parameters")
    include_sql: bool = Field(default=False, description="Developer flag: include SQL on Report Information sheet")
    query_id: Optional[str] = Field(default=None, description="Optional link to saved query ID")
    query_version_id: Optional[str] = Field(default=None, description="Optional link to query version ID")


class ExportJobResponse(BaseModel):
    """Status and details for an export job (physical paths are never exposed)."""
    id: str
    report_title: str
    database_name: str
    status: str = Field(description="Job status: Pending, Running, Completed, Failed, Cancelled")
    progress_pct: int = 0
    rows_exported: int = 0
    file_size_bytes: int = 0
    error_message: Optional[str] = None
    execution_duration_ms: int = 0
    requested_by: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    expires_at: str
    download_available: bool = False


class ExportJobListResponse(BaseModel):
    """List of export jobs."""
    jobs: List[ExportJobResponse]
    total: int


class CancelJobResponse(BaseModel):
    """Response when requesting job cancellation."""
    job_id: str
    cancelled: bool
    status: str
    message: str

