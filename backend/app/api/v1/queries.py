from fastapi import APIRouter, HTTPException, status
from app.schemas.queries import (
    QueryValidationRequest,
    QueryValidationResponse,
    QueryExecutionRequest,
    QueryExecutionResponse,
    QueryCancelResponse,
)
from app.services.sql.validator import get_sql_validator
from app.services.sql.executor import get_sql_executor

router = APIRouter(prefix="/queries", tags=["Queries"])


@router.post("/validate", response_model=QueryValidationResponse, status_code=status.HTTP_200_OK)
def validate_query(payload: QueryValidationRequest) -> QueryValidationResponse:
    """
    Validate SQL query using SQLGlot AST inspection (T-SQL dialect).
    Enforces read-only SELECT rules, single-statement restrictions,
    and checks for prohibited functions and operations.
    """
    validator = get_sql_validator()
    result = validator.validate(payload.sql, allowed_database=payload.database)

    return QueryValidationResponse(
        is_valid=result.is_valid,
        errors=result.errors,
        statement_type=result.statement_type,
        tables_referenced=result.tables_referenced,
        normalized_sql=result.normalized_sql,
    )


@router.post("/execute", response_model=QueryExecutionResponse, status_code=status.HTTP_200_OK)
def execute_query(payload: QueryExecutionRequest) -> QueryExecutionResponse:
    """
    Execute a validated preview query against SQL Server.
    Enforces a strict upper bound of 1,000 rows and query timeout.
    """
    executor = get_sql_executor()
    max_rows = min(payload.max_rows or 1000, 1000)

    result = executor.execute_query(
        sql=payload.sql,
        database=payload.database,
        parameters=payload.parameters,
        max_rows=max_rows,
        timeout_seconds=payload.timeout_seconds,
    )

    return result


@router.post("/cancel/{execution_id}", response_model=QueryCancelResponse, status_code=status.HTTP_200_OK)
def cancel_query(execution_id: str) -> QueryCancelResponse:
    """
    Cancel an active query execution in progress.
    """
    executor = get_sql_executor()
    cancelled = executor.cancel_query(execution_id)

    if cancelled:
        return QueryCancelResponse(
            execution_id=execution_id,
            cancelled=True,
            message="Query cancellation signal delivered to ODBC driver.",
        )
    return QueryCancelResponse(
        execution_id=execution_id,
        cancelled=False,
        message="Execution ID not found or query already completed.",
    )

