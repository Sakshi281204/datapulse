import sqlite3

from datapulse.database import deterministic_id, utc_now


def register_load_event(
    connection: sqlite3.Connection,
    dataset_name: str,
    run_id: str,
    source_file: str,
    expected_arrival_at: str,
    actual_arrival_at: str,
) -> dict:
    """
    Register one load attempt in load_events.

    The caller controls the database transaction.
    """

    dataset = connection.execute(
        """
        SELECT dataset_id
        FROM datasets
        WHERE dataset_name = ?
        """,
        (dataset_name,),
    ).fetchone()

    if dataset is None:
        raise ValueError(f"Unknown dataset: {dataset_name}")

    dataset_id = dataset["dataset_id"]

    run = connection.execute(
        """
        SELECT run_id
        FROM pipeline_runs
        WHERE run_id = ? AND dataset_id = ?
        """,
        (run_id, dataset_id),
    ).fetchone()

    if run is None:
        raise ValueError(
            f"Pipeline run {run_id} not found for {dataset_name}"
        )

    previous_attempt = connection.execute(
        """
        SELECT COALESCE(MAX(attempt_number), 0)
        FROM load_events
        WHERE dataset_id = ? AND source_file = ?
        """,
        (dataset_id, source_file),
    ).fetchone()[0]

    attempt_number = previous_attempt + 1

    load_event_id = deterministic_id(
        "load_event",
        run_id,
        dataset_id,
        source_file,
        attempt_number,
    )

    connection.execute(
        """
        INSERT INTO load_events (
            load_event_id,
            dataset_id,
            run_id,
            source_file,
            attempt_number,
            expected_arrival_at,
            actual_arrival_at,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            load_event_id,
            dataset_id,
            run_id,
            source_file,
            attempt_number,
            expected_arrival_at,
            actual_arrival_at,
            "ARRIVED",
            utc_now(),
        ),
    )

    return {
        "load_event_id": load_event_id,
        "dataset_id": dataset_id,
        "run_id": run_id,
        "source_file": source_file,
        "attempt_number": attempt_number,
        "status": "ARRIVED",
    }