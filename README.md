# SSMS2XLS: Internal SQL Query & Excel Export Portal

An internal web application designed to replace the manual developer workflow:
**SSMS → Execute SQL → Validate results → Copy SQL into SAP Crystal Reports → Generate Excel reports.**

Provides a secure, high-performance environment to write, validate, preview, version, approve, and execute SQL queries against Microsoft SQL Server, with automated generation of downloadable Excel workbooks.

---

## Architecture Highlights

- **Backend:** FastAPI (Python 3.11) with structured logging and pydantic settings.
- **SQL Connectivity:** `pyodbc` with **Microsoft ODBC Driver 18 for SQL Server** and Windows Integrated Authentication.
- **Metadata Database:** SQLite configured in **WAL mode** with a **30,000 ms busy timeout** and foreign keys enabled per connection.
- **Query Validation:** Structural AST validation via **SQLGlot** (T-SQL dialect) [Phase 2].
- **Excel Generation:** Streaming, chunked processing using **XlsxWriter** in `constant_memory=True` mode [Phase 4].
- **Job Processing:** Dedicated background worker claiming jobs from SQLite queue using atomic transactions [Phase 5].
- **Frontend:** React + TypeScript with Monaco Editor [Phase 7].

---

## Current Status: Phase 1 through Phase 7 Completed

- **Phase 1 (Backend Foundation & Connectivity):**
  - Scaffolding, configuration management, and environment isolation.
  - SQLite metadata database with WAL mode and per-connection busy timeout / foreign key enforcement.
  - Microsoft ODBC Driver 18 connection layer supporting Windows Authentication and configurable certificate trust.
  - Health checks distinguishing application liveness from SQL Server readiness.

- **Phase 2 (SQLGlot Validation & Read-Only Execution Engine):**
  - Structural AST validation using **SQLGlot** with the T-SQL dialect (`tsql`).
  - Strict enforcement of single-statement `SELECT` and CTE-based `SELECT` queries.
  - Rejection of DML, DDL, `SELECT INTO`, commands (`EXEC`), dangerous functions, and cross-server/cross-database queries.
  - Execution engine with `READ COMMITTED` isolation, low deadlock priority, timeout enforcement, query cancellation (`SQLCancel`), and column metadata extraction.
  - REST API endpoints for SQL validation, execution preview, and cancellation.

- **Phase 4 (Chunked Excel Generation Engine):**
  - Sequential, chunked streaming using **XlsxWriter** in `constant_memory=True` mode.
  - Benchmarked peak memory: **3.57 MB** for 100,000 rows.
  - Multi-worksheet partitioning at ~900,000 rows.
  - Frozen header rows, autofilters, date/numeric formatting, and sensible column widths.
  - Two-tab report structure: Data worksheets + **Report Information** audit sheet.
  - Secure SQL query toggle: SQL text is included only on explicit developer request and hidden from report users.

- **Phase 5 (Database-Backed Export Queue & Independent Worker):**
  - Database schema (`export_jobs`) in SQLite with indexing on status, requester, and expiration.
  - Atomic job claiming via SQLite `BEGIN IMMEDIATE` preventing duplicate worker claims without Redis/Celery.
  - Standalone Python Export Worker CLI (`python -m app.workers.export_worker`) running out-of-band.
  - Heartbeat tracking, row-level progress updates, cancellation detection, and automatic recovery of stale running jobs.
  - 7-day configurable retention period with automatic file sweeping upon expiration.
  - Secure download endpoint (`GET /api/exports/jobs/{id}/download`) concealing physical disk paths.

- **Phase 6 (Saved Queries, Immutable Versioning, Approval Workflow & Audit Trail):**
  - Schema additions: `queries`, `query_versions`, and `execution_audit_logs`.
  - **Immutability Enforcement:** Once a query version is `Approved`, `Active`, or `Archived`, in-place edits are strictly rejected.
  - **Clone-to-Modify Workflow:** `Draft` → `Tested` → `Approved` → `Active` → `Archived`.
  - Report enablement/disablement controls (`/toggle-active`).
  - Comprehensive audit trail recording user, duration, row counts, and automatic masking of sensitive parameter fields.

- **Phase 7 (React + TypeScript Developer Interface):**
  - Modern enterprise UI built with **Vite, React 19, TypeScript, and Monaco Editor**.
  - **Query Workspace:** Full Monaco SQL editor with T-SQL highlighting, AST validation feedback, live preview execution (up to 1,000 rows), execution cancellation, and export job creation modal.
  - **Export Jobs View:** Real-time polling dashboard displaying queued and running jobs, row export counters, and authorized one-click file download.
  - **Saved Reports & Version Catalog:** Complete version history viewer, one-click lifecycle buttons (`Test`, `Approve`, `Activate`, `Clone to Draft`), and SQL loader.
  - **Audit Trail Screen:** System-wide compliance log table detailing execution times, returned rows, and parameters.

See [docs/setup.md](docs/setup.md) for detailed setup and execution instructions.

