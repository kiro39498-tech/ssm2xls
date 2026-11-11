from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(default="SSMS2XLS", description="Application name")
    app_env: str = Field(default="development", description="Environment (development, staging, production)")
    debug: bool = Field(default=False, description="Debug mode")
    host: str = Field(default="127.0.0.1", description="Host to bind server")
    port: int = Field(default=8000, description="Port to bind server")
    log_level: str = Field(default="INFO", description="Logging level")

    # SQLite Metadata Database settings
    sqlite_db_path: str = Field(default="data/metadata.db", description="Path to SQLite metadata database")
    sqlite_busy_timeout_ms: int = Field(default=30000, description="SQLite busy timeout in milliseconds")

    # SQL Server Target Connection settings (ODBC Driver 18)
    sql_server: str = Field(default="localhost", description="SQL Server host / instance name")
    sql_database: str = Field(default="master", description="Default SQL database name")
    sql_driver: str = Field(default="ODBC Driver 18 for SQL Server", description="ODBC driver name")
    sql_trusted_connection: bool = Field(default=True, description="Use Windows Integrated Authentication")
    sql_encrypt: bool = Field(default=True, description="Require encrypted connection")
    sql_trust_server_certificate: bool = Field(
        default=False,
        description="Trust server certificate without CA verification. Defaults to False. Set to True only for local dev.",
    )
    sql_connection_timeout: int = Field(default=15, description="Connection timeout in seconds")
    sql_query_timeout: int = Field(default=30, description="Query execution timeout in seconds")

    def get_sqlite_path(self) -> Path:
        """Resolve SQLite path relative to backend root directory if relative."""
        p = Path(self.sqlite_db_path)
        if not p.is_absolute():
            backend_root = Path(__file__).resolve().parent.parent.parent
            p = backend_root / p
        return p

    def build_sql_server_connection_string(self, database: str | None = None) -> str:
        """Build standard pyodbc connection string for SQL Server."""
        db = database or self.sql_database
        trusted = "yes" if self.sql_trusted_connection else "no"
        encrypt = "yes" if self.sql_encrypt else "no"
        trust_cert = "yes" if self.sql_trust_server_certificate else "no"

        return (
            f"DRIVER={{{self.sql_driver}}};"
            f"SERVER={self.sql_server};"
            f"DATABASE={db};"
            f"Trusted_Connection={trusted};"
            f"Encrypt={encrypt};"
            f"TrustServerCertificate={trust_cert};"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()
