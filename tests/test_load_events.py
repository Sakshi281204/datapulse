"""Tests for DataPulse load-event registration."""

from contextlib import closing

import pytest

from datapulse.database import (
    get_connection,
    initialize_database,
    seed_datasets,
)
from datapulse.ingestion import ingest_file
from datapulse.load_events import register_load_event


@pytest.fixture
def database_path(tmp_path):
    """Create an isolated database with registered datasets."""
    db_path = tmp_path / "test_datapulse.db"

    initialize_database(db_path)
    seed_datasets(db_path)

    return db_path


def create_pipeline_run(database_path, tmp_path, filename):
    """Create a real pipeline run using the existing ingestion module."""
    csv_file = tmp_path / filename
    csv_file.write_text(
        "customer_id,name\nC001,Alice\n",
        encoding="utf-8",
    )

    return ingest_file("customers", csv_file, database_path)


def register_event(database_path, result):
    """Register a load event for an existing pipeline run."""
    with closing(get_connection(database_path)) as connection:
        event = register_load_event(
            connection=connection,
            dataset_name="customers",
            run_id=result.run_id,
            source_file=result.source_file,
            expected_arrival_at="2026-10-30T06:00:00+05:30",
            actual_arrival_at="2026-10-30T06:05:00+05:30",
        )
        connection.commit()

    return event


def test_first_load_attempt_gets_attempt_number_one(
    database_path, tmp_path
):
    result = create_pipeline_run(
        database_path, tmp_path, "customers.csv"
    )

    event = register_event(database_path, result)

    assert event["attempt_number"] == 1
    assert event["dataset_id"] == "dataset_customers"
    assert event["run_id"] == result.run_id
    assert event["status"] == "ARRIVED"

    with closing(get_connection(database_path)) as connection:
        record = connection.execute(
            """
            SELECT * FROM load_events
            WHERE load_event_id = ?
            """,
            (event["load_event_id"],),
        ).fetchone()

    assert record is not None
    assert record["attempt_number"] == 1
    assert record["expected_arrival_at"] == (
        "2026-10-30T06:00:00+05:30"
    )


def test_retry_gets_attempt_number_two(database_path, tmp_path):
    first_run = create_pipeline_run(
        database_path, tmp_path, "customers.csv"
    )
    second_run = create_pipeline_run(
        database_path, tmp_path, "customers.csv"
    )

    first_event = register_event(database_path, first_run)
    second_event = register_event(database_path, second_run)

    assert first_event["attempt_number"] == 1
    assert second_event["attempt_number"] == 2
    assert first_event["load_event_id"] != second_event["load_event_id"]


def test_different_source_file_starts_new_attempt_history(
    database_path, tmp_path
):
    first_run = create_pipeline_run(
        database_path, tmp_path, "customers_day1.csv"
    )
    second_run = create_pipeline_run(
        database_path, tmp_path, "customers_day2.csv"
    )

    first_event = register_event(database_path, first_run)
    second_event = register_event(database_path, second_run)

    assert first_event["attempt_number"] == 1
    assert second_event["attempt_number"] == 1


def test_unknown_dataset_is_rejected(database_path, tmp_path):
    result = create_pipeline_run(
        database_path, tmp_path, "customers.csv"
    )

    with closing(get_connection(database_path)) as connection:
        with pytest.raises(ValueError, match="Unknown dataset"):
            register_load_event(
                connection=connection,
                dataset_name="unknown_dataset",
                run_id=result.run_id,
                source_file=result.source_file,
                expected_arrival_at="2026-10-30T06:00:00+05:30",
                actual_arrival_at="2026-10-30T06:05:00+05:30",
            )


def test_invalid_run_id_is_rejected(database_path, tmp_path):
    with closing(get_connection(database_path)) as connection:
        with pytest.raises(ValueError, match="Pipeline run"):
            register_load_event(
                connection=connection,
                dataset_name="customers",
                run_id="invalid_run_id",
                source_file="customers.csv",
                expected_arrival_at="2026-10-30T06:00:00+05:30",
                actual_arrival_at="2026-10-30T06:05:00+05:30",
            )


def test_previous_load_events_are_preserved(database_path, tmp_path):
    first_run = create_pipeline_run(
        database_path, tmp_path, "customers.csv"
    )
    second_run = create_pipeline_run(
        database_path, tmp_path, "customers.csv"
    )

    first_event = register_event(database_path, first_run)
    second_event = register_event(database_path, second_run)

    with closing(get_connection(database_path)) as connection:
        records = connection.execute(
            """
            SELECT load_event_id, attempt_number
            FROM load_events
            WHERE dataset_id = ?
              AND source_file = ?
            ORDER BY attempt_number
            """,
            ("dataset_customers", first_run.source_file),
        ).fetchall()

    assert len(records) == 2
    assert records[0]["load_event_id"] == first_event["load_event_id"]
    assert records[1]["load_event_id"] == second_event["load_event_id"]
    assert [record["attempt_number"] for record in records] == [1, 2]