
"""Tests for DataPulse quarantine storage."""

import json
from contextlib import closing

import pandas as pd
import pytest

from datapulse.database import (
    get_connection,
    initialize_database,
    seed_datasets,
)
from datapulse.ingestion import ingest_file
from datapulse.load_events import register_load_event
from datapulse.quarantine import quarantine_rejected_records


@pytest.fixture
def database_path(tmp_path):
    """Create an isolated database with registered datasets."""
    db_path = tmp_path / "test_datapulse.db"
    initialize_database(db_path)
    seed_datasets(db_path)
    return db_path


def create_event(database_path, tmp_path, dataset_name):
    """Create a pipeline run and register its load event."""
    filename = f"{dataset_name}.csv"
    csv_file = tmp_path / filename

    if dataset_name == "customers":
        csv_file.write_text(
            "customer_id,first_name,last_name,email,city\n"
            "C001,Alice,Smith,alice@example.com,Pune\n",
            encoding="utf-8",
        )
    else:
        csv_file.write_text(
            "order_id,customer_id,total_amount,order_date\n"
            "O001,C001,500,2026-10-30\n",
            encoding="utf-8",
        )

    result = ingest_file(dataset_name, csv_file, database_path)

    with closing(get_connection(database_path)) as connection:
        event = register_load_event(
            connection=connection,
            dataset_name=dataset_name,
            run_id=result.run_id,
            source_file=result.source_file,
            expected_arrival_at="2026-10-30T06:00:00+05:30",
            actual_arrival_at="2026-10-30T06:05:00+05:30",
        )
        connection.commit()

    return event


def test_customer_rejected_record_is_saved(database_path, tmp_path):
    event = create_event(database_path, tmp_path, "customers")

    rejected = pd.DataFrame([
        {
            "customer_id": "C002",
            "first_name": "",
            "last_name": "Jones",
            "email": "invalid-email",
            "city": "Pune",
            "row_number": 3,
            "rejection_reason": "first_name is missing",
        }
    ])

    with closing(get_connection(database_path)) as connection:
        result = quarantine_rejected_records(
            connection, "customers", rejected, event
        )
        connection.commit()

        record = connection.execute(
            """
            SELECT * FROM quarantine_records
            WHERE load_event_id = ?
            """,
            (event["load_event_id"],),
        ).fetchone()

    assert result == {
        "input_count": 1,
        "inserted_count": 1,
        "skipped_count": 0,
    }
    assert record["record_key"] == "C002"
    assert record["row_number"] == 3
    assert record["rejection_reason"] == "first_name is missing"

    raw_data = json.loads(record["raw_record_json"])
    assert raw_data["customer_id"] == "C002"
    assert raw_data["email"] == "invalid-email"
    assert raw_data["city"] == "Pune"


def test_duplicate_quarantine_record_is_not_inserted(
    database_path, tmp_path
):
    event = create_event(database_path, tmp_path, "customers")

    rejected = pd.DataFrame([
        {
            "customer_id": "C002",
            "first_name": "",
            "last_name": "Jones",
            "email": "invalid-email",
            "city": "Pune",
            "row_number": 3,
            "rejection_reason": "first_name is missing",
        }
    ])

    with closing(get_connection(database_path)) as connection:
        first = quarantine_rejected_records(
            connection, "customers", rejected, event
        )
        second = quarantine_rejected_records(
            connection, "customers", rejected, event
        )
        connection.commit()

        count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM quarantine_records
            WHERE load_event_id = ?
            """,
            (event["load_event_id"],),
        ).fetchone()["total"]

    assert first["inserted_count"] == 1
    assert second["inserted_count"] == 0
    assert second["skipped_count"] == 1
    assert count == 1


def test_order_rejected_record_uses_order_id_as_record_key(
    database_path, tmp_path
):
    event = create_event(database_path, tmp_path, "orders")

    rejected = pd.DataFrame([
        {
            "order_id": "O002",
            "customer_id": "C999",
            "total_amount": 500,
            "order_date": "2026-10-30",
            "row_number": 4,
            "rejection_reason": "Invalid customer reference",
        }
    ])

    with closing(get_connection(database_path)) as connection:
        result = quarantine_rejected_records(
            connection, "orders", rejected, event
        )
        connection.commit()

        record = connection.execute(
            """
            SELECT record_key, raw_record_json
            FROM quarantine_records
            WHERE load_event_id = ?
            """,
            (event["load_event_id"],),
        ).fetchone()

    assert result["inserted_count"] == 1
    assert record["record_key"] == "O002"
    assert json.loads(record["raw_record_json"])["customer_id"] == "C999"


def test_empty_rejected_batch_inserts_nothing(database_path, tmp_path):
    event = create_event(database_path, tmp_path, "customers")

    rejected = pd.DataFrame(
        columns=[
            "customer_id",
            "row_number",
            "rejection_reason",
        ]
    )

    with closing(get_connection(database_path)) as connection:
        result = quarantine_rejected_records(
            connection, "customers", rejected, event
        )

    assert result == {
        "input_count": 0,
        "inserted_count": 0,
        "skipped_count": 0,
    }


def test_wrong_dataset_load_event_is_rejected(database_path, tmp_path):
    event = create_event(database_path, tmp_path, "customers")

    rejected = pd.DataFrame([
        {
            "order_id": "O002",
            "row_number": 2,
            "rejection_reason": "Invalid order",
        }
    ])

    with closing(get_connection(database_path)) as connection:
        with pytest.raises(ValueError, match="different dataset"):
            quarantine_rejected_records(
                connection, "orders", rejected, event
            )


def test_missing_required_columns_are_rejected(database_path, tmp_path):
    event = create_event(database_path, tmp_path, "customers")

    rejected = pd.DataFrame([
        {"customer_id": "C002"}
    ])

    with closing(get_connection(database_path)) as connection:
        with pytest.raises(ValueError, match="Missing required columns"):
            quarantine_rejected_records(
                connection, "customers", rejected, event
            )
