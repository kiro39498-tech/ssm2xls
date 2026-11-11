import decimal
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
import pytest
from app.services.exports.excel_generator import (
    ExcelExportEngine,
    ExportMetadata,
    ExportResult,
)


@pytest.fixture
def export_engine() -> ExcelExportEngine:
    return ExcelExportEngine(max_rows_per_sheet=100, chunk_size=20)


@pytest.mark.unit
def test_basic_excel_export(tmp_path: Path, export_engine: ExcelExportEngine):
    """Test generating a standard Excel workbook with Report Data and Report Information sheets."""
    file_path = tmp_path / "test_report.xlsx"
    columns = ["ID", "Name", "Score", "Active", "Joined"]
    data = [
        (1, "Alice", 95.5, True, date(2023, 1, 15)),
        (2, "Bob", 88.0, False, date(2023, 2, 20)),
        (3, "Charlie", None, True, None),
    ]

    metadata = ExportMetadata(
        report_name="User Scores Report",
        description="A test user score export",
        generated_by="azuread\\testuser",
        server_name="localhost",
        database_name="master",
        query_version="1.0",
        execution_duration_ms=45,
    )

    result = export_engine.generate_export_from_chunks(
        output_path=file_path,
        column_names=columns,
        chunk_iterator=[data],
        metadata=metadata,
    )

    assert result.total_rows == 3
    assert result.sheets_created == 1
    assert result.file_path.exists()
    assert result.file_size_bytes > 0

    # Verify sheet names inside the OpenXML archive
    with zipfile.ZipFile(file_path) as zf:
        tree = ET.fromstring(zf.read("xl/workbook.xml"))
        ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        sheets = [elem.attrib["name"] for elem in tree.findall(".//main:sheet", ns)]
        assert sheets == ["Report Data", "Report Information"]


@pytest.mark.unit
def test_multi_sheet_partitioning(tmp_path: Path):
    """Verify that result sets exceeding max_rows_per_sheet partition across multiple sheets."""
    file_path = tmp_path / "partitioned_report.xlsx"
    # Set small sheet cap of 25 rows to test partitioning
    engine = ExcelExportEngine(max_rows_per_sheet=25, chunk_size=10)

    # Generate 65 rows -> Should create 3 data sheets (25, 25, 15) + 1 info sheet
    chunks = [
        [(i, f"Product {i}", decimal.Decimal(f"{i * 10}.50")) for i in range(chunk_start, min(chunk_start + 10, 65))]
        for chunk_start in range(0, 65, 10)
    ]

    metadata = ExportMetadata(report_name="Inventory Report", generated_by="developer")
    result = engine.generate_export_from_chunks(
        output_path=file_path,
        column_names=["SKU", "Title", "Price"],
        chunk_iterator=chunks,
        metadata=metadata,
    )

    assert result.total_rows == 65
    assert result.sheets_created == 3

    with zipfile.ZipFile(file_path) as zf:
        tree = ET.fromstring(zf.read("xl/workbook.xml"))
        ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        sheets = [elem.attrib["name"] for elem in tree.findall(".//main:sheet", ns)]
        assert sheets == ["Report Data", "Report Data 2", "Report Data 3", "Report Information"]


@pytest.mark.unit
def test_sql_text_omitted_for_non_developers(tmp_path: Path, export_engine: ExcelExportEngine):
    """Ensure SQL query text is never included on Report Information sheet unless include_sql is True."""
    # 1. Standard user export (include_sql = False)
    path_user = tmp_path / "user_export.xlsx"
    meta_user = ExportMetadata(
        report_name="Quarterly Revenue",
        sql_text="SELECT * FROM confidential_revenue_tables;",
        include_sql=False,
    )
    export_engine.generate_export_from_chunks(
        path_user,
        ["Qtr", "Revenue"],
        [[("Q1", 50000), ("Q2", 60000)]],
        meta_user,
    )

    # 2. Developer export (include_sql = True)
    path_dev = tmp_path / "dev_export.xlsx"
    meta_dev = ExportMetadata(
        report_name="Quarterly Revenue Dev",
        sql_text="SELECT * FROM confidential_revenue_tables;",
        include_sql=True,
    )
    export_engine.generate_export_from_chunks(
        path_dev,
        ["Qtr", "Revenue"],
        [[("Q1", 50000), ("Q2", 60000)]],
        meta_dev,
    )

    with zipfile.ZipFile(path_user) as zf_user:
        # Check XML text of shared strings or sheet
        content_user = "".join([zf_user.read(name).decode("utf-8", errors="ignore") for name in zf_user.namelist()])
        assert "confidential_revenue_tables" not in content_user

    with zipfile.ZipFile(path_dev) as zf_dev:
        content_dev = "".join([zf_dev.read(name).decode("utf-8", errors="ignore") for name in zf_dev.namelist()])
        assert "confidential_revenue_tables" in content_dev


@pytest.mark.unit
def test_progress_callback(tmp_path: Path, export_engine: ExcelExportEngine):
    """Verify progress callback is called with running total row counts."""
    file_path = tmp_path / "progress_report.xlsx"
    chunks = [
        [(1, "A"), (2, "B")],
        [(3, "C"), (4, "D")],
        [(5, "E")],
    ]

    progress_counts = []

    def on_progress(count: int):
        progress_counts.append(count)

    metadata = ExportMetadata(report_name="Progress Test")
    result = export_engine.generate_export_from_chunks(
        file_path,
        ["ID", "Val"],
        chunks,
        metadata,
        progress_callback=on_progress,
    )

    assert result.total_rows == 5
    assert progress_counts == [2, 4, 5]

