import decimal
import threading
import time
import uuid
from datetime import date, datetime, time as dt_time
from typing import Any, Dict, List, Optional, Tuple
import pyodbc
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.mssql import get_mssql_connection
from app.schemas.queries import ColumnMetadata, QueryExecutionResponse
from app.services.sql.validator import get_sql_validator, ValidationResult

logger = get_logger(__name__)


def serialize_sql_value(val: Any) -> Any:
    """Format and serialize raw SQL data types to JSON-safe values."""
    if val is None:
        return None
    if isinstance(val, (datetime, date, dt_time)):
        return val.isoformat()
    if isinstance(val, decimal.Decimal):
        return float(val)
    if isinstance(val, bytes):
        return val.hex()
    if isinstance(val, uuid.UUID):
        return str(val)
    return val


def get_type_name(pyodbc_type: Any) -> str:
    """Extract human-readable SQL / Python type name from cursor.description."""
    if hasattr(pyodbc_type, "__name__"):
        return pyodbc_type.__name__
    return str(pyodbc_type)


class SQLExecutor:
    """
    Executes validated SQL queries against Microsoft SQL Server with timeouts,
    cancellation support, memory limits, and metadata extraction.
    """

    def __init__(self):
        self._active_cursors: Dict[str, pyodbc.Cursor] = {}
        self._lock = threading.Lock()

    def register_cursor(self, execution_id: str, cursor: pyodbc.Cursor) -> None:
        with self._lock:
            self._active_cursors[execution_id] = cursor

    def unregister_cursor(self, execution_id: str) -> None:
        with self._lock:
            self._active_cursors.pop(execution_id, None)

    def cancel_query(self, execution_id: str) -> bool:
        """Cancel an in-flight query execution via ODBC SQLCancel."""
        with self._lock:
            cursor = self._active_cursors.get(execution_id)

        if cursor:
            try:
                logger.info("Cancelling query execution %s", execution_id)
                cursor.cancel()
                return True
            except Exception as exc:
                logger.warning("Error cancelling execution %s: %s", execution_id, exc)
                return False
        return False

    def execute_query(
        self,
        sql: str,
        database: Optional[str] = None,
        parameters: Optional[List[Any]] = None,
        max_rows: int = 1000,
        timeout_seconds: Optional[int] = None,
        execution_id: Optional[str] = None,
    ) -> QueryExecutionResponse:
        """
        Validate and execute a limited SELECT query against SQL Server.
        Enforces maximum row limit (up to max_rows) and execution timeouts.
        """
        settings = get_settings()
        exec_id = execution_id or str(uuid.uuid4())
        target_db = database or settings.sql_database
        timeout = timeout_seconds or settings.sql_query_timeout

        # 1. Structural AST Validation
        validator = get_sql_validator()
        validation: ValidationResult = validator.validate(sql, allowed_database=target_db)
        if not validation.is_valid:
            error_details = "; ".join(validation.errors)
            logger.warning("Query rejected by SQLValidator: %s", error_details)
            return QueryExecutionResponse(
                execution_id=exec_id,
                status="failed",
                row_count=0,
                duration_ms=0,
                error_message=f"SQL Validation Error: {error_details}",
            )

        start_time = time.perf_counter()
        conn = None
        cursor = None

        try:
            conn = get_mssql_connection(target_db)

            cursor = conn.cursor()
            cursor.timeout = timeout
            self.register_cursor(exec_id, cursor)

            # Enforce read-only isolation and low deadlock priority
            cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED;")
            cursor.execute("SET DEADLOCK_PRIORITY LOW;")

            # Execute the user's query (with parameters if provided)
            if parameters:
                cursor.execute(sql, parameters)
            else:
                cursor.execute(sql)

            # Extract column metadata
            columns: List[ColumnMetadata] = []
            col_names: List[str] = []
            if cursor.description:
                for col in cursor.description:
                    col_name = col[0]
                    col_names.append(col_name)
                    columns.append(
                        ColumnMetadata(
                            name=col_name,
                            type_name=get_type_name(col[1]),
                            precision=col[4],
                            scale=col[5],
                            nullable=col[6],
                        )
                    )

            # Fetch up to max_rows sequentially
            raw_rows = cursor.fetchmany(max_rows)
            formatted_rows: List[Dict[str, Any]] = []

            for row in raw_rows:
                row_dict = {}
                for idx, col_name in enumerate(col_names):
                    row_dict[col_name] = serialize_sql_value(row[idx])
                formatted_rows.append(row_dict)

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            return QueryExecutionResponse(
                execution_id=exec_id,
                status="success",
                row_count=len(formatted_rows),
                duration_ms=elapsed_ms,
                columns=columns,
                rows=formatted_rows,
            )

        except pyodbc.OperationalError as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            err_str = str(exc)
            # Check for query cancellation (ODBC state HY008)
            if "HY008" in err_str or "Operation canceled" in err_str:
                logger.info("Execution %s was cancelled by user.", exec_id)
                return QueryExecutionResponse(
                    execution_id=exec_id,
                    status="cancelled",
                    row_count=0,
                    duration_ms=elapsed_ms,
                    error_message="Query execution was cancelled.",
                )
            logger.error("SQL Server OperationalError in %s: %s", exec_id, exc)
            return QueryExecutionResponse(
                execution_id=exec_id,
                status="failed",
                row_count=0,
                duration_ms=elapsed_ms,
                error_message=f"SQL Execution Error: {err_str}",
            )

        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("Error executing query %s: %s", exec_id, exc)
            return QueryExecutionResponse(
                execution_id=exec_id,
                status="failed",
                row_count=0,
                duration_ms=elapsed_ms,
                error_message=f"Execution Error: {str(exc)}",
            )

        finally:
            self.unregister_cursor(exec_id)
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


_default_executor = SQLExecutor()


def get_sql_executor() -> SQLExecutor:
    """Return singleton executor instance."""
    return _default_executor

