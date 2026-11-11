import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.sqlite import get_db_connection
from app.schemas.reports import (
    CreateReportRequest,
    UpdateDraftVersionRequest,
    NewDraftVersionRequest,
    QueryVersionResponse,
    ReportResponse,
)
from app.services.sql.validator import get_sql_validator

logger = get_logger(__name__)


def row_to_version_response(row: Any) -> QueryVersionResponse:
    """Map SQLite row to Pydantic QueryVersionResponse."""
    return QueryVersionResponse(
        id=row["id"],
        query_id=row["query_id"],
        version_number=row["version_number"],
        sql_text=row["sql_text"],
        parameters_schema_json=row["parameters_schema_json"],
        status=row["status"],
        change_summary=row["change_summary"],
        created_by=row["created_by"],
        tested_by=row["tested_by"],
        tested_at=row["tested_at"],
        test_results_summary=row["test_results_summary"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
        activated_by=row["activated_by"],
        activated_at=row["activated_at"],
        created_at=row["created_at"],
    )


def row_to_report_response(row: Any, version_row: Any = None) -> ReportResponse:
    """Map SQLite rows to ReportResponse with current version."""
    current_ver = row_to_version_response(version_row) if version_row else None
    return ReportResponse(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        database_name=row["database_name"],
        category=row["category"] or "General",
        is_active=bool(row["is_active"]),
        current_version_id=row["current_version_id"],
        current_version=current_ver,
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ReportService:
    """Handles report query definitions, immutable versioning, and approval state machine."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    def create_report(self, req: CreateReportRequest, user: str) -> ReportResponse:
        """Create a new report query definition and initial Draft v1."""
        settings = get_settings()
        target_db = req.database or settings.sql_database

        # 1. Structural AST validation of initial SQL
        validator = get_sql_validator()
        val_result = validator.validate(req.initial_sql, allowed_database=target_db)
        if not val_result.is_valid:
            error_str = "; ".join(val_result.errors)
            raise ValueError(f"Initial SQL validation failed: {error_str}")

        now_iso = datetime.now(timezone.utc).isoformat()
        query_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        with get_db_connection(self.db_path) as conn:
            # Insert query parent
            conn.execute(
                """
                INSERT INTO queries (
                    id, title, description, database_name, category,
                    is_active, current_version_id, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    query_id,
                    req.title,
                    req.description,
                    target_db,
                    req.category,
                    version_id,
                    user,
                    now_iso,
                    now_iso,
                ),
            )

            # Insert initial draft version 1
            conn.execute(
                """
                INSERT INTO query_versions (
                    id, query_id, version_number, sql_text, status,
                    change_summary, created_by, created_at
                ) VALUES (?, ?, 1, ?, 'Draft', 'Initial Draft Creation', ?, ?)
                """,
                (
                    version_id,
                    query_id,
                    req.initial_sql,
                    user,
                    now_iso,
                ),
            )

        logger.info("Created report '%s' (%s) with initial Draft v1 by %s", req.title, query_id, user)
        res = self.get_report(query_id)
        if not res:
            raise RuntimeError(f"Failed to load newly created report {query_id}")
        return res

    def get_report(self, query_id: str) -> Optional[ReportResponse]:
        """Fetch report by ID with current version."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM queries WHERE id = ?", (query_id,))
            q_row = cursor.fetchone()
            if not q_row:
                return None

            v_row = None
            if q_row["current_version_id"]:
                v_cursor = conn.execute("SELECT * FROM query_versions WHERE id = ?", (q_row["current_version_id"],))
                v_row = v_cursor.fetchone()

            return row_to_report_response(q_row, v_row)

    def list_reports(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ReportResponse], int]:
        """List reports with search, filtering, and pagination."""
        conditions = []
        params = []

        if search:
            conditions.append("(title LIKE ? OR description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if category:
            conditions.append("category = ?")
            params.append(category)
        if is_active is not None:
            conditions.append("is_active = ?")
            params.append(1 if is_active else 0)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with get_db_connection(self.db_path) as conn:
            count_sql = f"SELECT COUNT(*) FROM queries {where_clause}"
            total = conn.execute(count_sql, tuple(params)).fetchone()[0]

            query_sql = f"""
                SELECT * FROM queries
                {where_clause}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """
            cursor = conn.execute(query_sql, tuple(params + [limit, offset]))
            q_rows = cursor.fetchall()

            reports = []
            for qr in q_rows:
                vr = None
                if qr["current_version_id"]:
                    vr = conn.execute("SELECT * FROM query_versions WHERE id = ?", (qr["current_version_id"],)).fetchone()
                reports.append(row_to_report_response(qr, vr))

            return reports, total

    def get_version(self, version_id: str) -> Optional[QueryVersionResponse]:
        """Fetch specific version record."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM query_versions WHERE id = ?", (version_id,))
            row = cursor.fetchone()
            if row:
                return row_to_version_response(row)
        return None

    def list_versions(self, query_id: str) -> List[QueryVersionResponse]:
        """List all version history for a query ordered by version_number descending."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT * FROM query_versions
                WHERE query_id = ?
                ORDER BY version_number DESC
                """,
                (query_id,),
            )
            rows = cursor.fetchall()
            return [row_to_version_response(r) for r in rows]

    def update_draft_version(
        self,
        version_id: str,
        req: UpdateDraftVersionRequest,
        user: str,
    ) -> QueryVersionResponse:
        """
        Modify a draft version.
        IMMUTABILITY RULE: Approved, Active, or Archived versions CANNOT be modified.
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM query_versions WHERE id = ?", (version_id,))
            v_row = cursor.fetchone()
            if not v_row:
                raise ValueError(f"Version '{version_id}' not found.")

            if v_row["status"] != "Draft":
                raise ValueError(
                    f"Version is in '{v_row['status']}' status and is immutable. "
                    "Approved, Active, and Archived versions cannot be modified in place. "
                    "Create a new draft version to make changes."
                )

            # Get target database from parent query
            q_cursor = conn.execute("SELECT database_name FROM queries WHERE id = ?", (v_row["query_id"],))
            q_row = q_cursor.fetchone()
            target_db = q_row["database_name"] if q_row else None

            # Validate updated SQL
            validator = get_sql_validator()
            val_result = validator.validate(req.sql, allowed_database=target_db)
            if not val_result.is_valid:
                error_str = "; ".join(val_result.errors)
                raise ValueError(f"Updated SQL validation failed: {error_str}")

            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                UPDATE query_versions
                SET sql_text = ?,
                    change_summary = ?,
                    parameters_schema_json = ?
                WHERE id = ?
                """,
                (req.sql, req.change_summary, req.parameters_schema_json, version_id),
            )

            conn.execute(
                "UPDATE queries SET updated_at = ? WHERE id = ?",
                (now_iso, v_row["query_id"]),
            )

        logger.info("Updated draft version %s by %s", version_id, user)
        res = self.get_version(version_id)
        if not res:
            raise RuntimeError(f"Failed to reload version {version_id}")
        return res

    def clone_to_new_draft(
        self,
        query_id: str,
        from_version_id: Optional[str],
        change_summary: Optional[str],
        user: str,
    ) -> QueryVersionResponse:
        """
        Clone an existing version into a new Draft version with an incremented version number.
        """
        with get_db_connection(self.db_path) as conn:
            # Check report exists
            q_cursor = conn.execute("SELECT * FROM queries WHERE id = ?", (query_id,))
            q_row = q_cursor.fetchone()
            if not q_row:
                raise ValueError(f"Report query '{query_id}' not found.")

            # Identify source version to clone from
            src_version_id = from_version_id or q_row["current_version_id"]
            if not src_version_id:
                raise ValueError("No source version available to clone from.")

            v_cursor = conn.execute("SELECT * FROM query_versions WHERE id = ?", (src_version_id,))
            src_row = v_cursor.fetchone()
            if not src_row:
                raise ValueError(f"Source version '{src_version_id}' not found.")

            # Determine next version number
            max_ver_cursor = conn.execute(
                "SELECT MAX(version_number) FROM query_versions WHERE query_id = ?",
                (query_id,),
            )
            max_ver = max_ver_cursor.fetchone()[0] or 1
            new_version_number = max_ver + 1

            new_version_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()

            conn.execute(
                """
                INSERT INTO query_versions (
                    id, query_id, version_number, sql_text, parameters_schema_json,
                    status, change_summary, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, 'Draft', ?, ?, ?)
                """,
                (
                    new_version_id,
                    query_id,
                    new_version_number,
                    src_row["sql_text"],
                    src_row["parameters_schema_json"],
                    change_summary or f"Cloned from version {src_row['version_number']}",
                    user,
                    now_iso,
                ),
            )

            conn.execute("UPDATE queries SET updated_at = ? WHERE id = ?", (now_iso, query_id))

        logger.info(
            "Created new Draft v%d (%s) for query %s by %s",
            new_version_number,
            new_version_id,
            query_id,
            user,
        )
        res = self.get_version(new_version_id)
        if not res:
            raise RuntimeError(f"Failed to load newly created draft {new_version_id}")
        return res

    def test_version(
        self,
        version_id: str,
        test_summary: str,
        user: str,
    ) -> QueryVersionResponse:
        """Transition version from Draft -> Tested."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute("SELECT status, query_id FROM query_versions WHERE id = ?", (version_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Version '{version_id}' not found.")

            conn.execute(
                """
                UPDATE query_versions
                SET status = 'Tested',
                    tested_by = ?,
                    tested_at = ?,
                    test_results_summary = ?
                WHERE id = ?
                """,
                (user, now_iso, test_summary, version_id),
            )
            conn.execute("UPDATE queries SET updated_at = ? WHERE id = ?", (now_iso, row["query_id"]))

        logger.info("Marked version %s as Tested by %s", version_id, user)
        return self.get_version(version_id)  # type: ignore

    def approve_version(self, version_id: str, user: str) -> QueryVersionResponse:
        """Transition version from Tested -> Approved."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute("SELECT status, query_id FROM query_versions WHERE id = ?", (version_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Version '{version_id}' not found.")

            conn.execute(
                """
                UPDATE query_versions
                SET status = 'Approved',
                    approved_by = ?,
                    approved_at = ?
                WHERE id = ?
                """,
                (user, now_iso, version_id),
            )
            conn.execute("UPDATE queries SET updated_at = ? WHERE id = ?", (now_iso, row["query_id"]))

        logger.info("Approved version %s by %s", version_id, user)
        return self.get_version(version_id)  # type: ignore

    def activate_version(self, version_id: str, user: str) -> QueryVersionResponse:
        """
        Transition version from Approved -> Active.
        Sets queries.current_version_id = version_id.
        Archives any previously active version for this query.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.execute("SELECT query_id, status FROM query_versions WHERE id = ?", (version_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Version '{version_id}' not found.")

            query_id = row["query_id"]

            # Archive existing Active versions for this query
            conn.execute(
                """
                UPDATE query_versions
                SET status = 'Archived'
                WHERE query_id = ? AND status = 'Active' AND id != ?
                """,
                (query_id, version_id),
            )

            # Activate this version
            conn.execute(
                """
                UPDATE query_versions
                SET status = 'Active',
                    activated_by = ?,
                    activated_at = ?
                WHERE id = ?
                """,
                (user, now_iso, version_id),
            )

            # Point parent query to this active version
            conn.execute(
                """
                UPDATE queries
                SET current_version_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (version_id, now_iso, query_id),
            )

        logger.info("Activated version %s for query %s by %s", version_id, query_id, user)
        return self.get_version(version_id)  # type: ignore

    def toggle_report_active(self, query_id: str, is_active: bool) -> ReportResponse:
        """Enable or disable an entire report."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE queries SET is_active = ?, updated_at = ? WHERE id = ?",
                (1 if is_active else 0, now_iso, query_id),
            )
        res = self.get_report(query_id)
        if not res:
            raise ValueError(f"Report '{query_id}' not found.")
        return res


_default_report_service = ReportService()


def get_report_service() -> ReportService:
    return _default_report_service

