
"""Tests for DataPulse CSV ingestion."""

import pandas as pd
import pytest
from contextlib import closing

from datapulse.database import (
    get_connection,
    initialize_database,
    seed_datasets,
)
from datapulse.ingestion import ingest_file


@pytest.fixture
def database_path(tmp_path):
    """Create an isolated database with registered datasets."""
    db_path = tmp_path / "test_datapulse.db"

    initialize_database(db_path)
    seed_datasets(db_path)

    return db_path


def get_run_record(database_path, run_id):
    """Retrieve one pipeline run from the database."""
    with closing(get_connection(database_path)) as connection:
        row = connection.execute(
            "SELECT * FROM pipeline_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()

    return dict(row) if row else None


def test_successful_csv_ingestion(database_path, tmp_path):
    """A valid CSV should be read and recorded as SUCCESS."""
    csv_file = tmp_path / "customers.csv"
    csv_file.write_text(
        "customer_id,name\nC001,Alice\nC002,Bob\n",
        encoding="utf-8",
    )

    result = ingest_file("customers", csv_file, database_path)

    assert result.status == "SUCCESS"
    assert result.input_row_count == 2
    assert result.data is not None
    assert isinstance(result.data, pd.DataFrame)
    assert result.columns == ["customer_id", "name"]
    assert result.error_message is None

    record = get_run_record(database_path, result.run_id)

    assert record["status"] == "SUCCESS"
    assert record["records_received"] == 2
    assert record["records_loaded"] == 0
    assert record["completed_at"] is not None
    assert record["error_message"] is None


def test_missing_file_is_recorded_as_failed(database_path, tmp_path):
    """A missing source file should create a FAILED pipeline run."""
    missing_file = tmp_path / "missing.csv"

    result = ingest_file("customers", missing_file, database_path)

    assert result.status == "FAILED"
    assert result.input_row_count == 0
    assert "does not exist" in result.error_message

    record = get_run_record(database_path, result.run_id)

    assert record["status"] == "FAILED"
    assert record["records_received"] == 0
    assert record["completed_at"] is not None
    assert record["error_message"] is not None


def test_empty_file_is_recorded_as_failed(database_path, tmp_path):
    """An empty CSV should create a FAILED pipeline run."""
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("", encoding="utf-8")

    result = ingest_file("customers", empty_file, database_path)

    assert result.status == "FAILED"
    assert "empty" in result.error_message.lower()

    record = get_run_record(database_path, result.run_id)

    assert record["status"] == "FAILED"
    assert record["records_received"] == 0


def test_malformed_csv_is_recorded_as_failed(database_path, tmp_path):
    """A malformed CSV should create a FAILED pipeline run."""
    malformed_file = tmp_path / "malformed.csv"
    malformed_file.write_text(
        'id,name\n1,"Alice',
        encoding="utf-8",
    )

    result = ingest_file("customers", malformed_file, database_path)

    assert result.status == "FAILED"
    assert "Malformed CSV" in result.error_message

    record = get_run_record(database_path, result.run_id)

    assert record["status"] == "FAILED"
    assert record["records_received"] == 0
    assert record["error_message"] is not None


def test_each_attempt_gets_a_unique_run_id(database_path, tmp_path):
    """Repeated ingestion attempts should have different run IDs."""
    csv_file = tmp_path / "customers.csv"
    csv_file.write_text(
        "customer_id,name\nC001,Alice\n",
        encoding="utf-8",
    )

    first_result = ingest_file("customers", csv_file, database_path)
    second_result = ingest_file("customers", csv_file, database_path)

    assert first_result.run_id != second_result.run_id


def test_orders_ingestion(database_path, tmp_path):
    """Orders CSV should use the orders dataset registration."""
    csv_file = tmp_path / "orders.csv"
    csv_file.write_text(
        "order_id,customer_id,amount\nO001,C001,500\n",
        encoding="utf-8",
    )

    result = ingest_file("orders", csv_file, database_path)

    assert result.status == "SUCCESS"
    assert result.dataset_name == "orders"
    assert result.input_row_count == 1

    record = get_run_record(database_path, result.run_id)

    assert record["dataset_id"] == "dataset_orders"
    assert record["status"] == "SUCCESS"


def test_unsupported_dataset_is_rejected(database_path, tmp_path):
    """Only registered ingestion datasets should be accepted."""
    with pytest.raises(ValueError, match="Unsupported dataset"):
        ingest_file("payments", tmp_path / "payments.csv", database_path)
