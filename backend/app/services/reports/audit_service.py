import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from app.db.sqlite import get_db_connection
from app.schemas.reports import AuditLogResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

SENSITIVE_PARAM_KEYS = {"password", "secret", "token", "key", "ssn", "credential"}


def mask_sensitive_params(params: Any) -> Any:
    """Mask sensitive parameter values from audit logs."""
    if isinstance(params, dict):
        return {
            k: ("***MASKED***" if any(s in k.lower() for s in SENSITIVE_PARAM_KEYS) else v)
            for k, v in params.items()
        }
    return params


class AuditService:
    """Records and queries execution audit logs for compliance and debugging."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    def record_execution(
        self,
        executed_by: str,
        execution_type: str,
        database_name: str,
        duration_ms: int,
        rows_returned: int,
        status: str,
        query_id: Optional[str] = None,
        query_version_id: Optional[str] = None,
        error_message: Optional[str] = None,
        parameters: Optional[Any] = None,
    ) -> int:
        """Insert an immutable audit log record."""
        now_iso = datetime.now(timezone.utc).isoformat()
        masked = mask_sensitive_params(parameters)
        params_json = json.dumps(masked) if masked else None

        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO execution_audit_logs (
                    query_id, query_version_id, executed_by, execution_type,
                    database_name, duration_ms, rows_returned, status,
                    error_message, parameters_json, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query_id,
                    query_version_id,
                    executed_by,
                    execution_type,
                    database_name,
                    duration_ms,
                    rows_returned,
                    status,
                    error_message,
                    params_json,
                    now_iso,
                ),
            )
            log_id = cursor.lastrowid

        logger.info(
            "Audit log #%d recorded for %s by %s (Status: %s, Rows: %d, Time: %d ms)",
            log_id,
            execution_type,
            executed_by,
            status,
            rows_returned,
            duration_ms,
        )
        return log_id

    def list_logs(
        self,
        query_id: Optional[str] = None,
        executed_by: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AuditLogResponse], int]:
        """Query audit log trail with pagination."""
        conditions = []
        params = []

        if query_id:
            conditions.append("query_id = ?")
            params.append(query_id)
        if executed_by:
            conditions.append("executed_by = ?")
            params.append(executed_by)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with get_db_connection(self.db_path) as conn:
            count_sql = f"SELECT COUNT(*) FROM execution_audit_logs {where_clause}"
            total = conn.execute(count_sql, tuple(params)).fetchone()[0]

            query_sql = f"""
                SELECT * FROM execution_audit_logs
                {where_clause}
                ORDER BY executed_at DESC
                LIMIT ? OFFSET ?
            """
            cursor = conn.execute(query_sql, tuple(params + [limit, offset]))
            rows = cursor.fetchall()

            logs = [
                AuditLogResponse(
                    id=r["id"],
                    query_id=r["query_id"],
                    query_version_id=r["query_version_id"],
                    executed_by=r["executed_by"],
                    execution_type=r["execution_type"],
                    database_name=r["database_name"],
                    duration_ms=r["duration_ms"],
                    rows_returned=r["rows_returned"],
                    status=r["status"],
                    error_message=r["error_message"],
                    parameters_json=r["parameters_json"],
                    executed_at=r["executed_at"],
                )
                for r in rows
            ]
            return logs, total


_default_audit_service = AuditService()


def get_audit_service() -> AuditService:
    return _default_audit_service

