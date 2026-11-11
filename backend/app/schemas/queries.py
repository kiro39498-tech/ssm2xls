from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryValidationRequest(BaseModel):
    """Request payload for validating SQL text."""
    sql: str = Field(..., description="Raw SQL query text to validate")
    database: Optional[str] = Field(None, description="Optional target database name to restrict cross-database queries")


class QueryValidationResponse(BaseModel):
    """Response containing validation status and diagnostics."""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    statement_type: Optional[str] = None
    tables_referenced: List[str] = Field(default_factory=list)
    normalized_sql: Optional[str] = None


class ColumnMetadata(BaseModel):
    """Metadata describing a result set column."""
    name: str
    type_name: str
    precision: Optional[int] = None
    scale: Optional[int] = None
    nullable: Optional[bool] = None


class QueryExecutionRequest(BaseModel):
    """Request payload for executing a query preview."""
    sql: str = Field(..., description="SQL query to execute")
    database: Optional[str] = Field(None, description="Target database name")
    parameters: Optional[List[Any]] = Field(default=None, description="Positional parameters for parameterized query")
    max_rows: Optional[int] = Field(default=1000, le=1000, description="Max rows to return (cap: 1000)")
    timeout_seconds: Optional[int] = Field(default=None, description="Execution timeout in seconds")


class QueryExecutionResponse(BaseModel):
    """Response payload for query preview results."""
    execution_id: str
    status: str = Field(description="Execution status: success, cancelled, failed")
    row_count: int
    duration_ms: int
    columns: List[ColumnMetadata] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None


class QueryCancelResponse(BaseModel):
    """Response payload for cancellation request."""
    execution_id: str
    cancelled: bool
    message: str

