import pytest
from app.services.sql.validator import SQLValidator


@pytest.fixture
def validator() -> SQLValidator:
    return SQLValidator(dialect="tsql")


@pytest.mark.unit
def test_valid_select_queries(validator: SQLValidator):
    """Test standard SELECT variants are accepted."""
    queries = [
        "SELECT 1 AS num;",
        "SELECT id, name, created_at FROM users WHERE status = 'active';",
        "SELECT u.id, o.total FROM users u INNER JOIN orders o ON u.id = o.user_id;",
        "SELECT department, COUNT(*) as cnt FROM employees GROUP BY department HAVING COUNT(*) > 5;",
        "SELECT * FROM products ORDER BY price DESC;",
        "SELECT id FROM users WHERE id IN (SELECT user_id FROM orders WHERE total > 100);",
    ]
    for q in queries:
        result = validator.validate(q)
        assert result.is_valid is True, f"Failed for valid query: {q}. Errors: {result.errors}"
        assert result.statement_type == "SELECT"


@pytest.mark.unit
def test_valid_cte_query(validator: SQLValidator):
    """Test CTE queries are accepted and identified."""
    query = """
    WITH RecentOrders AS (
        SELECT user_id, SUM(total) AS total_spent
        FROM orders
        WHERE order_date >= '2024-01-01'
        GROUP BY user_id
    )
    SELECT u.name, r.total_spent
    FROM users u
    INNER JOIN RecentOrders r ON u.id = r.user_id;
    """
    result = validator.validate(query)
    assert result.is_valid is True, f"Errors: {result.errors}"
    assert "users" in [t.lower() for t in result.tables_referenced]
    assert "orders" in [t.lower() for t in result.tables_referenced]


@pytest.mark.unit
def test_valid_union_query(validator: SQLValidator):
    """Test UNION queries are accepted."""
    query = "SELECT id, 'user' AS type FROM users UNION ALL SELECT id, 'admin' AS type FROM admins;"
    result = validator.validate(query)
    assert result.is_valid is True, f"Errors: {result.errors}"
    assert result.statement_type == "UNION"


@pytest.mark.unit
def test_reject_dml_statements(validator: SQLValidator):
    """Reject INSERT, UPDATE, DELETE, MERGE statements."""
    forbidden = [
        "INSERT INTO users (name) VALUES ('Hacker');",
        "UPDATE users SET role = 'admin' WHERE id = 1;",
        "DELETE FROM users WHERE id = 1;",
        "MERGE INTO target USING source ON target.id = source.id WHEN MATCHED THEN DELETE;",
    ]
    for q in forbidden:
        result = validator.validate(q)
        assert result.is_valid is False, f"Should have rejected DML query: {q}"
        assert any("permitted" in err or "forbidden" in err or "not allowed" in err for err in result.errors)


@pytest.mark.unit
def test_reject_ddl_statements(validator: SQLValidator):
    """Reject DROP, TRUNCATE, ALTER, CREATE statements."""
    forbidden = [
        "DROP TABLE users;",
        "TRUNCATE TABLE logs;",
        "ALTER TABLE users ADD COLUMN is_admin BIT;",
        "CREATE TABLE backdoors (id INT);",
        "CREATE VIEW dangerous_view AS SELECT * FROM users;",
    ]
    for q in forbidden:
        result = validator.validate(q)
        assert result.is_valid is False, f"Should have rejected DDL query: {q}"


@pytest.mark.unit
def test_reject_select_into(validator: SQLValidator):
    """Reject SELECT INTO table creation."""
    query = "SELECT id, name INTO users_backup FROM users;"
    result = validator.validate(query)
    assert result.is_valid is False
    assert any("SELECT INTO" in err for err in result.errors)


@pytest.mark.unit
def test_reject_multi_statement(validator: SQLValidator):
    """Reject multiple statements in batch."""
    queries = [
        "SELECT 1; DROP TABLE users;",
        "SELECT 1; SELECT 2;",
        "SELECT * FROM users; UPDATE users SET active = 0;",
    ]
    for q in queries:
        result = validator.validate(q)
        assert result.is_valid is False
        assert any("Multiple SQL statements" in err for err in result.errors)


@pytest.mark.unit
def test_reject_commands_and_exec(validator: SQLValidator):
    """Reject EXEC, EXECUTE, DBCC, SHUTDOWN."""
    queries = [
        "EXEC sp_who2;",
        "EXEC xp_cmdshell 'whoami';",
        "EXECUTE ('SELECT 1');",
        "DBCC CHECKDB;",
        "SHUTDOWN WITH NOWAIT;",
    ]
    for q in queries:
        result = validator.validate(q)
        assert result.is_valid is False


@pytest.mark.unit
def test_reject_dangerous_functions(validator: SQLValidator):
    """Reject OPENROWSET, OPENDATASOURCE, OPENQUERY."""
    queries = [
        "SELECT * FROM OPENROWSET('SQLNCLI', 'Server=remotesrv;', 'SELECT 1') AS a;",
        "SELECT * FROM OPENDATASOURCE('SQLNCLI', 'Data Source=remotesrv;').master.dbo.users;",
    ]
    for q in queries:
        result = validator.validate(q)
        assert result.is_valid is False
        assert any("Restricted function" in err or "not permitted" in err or "Cross-server" in err for err in result.errors)


@pytest.mark.unit
def test_reject_cross_server_4part_names(validator: SQLValidator):
    """Reject linked-server 4-part table references."""
    query = "SELECT * FROM RemoteServer.SalesDB.dbo.Orders;"
    result = validator.validate(query)
    assert result.is_valid is False
    assert any("Cross-server" in err or "linked-server" in err for err in result.errors)


@pytest.mark.unit
def test_cross_database_restriction(validator: SQLValidator):
    """Enforce allowed database restriction when specified."""
    # When target DB is "FinanceDB", query accessing "HRPayroll" must be rejected
    query_unauthorized = "SELECT * FROM HRPayroll.dbo.Salaries;"
    result = validator.validate(query_unauthorized, allowed_database="FinanceDB")
    assert result.is_valid is False
    assert any("Cross-database access to 'HRPayroll' is not permitted" in err for err in result.errors)

    # When querying the authorized database, it should be accepted
    query_authorized = "SELECT * FROM FinanceDB.dbo.Invoices;"
    result = validator.validate(query_authorized, allowed_database="FinanceDB")
    assert result.is_valid is True, f"Errors: {result.errors}"


@pytest.mark.unit
def test_syntax_error_handling(validator: SQLValidator):
    """Test malformed SQL syntax returns clean error without raising."""
    query = "SELECT FROM WHERE;"
    result = validator.validate(query)
    assert result.is_valid is False
    assert any("Syntax Error" in err for err in result.errors)


@pytest.mark.unit
def test_empty_sql_handling(validator: SQLValidator):
    """Test empty SQL strings return validation error."""
    assert validator.validate("").is_valid is False
    assert validator.validate("   \n\t  ").is_valid is False

