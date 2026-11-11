from dataclasses import dataclass, field
from typing import List, Optional, Set
import sqlglot
import sqlglot.expressions as exp
from sqlglot.errors import ParseError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Dangerous keywords and extended procedures / functions
FORBIDDEN_FUNCTIONS: Set[str] = {
    "OPENROWSET",
    "OPENDATASOURCE",
    "OPENQUERY",
    "OPENXML",
    "XP_CMDSHELL",
    "SP_EXECUTESQL",
    "SHUTDOWN",
    "WAITFOR",
}

# Forbidden statement and AST node classes
FORBIDDEN_AST_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.AlterTable,
    exp.Create,
    exp.TruncateTable,
    exp.Merge,
    exp.Command,  # e.g., EXEC, DBCC, KILL
    exp.Into,     # SELECT ... INTO new_table
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
)


@dataclass
class ValidationResult:
    """Result of structural SQL AST validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    statement_type: Optional[str] = None
    tables_referenced: List[str] = field(default_factory=list)
    normalized_sql: Optional[str] = None


class SQLValidator:
    """
    Enforces read-only SELECT security using structural AST parsing (SQLGlot T-SQL dialect).
    Rejects DDL, DML, multiple statements, SELECT INTO, cross-server queries, and dangerous functions.
    """

    def __init__(self, dialect: str = "tsql"):
        self.dialect = dialect

    def validate(self, sql: str, allowed_database: Optional[str] = None) -> ValidationResult:
        """
        Validate SQL string. Returns ValidationResult with detailed error list.
        """
        errors: List[str] = []

        if not sql or not sql.strip():
            return ValidationResult(is_valid=False, errors=["SQL query must not be empty."])

        # 1. Parse SQL into AST
        try:
            expressions = sqlglot.parse(sql, read=self.dialect)
        except ParseError as exc:
            logger.info("SQL syntax parse error: %s", exc)
            return ValidationResult(
                is_valid=False,
                errors=[f"SQL Syntax Error: {str(exc)}"],
            )
        except Exception as exc:
            logger.warning("Unexpected error during SQL parsing: %s", exc)
            return ValidationResult(
                is_valid=False,
                errors=[f"Unable to parse SQL query: {str(exc)}"],
            )

        if not expressions:
            return ValidationResult(is_valid=False, errors=["No valid SQL statements found."])

        # 2. Reject multi-statement / batch scripts
        if len(expressions) > 1:
            return ValidationResult(
                is_valid=False,
                errors=[
                    f"Multiple SQL statements ({len(expressions)}) detected. "
                    "Only a single SELECT statement is permitted."
                ],
            )

        root = expressions[0]
        if root is None:
            return ValidationResult(is_valid=False, errors=["Parsed SQL expression was empty."])

        # 3. Check root statement type (must be Select or Union or CTE)
        if not isinstance(root, (exp.Select, exp.Union)):
            statement_type = root.key.upper() if hasattr(root, "key") else type(root).__name__
            return ValidationResult(
                is_valid=False,
                errors=[
                    f"Statement type '{statement_type}' is not allowed. "
                    "Only SELECT or CTE-based SELECT queries are permitted."
                ],
                statement_type=statement_type,
            )

        statement_type = "SELECT" if isinstance(root, exp.Select) else "UNION"

        # 4. Deep AST traversal for forbidden operations
        tables: Set[str] = set()

        for node in root.walk():
            # Check forbidden AST nodes
            if isinstance(node, FORBIDDEN_AST_NODES):
                node_name = type(node).__name__
                if isinstance(node, exp.Into):
                    errors.append("SELECT INTO construct is forbidden. Table creation is not permitted.")
                elif isinstance(node, exp.Command):
                    cmd_text = getattr(node, "this", "") or ""
                    errors.append(f"Command execution (e.g. EXEC, DBCC) is forbidden: {cmd_text[:50]}")
                else:
                    errors.append(f"Forbidden SQL operation detected: {node_name}")

            # Check function calls (OPENROWSET, OPENDATASOURCE, XP_CMDSHELL, etc.)
            if isinstance(node, (exp.Func, exp.Anonymous)):
                func_name = getattr(node, "name", "")
                if func_name and func_name.upper() in FORBIDDEN_FUNCTIONS:
                    errors.append(f"Restricted function or procedure '{func_name.upper()}' is not permitted.")

            # Check table references (collect tables, detect cross-server / cross-db)
            if isinstance(node, exp.Table):
                # Inspect table parts
                table_parts = node.parts
                parts_count = len(table_parts)

                # 4-part name: server.database.schema.table -> Cross-server
                if parts_count >= 4:
                    errors.append(
                        f"Cross-server / linked-server query '{node.sql(dialect=self.dialect)}' is not permitted."
                    )
                # 3-part name: database.schema.table -> Cross-database
                elif parts_count == 3:
                    db_part = node.catalog
                    if allowed_database and db_part and db_part.lower() != allowed_database.lower():
                        errors.append(
                            f"Cross-database access to '{db_part}' is not permitted. "
                            f"Only database '{allowed_database}' is allowed."
                        )

                table_name = f"{node.db}.{node.name}" if node.db else node.name
                if table_name:
                    tables.add(table_name)

        if errors:
            return ValidationResult(
                is_valid=False,
                errors=list(dict.fromkeys(errors)),  # deduplicate preserving order
                statement_type=statement_type,
                tables_referenced=sorted(list(tables)),
            )

        # Generate normalized T-SQL
        normalized_sql = root.sql(dialect=self.dialect)

        return ValidationResult(
            is_valid=True,
            errors=[],
            statement_type=statement_type,
            tables_referenced=sorted(list(tables)),
            normalized_sql=normalized_sql,
        )


_default_validator = SQLValidator()


def get_sql_validator() -> SQLValidator:
    """Return singleton validator instance."""
    return _default_validator
