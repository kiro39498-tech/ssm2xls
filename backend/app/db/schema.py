from app.db.sqlite import get_db_connection
from app.core.logging import get_logger

logger = get_logger(__name__)

SCHEMA_SQL = """
-- Export Jobs Queue Table
CREATE TABLE IF NOT EXISTS export_jobs (
    id TEXT PRIMARY KEY,
    query_id TEXT,
    query_version_id TEXT,
    report_title TEXT NOT NULL,
    sql_text TEXT NOT NULL,
    database_name TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending',
    progress_pct INTEGER DEFAULT 0,
    rows_exported INTEGER DEFAULT 0,
    file_path TEXT,
    file_size_bytes INTEGER DEFAULT 0,
    error_message TEXT,
    parameters_json TEXT,
    execution_duration_ms INTEGER DEFAULT 0,
    include_sql INTEGER DEFAULT 0,
    worker_id TEXT,
    heartbeat_at TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_export_jobs_status ON export_jobs(status);
CREATE INDEX IF NOT EXISTS idx_export_jobs_requested_by ON export_jobs(requested_by);
CREATE INDEX IF NOT EXISTS idx_export_jobs_expires_at ON export_jobs(expires_at);
CREATE INDEX IF NOT EXISTS idx_export_jobs_created_at ON export_jobs(created_at);

-- Saved Queries Table
CREATE TABLE IF NOT EXISTS queries (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    database_name TEXT NOT NULL,
    category TEXT DEFAULT 'General',
    is_active INTEGER DEFAULT 1,
    current_version_id TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_queries_created_by ON queries(created_by);
CREATE INDEX IF NOT EXISTS idx_queries_is_active ON queries(is_active);

-- Immutable Query Versions Table
CREATE TABLE IF NOT EXISTS query_versions (
    id TEXT PRIMARY KEY,
    query_id TEXT NOT NULL REFERENCES queries(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    sql_text TEXT NOT NULL,
    parameters_schema_json TEXT,
    status TEXT NOT NULL DEFAULT 'Draft', -- Draft, Tested, Approved, Active, Archived
    change_summary TEXT,
    created_by TEXT NOT NULL,
    tested_by TEXT,
    tested_at TEXT,
    test_results_summary TEXT,
    approved_by TEXT,
    approved_at TEXT,
    activated_by TEXT,
    activated_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(query_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_query_versions_query_id ON query_versions(query_id);
CREATE INDEX IF NOT EXISTS idx_query_versions_status ON query_versions(status);

-- Execution Audit Logs Table
CREATE TABLE IF NOT EXISTS execution_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id TEXT,
    query_version_id TEXT,
    executed_by TEXT NOT NULL,
    execution_type TEXT NOT NULL, -- Preview, Export
    database_name TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    rows_returned INTEGER NOT NULL,
    status TEXT NOT NULL,        -- Success, Failed, Cancelled
    error_message TEXT,
    parameters_json TEXT,
    executed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_query_id ON execution_audit_logs(query_id);
CREATE INDEX IF NOT EXISTS idx_audit_executed_by ON execution_audit_logs(executed_by);
CREATE INDEX IF NOT EXISTS idx_audit_executed_at ON execution_audit_logs(executed_at);
"""


def init_schema(db_path=None) -> None:
    """Initialize database tables and indexes."""
    logger.info("Ensuring metadata database schema is up-to-date")
    with get_db_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
    logger.info("Metadata database schema initialized successfully")

