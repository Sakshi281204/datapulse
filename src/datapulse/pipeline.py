"""End-to-end DataPulse pipeline orchestration."""
from datetime import timezone
from datetime import datetime, time
from zoneinfo import ZoneInfo
from datapulse.load_events import register_load_event
from datapulse.validation import validate_customers, validate_orders
from datapulse.transformation import transform_customers, transform_orders
from datapulse.quarantine import quarantine_rejected_records
from datapulse.publishing import publish_customers, publish_orders
from contextlib import closing
from pathlib import Path

from datapulse.database import DATABASE_PATH, get_connection
from datapulse.ingestion import ingest_file
from datapulse.database import utc_now
from contextlib import closing
from pathlib import Path

from datapulse.database import DATABASE_PATH, get_connection
from datapulse.ingestion import ingest_file
import sqlite3


def get_dataset_schedule(
    connection: sqlite3.Connection,
    dataset_name: str,
) -> dict:
    """Get expected and actual arrival timestamps for a dataset."""

    dataset = connection.execute(
        """
        SELECT expected_arrival_time, timezone
        FROM datasets
        WHERE dataset_name = ?
        """,
        (dataset_name,),
    ).fetchone()

    if dataset is None:
        raise ValueError(f"Unknown dataset: {dataset_name}")

    dataset_timezone = ZoneInfo(dataset["timezone"])

    actual_arrival = datetime.now(ZoneInfo("UTC"))

    expected_time = time.fromisoformat(
        dataset["expected_arrival_time"]
    )

    expected_arrival = datetime.combine(
        actual_arrival.astimezone(dataset_timezone).date(),
        expected_time,
        tzinfo=dataset_timezone,
    )

    return {
        "expected_arrival_at": expected_arrival.isoformat(
            timespec="seconds"
        ),
        "actual_arrival_at": actual_arrival.isoformat(
            timespec="seconds"
        ),
    }
def prepare_load_event(
    connection: sqlite3.Connection,
    ingestion_result,
) -> dict:
    """Prepare an ingested file for validation and publishing."""

    if ingestion_result.status != "SUCCESS":
        raise ValueError(
            "Cannot register a load event for failed ingestion."
        )

    schedule = get_dataset_schedule(
        connection,
        ingestion_result.dataset_name,
    )

    connection.execute(
        """
        UPDATE pipeline_runs
        SET status = 'RUNNING',
            completed_at = NULL,
            error_message = NULL
        WHERE run_id = ?
        """,
        (ingestion_result.run_id,),
    )

    load_event = register_load_event(
        connection=connection,
        dataset_name=ingestion_result.dataset_name,
        run_id=ingestion_result.run_id,
        source_file=ingestion_result.source_file,
        expected_arrival_at=schedule["expected_arrival_at"],
        actual_arrival_at=schedule["actual_arrival_at"],
    )

    return load_event
def validate_and_transform(
    connection: sqlite3.Connection,
    dataset_name: str,
    dataframe,
):
    """Validate source records and transform valid records."""

    if dataset_name == "customers":
        validation_result = validate_customers(dataframe)

        transformed_records = transform_customers(
            validation_result.valid_records
        )

    elif dataset_name == "orders":
        customer_rows = connection.execute(
            "SELECT customer_id FROM customer_target"
        ).fetchall()

        valid_customer_ids = {
            row["customer_id"] for row in customer_rows
        }

        validation_result = validate_orders(
            dataframe,
            valid_customer_ids,
        )

        transformed_records = transform_orders(
            validation_result.valid_records
        )

    else:
        raise ValueError(
            f"Unsupported dataset: {dataset_name}"
        )

    return validation_result, transformed_records
def quarantine_and_publish(
    connection: sqlite3.Connection,
    dataset_name: str,
    validation_result,
    transformed_records,
    load_event: dict,
) -> dict:
    """Quarantine rejected rows and publish valid transformed rows."""

    quarantine_result = quarantine_rejected_records(
        connection=connection,
        dataset_name=dataset_name,
        rejected_records=validation_result.rejected_records,
        load_event=load_event,
    )

    if dataset_name == "customers":
        publishing_result = publish_customers(
            connection=connection,
            records=transformed_records,
            load_event=load_event,
        )

    elif dataset_name == "orders":
        publishing_result = publish_orders(
            connection=connection,
            records=transformed_records,
            load_event=load_event,
        )

    else:
        raise ValueError(
            f"Unsupported dataset: {dataset_name}"
        )

    return {
        "quarantine": quarantine_result,
        "publishing": publishing_result,
    }
def finalize_pipeline_run(
    connection: sqlite3.Connection,
    run_id: str,
    load_event_id: str,
    records_received: int,
    records_loaded: int,
    records_rejected: int,
) -> dict:
    """Save final pipeline and load-event metrics."""

    completed_at = utc_now()

    pipeline_status = (
        "PARTIAL" if records_rejected > 0 else "SUCCESS"
    )

    connection.execute(
        """
        UPDATE pipeline_runs
        SET completed_at = ?,
            status = ?,
            records_received = ?,
            records_loaded = ?,
            records_rejected = ?,
            error_message = NULL
        WHERE run_id = ?
        """,
        (
            completed_at,
            pipeline_status,
            records_received,
            records_loaded,
            records_rejected,
            run_id,
        ),
    )

    connection.execute(
        """
        UPDATE load_events
        SET completion_at = ?,
            status = 'SUCCESS',
            rows_received = ?,
            rows_loaded = ?,
            rows_rejected = ?
        WHERE load_event_id = ?
        """,
        (
            completed_at,
            records_received,
            records_loaded,
            records_rejected,
            load_event_id,
        ),
    )

    return {
        "status": pipeline_status,
        "completed_at": completed_at,
        "records_received": records_received,
        "records_loaded": records_loaded,
        "records_rejected": records_rejected,
    }
def run_dataset_pipeline(
    dataset_name: str,
    source_path: str | Path,
    database_path: str | Path = DATABASE_PATH,
) -> dict:
    """Execute the complete pipeline for one supported dataset."""

    database_path = Path(database_path)

    # Step 1: Read the source CSV and create a pipeline run.
    ingestion_result = ingest_file(
        dataset_name=dataset_name,
        file_path=source_path,
        database_path=database_path,
    )

    if ingestion_result.status != "SUCCESS":
        return {
            "dataset_name": dataset_name,
            "run_id": ingestion_result.run_id,
            "status": "FAILED",
            "error_message": ingestion_result.error_message,
        }

    load_event = None

    try:
        # Step 2: Register the file arrival.
        with closing(get_connection(database_path)) as connection:
            load_event = prepare_load_event(
                connection,
                ingestion_result,
            )
            connection.commit()

            # Step 3: Validate and transform the source records.
            validation_result, transformed_records = (
                validate_and_transform(
                    connection,
                    dataset_name,
                    ingestion_result.data,
                )
            )

            # Step 4: Quarantine invalid rows and publish valid rows.
            processing_result = quarantine_and_publish(
                connection=connection,
                dataset_name=dataset_name,
                validation_result=validation_result,
                transformed_records=transformed_records,
                load_event=load_event,
            )

            publishing_result = processing_result["publishing"]

            # Step 5: Save final pipeline metrics.
            final_result = finalize_pipeline_run(
                connection=connection,
                run_id=ingestion_result.run_id,
                load_event_id=load_event["load_event_id"],
                records_received=validation_result.input_count,
                records_loaded=publishing_result["inserted_count"],
                records_rejected=validation_result.rejected_count,
            )

            connection.commit()

        return {
            "dataset_name": dataset_name,
            "run_id": ingestion_result.run_id,
            "load_event_id": load_event["load_event_id"],
            **final_result,
            "quarantine": processing_result["quarantine"],
            "publishing": publishing_result,
        }

    except Exception as exc:
        error_message = str(exc)
        completed_at = utc_now()

        # Roll back unfinished processing changes.
        try:
            connection.rollback()
        except Exception:
            pass

        # Record the failure separately so it survives the rollback.
        with closing(get_connection(database_path)) as failure_connection:
            failure_connection.execute(
                """
                UPDATE pipeline_runs
                SET status = 'FAILED',
                    completed_at = ?,
                    error_message = ?
                WHERE run_id = ?
                """,
                (
                    completed_at,
                    error_message,
                    ingestion_result.run_id,
                ),
            )

            if load_event is not None:
                failure_connection.execute(
                    """
                    UPDATE load_events
                    SET status = 'FAILED',
                        completion_at = ?,
                        error_message = ?
                    WHERE load_event_id = ?
                    """,
                    (
                        completed_at,
                        error_message,
                        load_event["load_event_id"],
                    ),
                )

            failure_connection.commit()

        return {
            "dataset_name": dataset_name,
            "run_id": ingestion_result.run_id,
            "load_event_id": (
                load_event["load_event_id"]
                if load_event is not None
                else None
            ),
            "status": "FAILED",
            "error_message": error_message,
        }
