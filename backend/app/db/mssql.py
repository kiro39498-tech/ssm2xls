import pyodbc
from contextlib import contextmanager
from typing import Generator
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_mssql_connection(database: str | None = None) -> pyodbc.Connection:
    """
    Establish a connection to Microsoft SQL Server using pyodbc and ODBC Driver 18.
    Uses Windows Integrated Authentication (Trusted_Connection=yes).
    """
    settings = get_settings()
    conn_str = settings.build_sql_server_connection_string(database)
    logger.debug("Connecting to SQL Server: %s", settings.sql_server)

    try:
        conn = pyodbc.connect(conn_str, timeout=settings.sql_connection_timeout)
        return conn
    except pyodbc.Error as exc:
        logger.error("Failed to connect to SQL Server (%s): %s", settings.sql_server, exc)
        raise


@contextmanager
def get_mssql_session(database: str | None = None) -> Generator[pyodbc.Connection, None, None]:
    """Context manager for safely managing SQL Server connection lifecycle."""
    conn = get_mssql_connection(database)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception as exc:
            logger.warning("Error closing SQL Server connection: %s", exc)


def check_mssql_health(database: str | None = None) -> dict:
    """
    Check SQL Server readiness and connectivity.
    Gracefully catches connection failures and returns diagnostic information
    so application liveness is not coupled to SQL Server availability.
    """
    settings = get_settings()
    target_server = settings.sql_server
    target_db = database or settings.sql_database

    try:
        conn = get_mssql_connection(target_db)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT @@VERSION AS version, DB_NAME() AS current_db, @@SERVERNAME AS server_name;"
            )
            row = cursor.fetchone()
            version = row[0] if row else "Unknown"
            current_db = row[1] if row else target_db
            server_name = row[2] if row else target_server
            cursor.close()

            # Extract first line of SQL Server version (e.g. "Microsoft SQL Server 2022...")
            version_summary = version.split("\n")[0].strip() if version else "Unknown"

            return {
                "status": "connected",
                "connected": True,
                "server": target_server,
                "server_instance": server_name,
                "database": current_db,
                "driver": settings.sql_driver,
                "version": version_summary,
                "encrypt": settings.sql_encrypt,
                "trust_server_certificate": settings.sql_trust_server_certificate,
            }
        finally:
            conn.close()
    except pyodbc.Error as exc:
        error_msg = str(exc)
        logger.warning("SQL Server health check: instance '%s' unreachable: %s", target_server, error_msg)
        return {
            "status": "unreachable",
            "connected": False,
            "server": target_server,
            "database": target_db,
            "driver": settings.sql_driver,
            "encrypt": settings.sql_encrypt,
            "trust_server_certificate": settings.sql_trust_server_certificate,
            "error": error_msg,
        }
    except Exception as exc:
        logger.warning("SQL Server health check encountered unexpected error: %s", exc)
        return {
            "status": "error",
            "connected": False,
            "server": target_server,
            "database": target_db,
            "error": str(exc),
        }

