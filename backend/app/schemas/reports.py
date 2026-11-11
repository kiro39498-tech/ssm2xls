from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreateReportRequest(BaseModel):
    """Payload to create a new report query and initial Draft v1."""
    title: str = Field(..., min_length=1, max_length=200, description="Report display title")
    description: Optional[str] = Field(None, description="Detailed report description")
    database: Optional[str] = Field(None, description="Target database (defaults to configured DB)")
    category: Optional[str] = Field(default="General", description="Category / Department grouping")
    initial_sql: str = Field(..., description="Initial draft SQL text")


class UpdateDraftVersionRequest(BaseModel):
    """Payload to modify a draft query version."""
    sql: str = Field(..., description="Updated SQL text")
    change_summary: Optional[str] = Field(None, description="Notes on what was modified")
    parameters_schema_json: Optional[str] = Field(None, description="Optional parameter definitions")


class NewDraftVersionRequest(BaseModel):
    """Payload to clone an existing version into a new Draft."""
    from_version_id: Optional[str] = Field(None, description="Source version ID to clone (defaults to latest active/approved)")
    change_summary: Optional[str] = Field(None, description="Reason for new version")


class QueryVersionResponse(BaseModel):
    """Full detail of an immutable query version record."""
    id: str
    query_id: str
    version_number: int
    sql_text: str
    parameters_schema_json: Optional[str] = None
    status: str = Field(description="Draft, Tested, Approved, Active, Archived")
    change_summary: Optional[str] = None
    created_by: str
    tested_by: Optional[str] = None
    tested_at: Optional[str] = None
    test_results_summary: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    activated_by: Optional[str] = None
    activated_at: Optional[str] = None
    created_at: str


class ReportResponse(BaseModel):
    """Report query entity with current active or latest draft version."""
    id: str
    title: str
    description: Optional[str] = None
    database_name: str
    category: str
    is_active: bool
    current_version_id: Optional[str] = None
    current_version: Optional[QueryVersionResponse] = None
    created_by: str
    created_at: str
    updated_at: str


class ReportListResponse(BaseModel):
    """Paginated list of reports."""
    reports: List[ReportResponse]
    total: int


class AuditLogResponse(BaseModel):
    """Execution audit trail entry."""
    id: int
    query_id: Optional[str] = None
    query_version_id: Optional[str] = None
    executed_by: str
    execution_type: str
    database_name: str
    duration_ms: int
    rows_returned: int
    status: str
    error_message: Optional[str] = None
    parameters_json: Optional[str] = None
    executed_at: str

