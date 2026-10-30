import json

from datapulse.database import (
    deterministic_id,
    get_connection,
    initialize_database,
    seed_datasets,
)


def setup_database(tmp_path):
    """Create an isolated temporary Phase 2 database."""
    db_path = tmp_path / "test_datapulse.db"

    initialize_database(db_path)
    seed_datasets(db_path)

    return db_path


def test_all_seven_tables_exist(tmp_path):
    db_path = setup_database(tmp_path)

    expected_tables = {
        "datasets",
        "pipeline_runs",
        "load_events",
        "customer_target",
        "orders_target",
        "quarantine_records",
        "alerts",
    }

    with get_connection(db_path) as connection:
        actual_tables = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

    assert expected_tables.issubset(actual_tables)


def test_sample_dataset_configurations(tmp_path):
    db_path = setup_database(tmp_path)

    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT dataset_id, dataset_name, expected_arrival_time
            FROM datasets
            ORDER BY expected_arrival_time
            """
        ).fetchall()

    assert len(rows) == 4
    assert [row["dataset_name"] for row in rows] == [
        "customers",
        "products",
        "orders",
        "payments",
    ]


def test_seeding_is_idempotent(tmp_path):
    db_path = setup_database(tmp_path)

    # Run the seed process a second time.
    seed_datasets(db_path)

    with get_connection(db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM datasets"
        ).fetchone()[0]

    assert count == 4


def test_deterministic_ids_are_stable():
    first = deterministic_id(
        "run",
        "dataset_customers",
        "customers_2026-10-30.csv",
        "1",
    )

    second = deterministic_id(
        "run",
        "dataset_customers",
        "customers_2026-10-30.csv",
        "1",
    )

    different_attempt = deterministic_id(
        "run",
        "dataset_customers",
        "customers_2026-10-30.csv",
        "2",
    )

    assert first == second
    assert first != different_attempt


def test_all_tables_accept_related_records(tmp_path):
    db_path = setup_database(tmp_path)

    run_id = deterministic_id(
        "run",
        "dataset_customers",
        "customers_2026-10-30.csv",
        "1",
    )

    event_id = deterministic_id(
        "event",
        "dataset_customers",
        "customers_2026-10-30.csv",
        "1",
    )

    customer_id = "customer_001"
    order_id = "order_001"

    with get_connection(db_path) as connection:
        # pipeline_runs
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
                "customers_2026-10-30.csv",
                "2026-10-30T00:30:00+00:00",
                "RUNNING",
            ),
        )

        # load_events
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
                event_id,
                "dataset_customers",
                run_id,
                "customers_2026-10-30.csv",
                1,
                "2026-10-30T00:30:00+00:00",
                "2026-10-30T00:35:00+00:00",
                "ARRIVED",
                "2026-10-30T00:35:00+00:00",
            ),
        )

        # customer_target
        connection.execute(
            """
            INSERT INTO customer_target (
                customer_id, customer_name, email,
                source_event_id, run_id, source_file, loaded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                "Test Customer",
                "test@example.com",
                event_id,
                run_id,
                "customers_2026-10-30.csv",
                "2026-10-30T00:40:00+00:00",
            ),
        )

        # orders_target
        connection.execute(
            """
            INSERT INTO orders_target (
                order_id, customer_id, order_date,
                amount, order_status,
                source_event_id, run_id, source_file, loaded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                customer_id,
                "2026-10-30",
                1250.50,
                "COMPLETED",
                event_id,
                run_id,
                "orders_2026-10-30.csv",
                "2026-10-30T00:45:00+00:00",
            ),
        )

        # quarantine_records
        connection.execute(
            """
            INSERT INTO quarantine_records (
                quarantine_id, dataset_id, load_event_id,
                run_id, source_file, row_number,
                record_key, raw_record_json,
                rejection_reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "quarantine_test_001",
                "dataset_customers",
                event_id,
                run_id,
                "customers_2026-10-30.csv",
                2,
                "customer_002",
                json.dumps({"customer_id": None}),
                "customer_id is required",
                "2026-10-30T00:41:00+00:00",
            ),
        )

        # alerts
        connection.execute(
            """
            INSERT INTO alerts (
                alert_id, dataset_id, load_event_id,
                run_id, alert_type, severity,
                message, status, detected_at, fingerprint
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "alert_test_001",
                "dataset_customers",
                event_id,
                run_id,
                "LATE_ARRIVAL",
                "MEDIUM",
                "Customer file arrived after its expected time.",
                "OPEN",
                "2026-10-30T00:36:00+00:00",
                "customers-late-2026-10-30",
            ),
        )

        # Update the run after its simulated processing.
        connection.execute(
            """
            UPDATE pipeline_runs
            SET completed_at = ?,
                status = ?,
                records_received = ?,
                records_loaded = ?,
                records_rejected = ?
            WHERE run_id = ?
            """,
            (
                "2026-10-30T00:45:00+00:00",
                "PARTIAL",
                2,
                1,
                1,
                run_id,
            ),
        )

        # Update the load event with its completion details.
        connection.execute(
            """
            UPDATE load_events
            SET completion_at = ?,
                status = ?,
                rows_received = ?,
                rows_loaded = ?,
                rows_rejected = ?
            WHERE load_event_id = ?
            """,
            (
                "2026-10-30T00:45:00+00:00",
                "SUCCESS",
                2,
                1,
                1,
                event_id,
            ),
        )

    # Verify that every table has the expected record.
    expected_counts = {
        "datasets": 4,
        "pipeline_runs": 1,
        "load_events": 1,
        "customer_target": 1,
        "orders_target": 1,
        "quarantine_records": 1,
        "alerts": 1,
    }

    with get_connection(db_path) as connection:
        for table_name, expected_count in expected_counts.items():
            actual_count = connection.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]

            assert actual_count == expected_count


def test_foreign_key_prevents_invalid_order_customer(tmp_path):
    db_path = setup_database(tmp_path)

    with get_connection(db_path) as connection:
        try:
            connection.execute(
                """
                INSERT INTO orders_target (
                    order_id, customer_id, order_date,
                    amount, order_status,
                    source_event_id, run_id, source_file, loaded_at
                )
                VALUES (
                    'order_bad', 'unknown_customer', '2026-10-30',
                    100, 'COMPLETED',
                    'unknown_event', 'unknown_run',
                    'orders.csv', '2026-10-30T00:00:00+00:00'
                )
                """
            )
        except Exception as exc:
            assert "FOREIGN KEY constraint failed" in str(exc)
        else:
            raise AssertionError(
                "Invalid foreign-key references were accepted."
            )


def test_duplicate_load_attempt_is_rejected(tmp_path):
    db_path = setup_database(tmp_path)

    run_id = "run_duplicate_test"
    event_id = "event_duplicate_test"

    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO pipeline_runs (
                run_id, dataset_id, source_file, started_at, status
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

        values = (
            event_id,
            "dataset_customers",
            run_id,
            "customers.csv",
            1,
            "2026-10-30T00:00:00+00:00",
            "EXPECTED",
            "2026-10-30T00:00:00+00:00",
        )

        connection.execute(
            """
            INSERT INTO load_events (
                load_event_id, dataset_id, run_id,
                source_file, attempt_number,
                expected_arrival_at, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )

        try:
            connection.execute(
                """
                INSERT INTO load_events (
                    load_event_id, dataset_id, run_id,
                    source_file, attempt_number,
                    expected_arrival_at, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "another_event",
                    "dataset_customers",
                    run_id,
                    "customers.csv",
                    1,
                    "2026-10-30T00:00:00+00:00",
                    "EXPECTED",
                    "2026-10-30T00:00:00+00:00",
                ),
            )
        except Exception as exc:
            assert "UNIQUE constraint failed" in str(exc)
        else:
            raise AssertionError(
                "Duplicate attempt number was accepted."
            )