
"""Tests for DataPulse target publishing."""

import sqlite3
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
from datapulse.publishing import publish_customers, publish_orders


@pytest.fixture
def database_path(tmp_path):
    """Create an isolated database with registered datasets."""
    db_path = tmp_path / "test_datapulse.db"
    initialize_database(db_path)
    seed_datasets(db_path)
    return db_path


def create_run_and_event(database_path, tmp_path, dataset_name):
    """Create a pipeline run and register its load event."""
    if dataset_name == "customers":
        filename = "customers.csv"
        content = "customer_id,name\nC001,Alice\n"
    else:
        filename = "orders.csv"
        content = "order_id,customer_id,amount\nO001,C001,500\n"

    csv_file = tmp_path / filename
    csv_file.write_text(content, encoding="utf-8")

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

    return result, event


def publish_one_customer(database_path, tmp_path):
    """Publish one customer for use by order tests."""
    result, event = create_run_and_event(
        database_path, tmp_path, "customers"
    )

    records = pd.DataFrame([
        {
            "customer_id": "C001",
            "customer_name": "Alice",
            "email": "alice@example.com",
        }
    ])

    with closing(get_connection(database_path)) as connection:
        outcome = publish_customers(connection, records, event)
        connection.commit()

    return result, event, outcome


def test_customer_is_published_with_traceability(
    database_path, tmp_path
):
    result, event = create_run_and_event(
        database_path, tmp_path, "customers"
    )

    records = pd.DataFrame([
        {
            "customer_id": "C001",
            "customer_name": "Alice",
            "email": "alice@example.com",
        }
    ])

    with closing(get_connection(database_path)) as connection:
        outcome = publish_customers(connection, records, event)
        connection.commit()

        saved = connection.execute(
            "SELECT * FROM customer_target WHERE customer_id = ?",
            ("C001",),
        ).fetchone()

    assert outcome["input_count"] == 1
    assert outcome["inserted_count"] == 1
    assert outcome["skipped_count"] == 0

    assert saved["customer_name"] == "Alice"
    assert saved["email"] == "alice@example.com"
    assert saved["source_event_id"] == event["load_event_id"]
    assert saved["run_id"] == result.run_id
    assert saved["source_file"] == result.source_file


def test_duplicate_customer_is_skipped_without_overwriting(
    database_path, tmp_path
):
    _, first_event, _ = publish_one_customer(database_path, tmp_path)

    _, second_event = create_run_and_event(
        database_path, tmp_path, "customers"
    )

    records = pd.DataFrame([
        {
            "customer_id": "C001",
            "customer_name": "Changed Name",
            "email": "changed@example.com",
        }
    ])

    with closing(get_connection(database_path)) as connection:
        outcome = publish_customers(connection, records, second_event)
        connection.commit()

        saved = connection.execute(
            "SELECT * FROM customer_target WHERE customer_id = ?",
            ("C001",),
        ).fetchone()

    assert outcome["inserted_count"] == 0
    assert outcome["skipped_count"] == 1
    assert saved["customer_name"] == "Alice"
    assert saved["source_event_id"] == first_event["load_event_id"]


def test_order_is_published_with_traceability(
    database_path, tmp_path
):
    publish_one_customer(database_path, tmp_path)

    result, event = create_run_and_event(
        database_path, tmp_path, "orders"
    )

    records = pd.DataFrame([
        {
            "order_id": "O001",
            "customer_id": "C001",
            "order_date": "2026-10-30",
            "amount": 500.0,
            "order_status": "COMPLETED",
        }
    ])

    with closing(get_connection(database_path)) as connection:
        outcome = publish_orders(connection, records, event)
        connection.commit()

        saved = connection.execute(
            "SELECT * FROM orders_target WHERE order_id = ?",
            ("O001",),
        ).fetchone()

    assert outcome["input_count"] == 1
    assert outcome["inserted_count"] == 1
    assert outcome["skipped_count"] == 0

    assert saved["customer_id"] == "C001"
    assert saved["amount"] == 500.0
    assert saved["source_event_id"] == event["load_event_id"]
    assert saved["run_id"] == result.run_id


def test_duplicate_order_is_skipped(
    database_path, tmp_path
):
    publish_one_customer(database_path, tmp_path)

    _, first_event = create_run_and_event(
        database_path, tmp_path, "orders"
    )

    records = pd.DataFrame([
        {
            "order_id": "O001",
            "customer_id": "C001",
            "order_date": "2026-10-30",
            "amount": 500.0,
            "order_status": "COMPLETED",
        }
    ])

    with closing(get_connection(database_path)) as connection:
        first = publish_orders(connection, records, first_event)
        connection.commit()

    _, second_event = create_run_and_event(
        database_path, tmp_path, "orders"
    )

    with closing(get_connection(database_path)) as connection:
        second = publish_orders(connection, records, second_event)
        connection.commit()

        saved = connection.execute(
            "SELECT * FROM orders_target WHERE order_id = ?",
            ("O001",),
        ).fetchone()

    assert first["inserted_count"] == 1
    assert second["inserted_count"] == 0
    assert second["skipped_count"] == 1
    assert saved["source_event_id"] == first_event["load_event_id"]


def test_order_with_unknown_customer_fails(
    database_path, tmp_path
):
    _, event = create_run_and_event(
        database_path, tmp_path, "orders"
    )

    records = pd.DataFrame([
        {
            "order_id": "O001",
            "customer_id": "UNKNOWN",
            "order_date": "2026-10-30",
            "amount": 500.0,
            "order_status": "COMPLETED",
        }
    ])

    with closing(get_connection(database_path)) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            publish_orders(connection, records, event)

        connection.rollback()


def test_empty_customer_batch_is_handled(
    database_path, tmp_path
):
    _, event = create_run_and_event(
        database_path, tmp_path, "customers"
    )

    records = pd.DataFrame(
        columns=["customer_id", "customer_name", "email"]
    )

    with closing(get_connection(database_path)) as connection:
        outcome = publish_customers(connection, records, event)

    assert outcome["input_count"] == 0
    assert outcome["inserted_count"] == 0
    assert outcome["skipped_count"] == 0


def test_wrong_dataset_load_event_is_rejected(
    database_path, tmp_path
):
    _, orders_event = create_run_and_event(
        database_path, tmp_path, "orders"
    )

    records = pd.DataFrame([
        {
            "customer_id": "C001",
            "customer_name": "Alice",
            "email": "alice@example.com",
        }
    ])

    with closing(get_connection(database_path)) as connection:
        with pytest.raises(ValueError):
            publish_customers(connection, records, orders_event)


def test_missing_required_columns_are_rejected(
    database_path, tmp_path
):
    _, event = create_run_and_event(
        database_path, tmp_path, "customers"
    )

    records = pd.DataFrame([
        {"customer_id": "C001"}
    ])

    with closing(get_connection(database_path)) as connection:
        with pytest.raises(ValueError, match="Missing required columns"):
            publish_customers(connection, records, event)
