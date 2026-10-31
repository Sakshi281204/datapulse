
"""Tests for DataPulse SLA monitoring foundations."""

import sqlite3
import pytest
from datetime import datetime, timedelta, timezone
from datapulse.sla_monitor import parse_timestamp

from datapulse.sla_monitor import (
    check_late_arrival,
    check_completion_sla,
    check_freshness,
    check_missing_load,
    run_sla_checks
)


def test_parse_timestamp_normalizes_to_utc():
    timestamp = parse_timestamp(
        "2026-10-30T06:00:00+05:30"
    )

    assert timestamp.isoformat() == "2026-10-30T00:30:00+00:00"


def test_parse_timestamp_rejects_missing_timezone():
    with pytest.raises(ValueError, match="timezone"):
        parse_timestamp("2026-10-30T06:00:00")

from datapulse.database import (
    get_connection,
    initialize_database,
    seed_datasets,
)
from datapulse.sla_monitor import create_alert


def test_create_alert_prevents_duplicates(tmp_path):
    database_path = tmp_path / "test_sla.db"

    initialize_database(database_path)
    seed_datasets(database_path)

    with get_connection(database_path) as connection:
        first = create_alert(
            connection=connection,
            dataset_id="dataset_customers",
            alert_type="LATE_ARRIVAL",
            severity="HIGH",
            message="Customers dataset arrived late.",
            fingerprint="customers|LATE_ARRIVAL|2026-10-30",
            detected_at="2026-10-30T07:00:00+00:00",
        )

        second = create_alert(
            connection=connection,
            dataset_id="dataset_customers",
            alert_type="LATE_ARRIVAL",
            severity="HIGH",
            message="Customers dataset arrived late.",
            fingerprint="customers|LATE_ARRIVAL|2026-10-30",
            detected_at="2026-10-30T07:05:00+00:00",
        )

        alert_count = connection.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]

    assert first["created"] is True
    assert second["created"] is False
    assert first["alert_id"] == second["alert_id"]
    assert alert_count == 1


def check_late_arrival(
    connection: sqlite3.Connection,
    load_event_id: str,
) -> dict:
    """Check whether a load event arrived after its allowed grace period."""

    event = connection.execute(
        """
        SELECT
            le.load_event_id,
            le.dataset_id,
            le.run_id,
            le.expected_arrival_at,
            le.actual_arrival_at,
            d.dataset_name,
            d.arrival_grace_minutes
        FROM load_events le
        JOIN datasets d
            ON d.dataset_id = le.dataset_id
        WHERE le.load_event_id = ?
        """,
        (load_event_id,),
    ).fetchone()

    if event is None:
        raise ValueError(f"Load event not found: {load_event_id}")

    if not event["actual_arrival_at"]:
        return {
            "late": False,
            "reason": "Actual arrival time is not available.",
            "alert_created": False,
        }

    expected = parse_timestamp(event["expected_arrival_at"])
    actual = parse_timestamp(event["actual_arrival_at"])

    deadline = expected + timedelta(
        minutes=event["arrival_grace_minutes"]
    )

    if actual <= deadline:
        return {
            "late": False,
            "reason": "Load arrived within the allowed grace period.",
            "alert_created": False,
        }

    delay_minutes = round(
        (actual - deadline).total_seconds() / 60,
        2,
    )

    fingerprint = (
        f"{event['dataset_name']}|LATE_ARRIVAL|"
        f"{event['expected_arrival_at']}"
    )

    alert = create_alert(
        connection=connection,
        dataset_id=event["dataset_id"],
        load_event_id=event["load_event_id"],
        run_id=event["run_id"],
        alert_type="LATE_ARRIVAL",
        severity="HIGH",
        message=(
            f"{event['dataset_name']} arrived "
            f"{delay_minutes} minutes after its SLA deadline."
        ),
        fingerprint=fingerprint,
    )

    connection.execute(
        """
        UPDATE load_events
        SET status = 'LATE'
        WHERE load_event_id = ?
        """,
        (load_event_id,),
    )

    return {
        "late": True,
        "delay_minutes": delay_minutes,
        "alert_created": alert["created"],
        "alert_id": alert["alert_id"],
    }
def create_test_load_event(
    connection,
    actual_arrival_at,
    expected_arrival_at="2026-10-30T06:00:00+05:30",
):
    """Insert a test pipeline run and its load event."""

    run_id = "test_run_001"
    load_event_id = "test_load_001"

    connection.execute(
        """
        INSERT INTO pipeline_runs (
            run_id, dataset_id, source_file,
            started_at, status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            run_id,
            "dataset_customers",
            "customers.csv",
            "2026-10-30T00:00:00+00:00",
            "RUNNING",
        ),
    )

    connection.execute(
        """
        INSERT INTO load_events (
            load_event_id, dataset_id, run_id,
            source_file, attempt_number,
            expected_arrival_at, actual_arrival_at,
            status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            load_event_id,
            "dataset_customers",
            run_id,
            "customers.csv",
            1,
            expected_arrival_at,
            actual_arrival_at,
            "ARRIVED",
            "2026-10-30T00:00:00+00:00",
        ),
    )

    return load_event_id

def test_late_arrival_creates_alert(tmp_path):
    database_path = tmp_path / "late_arrival.db"

    initialize_database(database_path)
    seed_datasets(database_path)

    with get_connection(database_path) as connection:
        load_event_id = create_test_load_event(
            connection,
            actual_arrival_at="2026-10-30T06:20:00+05:30",
        )

        result = check_late_arrival(
            connection,
            load_event_id,
        )

        alert_count = connection.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]

        event_status = connection.execute(
            "SELECT status FROM load_events WHERE load_event_id = ?",
            (load_event_id,),
        ).fetchone()["status"]

    assert result["late"] is True
    assert result["delay_minutes"] == 5
    assert result["alert_created"] is True
    assert alert_count == 1
    assert event_status == "LATE"


def test_on_time_arrival_does_not_create_alert(tmp_path):
    database_path = tmp_path / "on_time.db"

    initialize_database(database_path)
    seed_datasets(database_path)

    with get_connection(database_path) as connection:
        load_event_id = create_test_load_event(
            connection,
            actual_arrival_at="2026-10-30T06:10:00+05:30",
        )

        result = check_late_arrival(
            connection,
            load_event_id,
        )

        alert_count = connection.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]

    assert result["late"] is False
    assert result["alert_created"] is False
    assert alert_count == 0

def check_late_arrival(
    connection: sqlite3.Connection,
    load_event_id: str,
) -> dict:
    """Check whether a load event arrived after its allowed grace period."""

    event = connection.execute(
        """
        SELECT
            le.load_event_id,
            le.dataset_id,
            le.run_id,
            le.expected_arrival_at,
            le.actual_arrival_at,
            d.dataset_name,
            d.arrival_grace_minutes
        FROM load_events le
        JOIN datasets d
            ON d.dataset_id = le.dataset_id
        WHERE le.load_event_id = ?
        """,
        (load_event_id,),
    ).fetchone()

    if event is None:
        raise ValueError(f"Load event not found: {load_event_id}")

    if not event["actual_arrival_at"]:
        return {
            "late": False,
            "reason": "Actual arrival time is not available.",
            "alert_created": False,
        }

    expected = parse_timestamp(event["expected_arrival_at"])
    actual = parse_timestamp(event["actual_arrival_at"])

    deadline = expected + timedelta(
        minutes=event["arrival_grace_minutes"]
    )

    if actual <= deadline:
        return {
            "late": False,
            "reason": "Load arrived within the allowed grace period.",
            "alert_created": False,
        }

    delay_minutes = round(
        (actual - deadline).total_seconds() / 60,
        2,
    )

    fingerprint = (
        f"{event['dataset_name']}|LATE_ARRIVAL|"
        f"{event['expected_arrival_at']}"
    )

    alert = create_alert(
        connection=connection,
        dataset_id=event["dataset_id"],
        load_event_id=event["load_event_id"],
        run_id=event["run_id"],
        alert_type="LATE_ARRIVAL",
        severity="HIGH",
        message=(
            f"{event['dataset_name']} arrived "
            f"{delay_minutes} minutes after its SLA deadline."
        ),
        fingerprint=fingerprint,
    )

    connection.execute(
        """
        UPDATE load_events
        SET status = 'LATE'
        WHERE load_event_id = ?
        """,
        (load_event_id,),
    )

    return {
        "late": True,
        "delay_minutes": delay_minutes,
        "alert_created": alert["created"],
        "alert_id": alert["alert_id"],
    }

def test_completion_sla_creates_alert(tmp_path):
    database_path = tmp_path / "completion_breach.db"

    initialize_database(database_path)
    seed_datasets(database_path)

    with get_connection(database_path) as connection:
        load_event_id = create_test_load_event(
            connection,
            actual_arrival_at="2026-10-30T06:00:00+05:30",
        )

        connection.execute(
            """
            UPDATE load_events
            SET completion_at = ?
            WHERE load_event_id = ?
            """,
            (
                "2026-10-30T06:40:00+05:30",
                load_event_id,
            ),
        )

        result = check_completion_sla(
            connection,
            load_event_id,
        )

        alert_count = connection.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]

    assert result["breached"] is True
    assert result["duration_minutes"] == 40
    assert result["breach_minutes"] == 10
    assert result["alert_created"] is True
    assert alert_count == 1


def test_completion_within_sla_does_not_create_alert(tmp_path):
    database_path = tmp_path / "completion_on_time.db"

    initialize_database(database_path)
    seed_datasets(database_path)

    with get_connection(database_path) as connection:
        load_event_id = create_test_load_event(
            connection,
            actual_arrival_at="2026-10-30T06:00:00+05:30",
        )

        connection.execute(
            """
            UPDATE load_events
            SET completion_at = ?
            WHERE load_event_id = ?
            """,
            (
                "2026-10-30T06:20:00+05:30",
                load_event_id,
            ),
        )

        result = check_completion_sla(
            connection,
            load_event_id,
        )

        alert_count = connection.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]

    assert result["breached"] is False
    assert result["duration_minutes"] == 20
    assert result["alert_created"] is False
    assert alert_count == 0


def test_stale_dataset_creates_freshness_alert(tmp_path):
    database_path = tmp_path / "stale_dataset.db"

    initialize_database(database_path)
    seed_datasets(database_path)

    with get_connection(database_path) as connection:
        load_event_id = create_test_load_event(
            connection,
            actual_arrival_at="2026-10-29T06:00:00+05:30",
            expected_arrival_at="2026-10-29T06:00:00+05:30",
        )

        connection.execute(
            """
            UPDATE load_events
            SET completion_at = ?,
                rows_loaded = 10,
                status = 'SUCCESS'
            WHERE load_event_id = ?
            """,
            (
                "2026-10-29T06:00:00+05:30",
                load_event_id,
            ),
        )

        result = check_freshness(
            connection,
            "dataset_customers",
            now="2026-10-30T07:00:00+05:30",
        )

        alert_count = connection.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]

    assert result["stale"] is True
    assert result["age_minutes"] == 1500
    assert result["stale_minutes"] == 60
    assert result["alert_created"] is True
    assert alert_count == 1


def test_fresh_dataset_does_not_create_alert(tmp_path):
    database_path = tmp_path / "fresh_dataset.db"

    initialize_database(database_path)
    seed_datasets(database_path)

    with get_connection(database_path) as connection:
        load_event_id = create_test_load_event(
            connection,
            actual_arrival_at="2026-10-30T06:00:00+05:30",
        )

        connection.execute(
            """
            UPDATE load_events
            SET completion_at = ?,
                rows_loaded = 10,
                status = 'SUCCESS'
            WHERE load_event_id = ?
            """,
            (
                "2026-10-30T06:00:00+05:30",
                load_event_id,
            ),
        )

        result = check_freshness(
            connection,
            "dataset_customers",
            now="2026-10-30T07:00:00+05:30",
        )

        alert_count = connection.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]

    assert result["stale"] is False
    assert result["age_minutes"] == 60
    assert result["alert_created"] is False
    assert alert_count == 0


def test_missing_load_creates_alert(tmp_path):
    database_path = tmp_path / "missing_load.db"

    initialize_database(database_path)
    seed_datasets(database_path)

    with get_connection(database_path) as connection:
        result = check_missing_load(
            connection,
            "dataset_customers",
            now="2026-10-30T06:16:00+05:30",
        )

        alert_count = connection.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]

    assert result["missing"] is True
    assert result["alert_created"] is True
    assert alert_count == 1


def test_missing_load_before_deadline_does_not_alert(tmp_path):
    database_path = tmp_path / "before_deadline.db"

    initialize_database(database_path)
    seed_datasets(database_path)

    with get_connection(database_path) as connection:
        result = check_missing_load(
            connection,
            "dataset_customers",
            now="2026-10-30T06:10:00+05:30",
        )

        alert_count = connection.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]

    assert result["missing"] is False
    assert result["alert_created"] is False
    assert alert_count == 0


def test_load_event_without_actual_arrival_is_still_missing(tmp_path):
    database_path = tmp_path / "unarrived_event.db"

    initialize_database(database_path)
    seed_datasets(database_path)

    with get_connection(database_path) as connection:
        create_test_load_event(
            connection,
            actual_arrival_at=None,
        )

        result = check_missing_load(
            connection,
            "dataset_customers",
            now="2026-10-30T06:16:00+05:30",
        )

    assert result["missing"] is True
    assert result["alert_created"] is True


def test_run_sla_checks_monitors_all_active_datasets(tmp_path):
    database_path = tmp_path / "sla_coordinator.db"

    initialize_database(database_path)
    seed_datasets(database_path)

    fixed_now = "2026-10-30T08:00:00+05:30"

    with get_connection(database_path) as connection:
        first_result = run_sla_checks(
            connection,
            now=fixed_now,
        )

        first_alert_count = connection.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]

        second_result = run_sla_checks(
            connection,
            now=fixed_now,
        )

        second_alert_count = connection.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]

    assert first_result["datasets_checked"] == 4
    assert first_result["load_events_checked"] == 0

    assert all(
        dataset["missing_load"]["missing"] is True
        for dataset in first_result["datasets"]
    )

    assert first_result["alerts_created"] == 4
    assert second_result["alerts_created"] == 0
    assert first_alert_count == 4
    assert second_alert_count == 4



def test_freshness_uses_latest_completion_when_older_load_is_inserted_later(
    tmp_path,
):
    """An older load inserted later must not replace the latest completion."""

    database_path = tmp_path / "out_of_order_freshness.db"

    initialize_database(database_path)
    seed_datasets(database_path)

    with get_connection(database_path) as connection:
        newer_load_id = create_test_load_event(
            connection,
            actual_arrival_at="2026-10-31T06:00:00+05:30",
        )

        connection.execute(
            """
            UPDATE load_events
            SET completion_at = ?,
                rows_loaded = 10,
                status = 'SUCCESS'
            WHERE load_event_id = ?
            """,
            ("2026-10-31T06:30:00+05:30", newer_load_id),
        )

        connection.execute(
            """
            INSERT INTO pipeline_runs (
                run_id, dataset_id, source_file, started_at, status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "test_run_older",
                "dataset_customers",
                "customers_older.csv",
                "2026-10-31T06:05:00+05:30",
                "SUCCESS",
            ),
        )

        connection.execute(
            """
            INSERT INTO load_events (
                load_event_id, dataset_id, run_id,
                source_file, attempt_number,
                expected_arrival_at, actual_arrival_at,
                completion_at, status, rows_loaded, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "test_load_older",
                "dataset_customers",
                "test_run_older",
                "customers_older.csv",
                1,
                "2026-10-31T06:00:00+05:30",
                "2026-10-31T06:05:00+05:30",
                "2026-10-31T06:10:00+05:30",
                "SUCCESS",
                5,
                "2026-10-31T06:05:00+05:30",
            ),
        )

        result = check_freshness(
            connection,
            "dataset_customers",
            now="2026-10-31T07:00:00+05:30",
        )

    assert result["stale"] is False
    assert result["age_minutes"] == 30
    assert result["alert_created"] is False
