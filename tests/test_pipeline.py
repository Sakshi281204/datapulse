
"""Tests for end-to-end DataPulse pipeline orchestration."""

import pytest

from datapulse.database import (
    get_connection,
    initialize_database,
    seed_datasets,
)
from datapulse.pipeline import run_dataset_pipeline


@pytest.fixture
def database_path(tmp_path):
    """Create an isolated operational database."""
    db_path = tmp_path / "test_pipeline.db"
    initialize_database(db_path)
    seed_datasets(db_path)
    return db_path


def write_customers_csv(tmp_path, filename="customers.csv"):
    """Create a valid customer source file."""
    csv_file = tmp_path / filename

    csv_file.write_text(
        (
            "customer_id,first_name,last_name,email,city\n"
            "C001,Alice,Sharma,alice@example.com,Pune\n"
            "C002,Bob,Patil,bob@example.com,Mumbai\n"
        ),
        encoding="utf-8",
    )

    return csv_file


def test_customer_pipeline_success(database_path, tmp_path):
    """Valid customer records should be published successfully."""
    csv_file = write_customers_csv(tmp_path)

    result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=csv_file,
        database_path=database_path,
    )

    assert result["status"] == "SUCCESS"
    assert result["records_received"] == 2
    assert result["records_loaded"] == 2
    assert result["records_rejected"] == 0

    assert result["publishing"]["inserted_count"] == 2
    assert result["quarantine"]["inserted_count"] == 0

    with get_connection(database_path) as connection:
        customer_count = connection.execute(
            "SELECT COUNT(*) FROM customer_target"
        ).fetchone()[0]

        run = connection.execute(
            """
            SELECT status, records_received,
                   records_loaded, records_rejected
            FROM pipeline_runs
            WHERE run_id = ?
            """,
            (result["run_id"],),
        ).fetchone()

    assert customer_count == 2
    assert run["status"] == "SUCCESS"
    assert run["records_received"] == 2
    assert run["records_loaded"] == 2
    assert run["records_rejected"] == 0

def test_customer_pipeline_quarantines_invalid_records(
    database_path, tmp_path
):
    """Invalid customers should be quarantined, not published."""
    csv_file = tmp_path / "customers_with_invalid.csv"

    csv_file.write_text(
        (
            "customer_id,first_name,last_name,email,city\n"
            "C001,Alice,Sharma,alice@example.com,Pune\n"
            "C002,Bob,Patil,invalid-email,Mumbai\n"
            "C003,Neha,Joshi,neha@example.com,Nashik\n"
        ),
        encoding="utf-8",
    )

    result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=csv_file,
        database_path=database_path,
    )

    assert result["status"] == "PARTIAL"
    assert result["records_received"] == 3
    assert result["records_loaded"] == 2
    assert result["records_rejected"] == 1

    assert result["publishing"]["inserted_count"] == 2
    assert result["quarantine"]["inserted_count"] == 1

    with get_connection(database_path) as connection:
        customer_count = connection.execute(
            "SELECT COUNT(*) FROM customer_target"
        ).fetchone()[0]

        quarantine_count = connection.execute(
            "SELECT COUNT(*) FROM quarantine_records"
        ).fetchone()[0]

    assert customer_count == 2
    assert quarantine_count == 1

def test_pipeline_handles_missing_source_file(database_path, tmp_path):
    """Missing source files should result in a FAILED pipeline run."""
    missing_file = tmp_path / "missing_customers.csv"

    result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=missing_file,
        database_path=database_path,
    )

    assert result["status"] == "FAILED"
    assert result["run_id"] is not None
    assert "does not exist" in result["error_message"]

    with get_connection(database_path) as connection:
        run = connection.execute(
            """
            SELECT status, records_received, records_loaded,
                   records_rejected, error_message
            FROM pipeline_runs
            WHERE run_id = ?
            """,
            (result["run_id"],),
        ).fetchone()

        event_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM load_events
            WHERE run_id = ?
            """,
            (result["run_id"],),
        ).fetchone()[0]

    assert run["status"] == "FAILED"
    assert run["records_received"] == 0
    assert run["records_loaded"] == 0
    assert run["records_rejected"] == 0
    assert run["error_message"] is not None
    assert event_count == 0

def test_orders_pipeline_success(database_path, tmp_path):
    """Valid orders should be published for existing customers."""

    customer_file = write_customers_csv(tmp_path)

    customer_result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=customer_file,
        database_path=database_path,
    )

    assert customer_result["status"] == "SUCCESS"

    orders_file = tmp_path / "orders.csv"
    orders_file.write_text(
        (
            "order_id,customer_id,product_id,order_date,"
            "quantity,unit_price,total_amount,status\n"
            "O001,C001,P001,2026-10-30,2,250,500,PLACED\n"
            "O002,C002,P002,2026-10-30,1,300,300,SHIPPED\n"
        ),
        encoding="utf-8",
    )

    result = run_dataset_pipeline(
        dataset_name="orders",
        source_path=orders_file,
        database_path=database_path,
    )

    assert result["status"] == "SUCCESS"
    assert result["records_received"] == 2
    assert result["records_loaded"] == 2
    assert result["records_rejected"] == 0

    with get_connection(database_path) as connection:
        order_count = connection.execute(
            "SELECT COUNT(*) FROM orders_target"
        ).fetchone()[0]

        unmatched_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM orders_target o
            LEFT JOIN customer_target c
                ON o.customer_id = c.customer_id
            WHERE c.customer_id IS NULL
            """
        ).fetchone()[0]

    assert order_count == 2
    assert unmatched_count == 0

def test_pipeline_rolls_back_when_publishing_fails(
    database_path, tmp_path, monkeypatch
):
    """Publishing failures should roll back processing changes."""

    import datapulse.pipeline as pipeline_module

    csv_file = write_customers_csv(tmp_path)

    def simulate_publishing_failure(*args, **kwargs):
        raise RuntimeError("Simulated publishing failure")

    monkeypatch.setattr(
        pipeline_module,
        "publish_customers",
        simulate_publishing_failure,
    )

    result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=csv_file,
        database_path=database_path,
    )

    assert result["status"] == "FAILED"
    assert "Simulated publishing failure" in result["error_message"]

    with get_connection(database_path) as connection:
        run = connection.execute(
            """
            SELECT status, error_message
            FROM pipeline_runs
            WHERE run_id = ?
            """,
            (result["run_id"],),
        ).fetchone()

        event = connection.execute(
            """
            SELECT status, error_message
            FROM load_events
            WHERE load_event_id = ?
            """,
            (result["load_event_id"],),
        ).fetchone()

        customer_count = connection.execute(
            "SELECT COUNT(*) FROM customer_target"
        ).fetchone()[0]

        quarantine_count = connection.execute(
            "SELECT COUNT(*) FROM quarantine_records"
        ).fetchone()[0]

    assert run["status"] == "FAILED"
    assert event["status"] == "FAILED"
    assert "Simulated publishing failure" in run["error_message"]
    assert customer_count == 0
    assert quarantine_count == 0

def test_customer_pipeline_rerun_does_not_duplicate_records(
    database_path, tmp_path
):
    """Rerunning the same file should not duplicate target records."""

    csv_file = write_customers_csv(tmp_path)

    first_result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=csv_file,
        database_path=database_path,
    )

    second_result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=csv_file,
        database_path=database_path,
    )

    assert first_result["status"] == "SUCCESS"
    assert second_result["status"] == "SUCCESS"

    assert first_result["run_id"] != second_result["run_id"]
    assert first_result["load_event_id"] != second_result["load_event_id"]

    assert first_result["publishing"]["inserted_count"] == 2
    assert second_result["publishing"]["inserted_count"] == 0
    assert second_result["publishing"]["skipped_count"] == 2

    with get_connection(database_path) as connection:
        customer_count = connection.execute(
            "SELECT COUNT(*) FROM customer_target"
        ).fetchone()[0]

        run_count = connection.execute(
            "SELECT COUNT(*) FROM pipeline_runs"
        ).fetchone()[0]

        event_count = connection.execute(
            "SELECT COUNT(*) FROM load_events"
        ).fetchone()[0]

    assert customer_count == 2
    assert run_count == 2
    assert event_count == 2

def test_pipeline_recovers_after_failed_ingestion(
    database_path, tmp_path
):
    """A failed ingestion can be retried successfully with the same file."""

    csv_file = tmp_path / "customers.csv"

    first_result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=csv_file,
        database_path=database_path,
    )

    assert first_result["status"] == "FAILED"

    write_customers_csv(tmp_path)

    second_result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=csv_file,
        database_path=database_path,
    )

    assert second_result["status"] == "SUCCESS"
    assert first_result["run_id"] != second_result["run_id"]
    assert second_result["records_loaded"] == 2

    with get_connection(database_path) as connection:
        runs = connection.execute(
            """
            SELECT status
            FROM pipeline_runs
            ORDER BY rowid
            """
        ).fetchall()

        events = connection.execute(
            """
            SELECT attempt_number, status
            FROM load_events
            """
        ).fetchall()

        customer_count = connection.execute(
            "SELECT COUNT(*) FROM customer_target"
        ).fetchone()[0]

    assert len(runs) == 2
    assert runs[0]["status"] == "FAILED"
    assert runs[1]["status"] == "SUCCESS"
    assert len(events) == 1
    assert events[0]["attempt_number"] == 1
    assert customer_count == 2

def test_pipeline_restarts_safely_after_interrupted_run(
    database_path, tmp_path, monkeypatch
):
    """An interrupted run leaves no partial data and can be restarted."""

    class SimulatedInterrupt(BaseException):
        """Like Ctrl+C: not caught by 'except Exception'."""

    def interrupt(*args, **kwargs):
        raise SimulatedInterrupt

    csv_file = write_customers_csv(tmp_path)

    with monkeypatch.context() as patch:
        patch.setattr("datapulse.pipeline.publish_customers", interrupt)

        with pytest.raises(SimulatedInterrupt):
            run_dataset_pipeline(
                dataset_name="customers",
                source_path=csv_file,
                database_path=database_path,
            )

    with get_connection(database_path) as connection:
        interrupted_run = connection.execute(
            "SELECT status FROM pipeline_runs"
        ).fetchone()
        interrupted_event = connection.execute(
            "SELECT status FROM load_events"
        ).fetchone()
        partial_customers = connection.execute(
            "SELECT COUNT(*) FROM customer_target"
        ).fetchone()[0]

    assert interrupted_run["status"] == "RUNNING"
    assert interrupted_event["status"] == "ARRIVED"
    assert partial_customers == 0

    restart_result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=csv_file,
        database_path=database_path,
    )

    assert restart_result["status"] == "SUCCESS"
    assert restart_result["records_loaded"] == 2

    with get_connection(database_path) as connection:
        runs = connection.execute(
            "SELECT status FROM pipeline_runs ORDER BY rowid"
        ).fetchall()
        events = connection.execute(
            """
            SELECT attempt_number, status
            FROM load_events
            ORDER BY attempt_number
            """
        ).fetchall()
        customer_count = connection.execute(
            "SELECT COUNT(*) FROM customer_target"
        ).fetchone()[0]

    assert [run["status"] for run in runs] == ["RUNNING", "SUCCESS"]
    assert [event["attempt_number"] for event in events] == [1, 2]
    assert [event["status"] for event in events] == ["ARRIVED", "SUCCESS"]
    assert customer_count == 2

def test_backfill_file_is_additive_and_never_overwrites_customers(
    database_path, tmp_path
):
    """A second file with overlapping IDs adds new rows and skips existing ones."""

    current_file = write_customers_csv(tmp_path, "customers_current.csv")

    backfill_file = tmp_path / "customers_backfill.csv"
    backfill_file.write_text(
        (
            "customer_id,first_name,last_name,email,city\n"
            "C001,Zed,Different,zed@example.com,Pune\n"
            "C003,Carol,Desai,carol@example.com,Delhi\n"
        ),
        encoding="utf-8",
    )

    first_result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=current_file,
        database_path=database_path,
    )
    backfill_result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=backfill_file,
        database_path=database_path,
    )

    assert first_result["status"] == "SUCCESS"
    assert backfill_result["status"] == "SUCCESS"
    assert backfill_result["records_loaded"] == 1
    assert backfill_result["publishing"]["inserted_count"] == 1
    assert backfill_result["publishing"]["skipped_count"] == 1

    with get_connection(database_path) as connection:
        customers = {
            row["customer_id"]: row
            for row in connection.execute(
                """
                SELECT customer_id, customer_name, source_event_id
                FROM customer_target
                """
            ).fetchall()
        }
        events = connection.execute(
            "SELECT source_file, attempt_number FROM load_events"
        ).fetchall()

    assert sorted(customers) == ["C001", "C002", "C003"]
    assert "Alice" in customers["C001"]["customer_name"]
    assert "Zed" not in customers["C001"]["customer_name"]
    assert customers["C001"]["source_event_id"] == first_result["load_event_id"]
    assert customers["C003"]["source_event_id"] == backfill_result["load_event_id"]
    assert len(events) == 2
    assert [event["attempt_number"] for event in events] == [1, 1]

def test_source_rows_reconcile_and_rejects_are_traceable(
    database_path, tmp_path
):
    """Every source row is loaded or quarantined, and every reject is traceable."""

    csv_file = tmp_path / "customers_reconciliation.csv"
    csv_file.write_text(
        (
            "customer_id,first_name,last_name,email,city\n"
            "C001,Alice,Sharma,alice@example.com,Pune\n"
            "C002,Bob,Patil,invalid-email,Mumbai\n"
            "C003,Neha,Joshi,neha@example.com,Nashik\n"
            "C001,Alice,Again,alice2@example.com,Pune\n"
        ),
        encoding="utf-8",
    )
    source_row_count = (
        len(csv_file.read_text(encoding="utf-8").strip().splitlines()) - 1
    )

    result = run_dataset_pipeline(
        dataset_name="customers",
        source_path=csv_file,
        database_path=database_path,
    )

    assert result["status"] == "PARTIAL"
    assert source_row_count == 4

    with get_connection(database_path) as connection:
        run = connection.execute(
            """
            SELECT records_received, records_loaded, records_rejected, source_file
            FROM pipeline_runs
            WHERE run_id = ?
            """,
            (result["run_id"],),
        ).fetchone()

        event = connection.execute(
            """
            SELECT rows_received, rows_loaded, rows_rejected, source_file
            FROM load_events
            WHERE load_event_id = ?
            """,
            (result["load_event_id"],),
        ).fetchone()

        targets = connection.execute(
            """
            SELECT customer_id, source_event_id, run_id, source_file
            FROM customer_target
            """
        ).fetchall()

        quarantined = connection.execute(
            """
            SELECT load_event_id, run_id, source_file, row_number,
                   raw_record_json, rejection_reason
            FROM quarantine_records
            ORDER BY row_number
            """
        ).fetchall()

        broken_links = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

    # Reconciliation: every source row is accounted for.
    assert run["records_received"] == source_row_count
    assert (
        run["records_loaded"] + run["records_rejected"]
        == run["records_received"]
    )
    assert (
        event["rows_received"],
        event["rows_loaded"],
        event["rows_rejected"],
    ) == (4, 2, 2)
    assert len(targets) + len(quarantined) == source_row_count
    assert sorted(target["customer_id"] for target in targets) == [
        "C001",
        "C003",
    ]

    # Traceability: rejected rows point back to their file, run and event.
    assert [row["row_number"] for row in quarantined] == [3, 5]

    for row in quarantined:
        assert row["load_event_id"] == result["load_event_id"]
        assert row["run_id"] == result["run_id"]
        assert row["source_file"] == event["source_file"] == run["source_file"]

    assert "INVALID_EMAIL" in quarantined[0]["rejection_reason"]
    assert "invalid-email" in quarantined[0]["raw_record_json"]
    assert "DUPLICATE_CUSTOMER_ID" in quarantined[1]["rejection_reason"]

    # Traceability: published rows point back to their file, run and event.
    for target in targets:
        assert target["source_event_id"] == result["load_event_id"]
        assert target["run_id"] == result["run_id"]
        assert target["source_file"] == run["source_file"]

    assert broken_links == []