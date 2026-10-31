import json

import pandas as pd

from datapulse.database import deterministic_id, utc_now


DATASET_KEYS = {
    "customers": "customer_id",
    "orders": "order_id",
}


def _json_safe(value):
    """Convert pandas and NumPy values into JSON-compatible values."""
    if pd.isna(value):
        return None

    if hasattr(value, "item"):
        return value.item()

    return value


def quarantine_rejected_records(
    connection,
    dataset_name,
    rejected_records,
    load_event,
):
    """
    Store rejected records with their original data and rejection reasons.

    The caller manages the database transaction and commit.
    """
    if dataset_name not in DATASET_KEYS:
        raise ValueError(f"Unsupported dataset: {dataset_name}")

    required_columns = {"row_number", "rejection_reason"}
    missing = required_columns - set(rejected_records.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    event = connection.execute(
        """
        SELECT le.load_event_id, le.dataset_id, le.run_id,
               le.source_file, d.dataset_name
        FROM load_events le
        JOIN datasets d ON d.dataset_id = le.dataset_id
        WHERE le.load_event_id = ?
        """,
        (load_event["load_event_id"],),
    ).fetchone()

    if event is None:
        raise ValueError("Load event does not exist")

    if event["dataset_name"] != dataset_name:
        raise ValueError("Load event belongs to a different dataset")

    if (
        event["run_id"] != load_event["run_id"]
        or event["source_file"] != load_event["source_file"]
    ):
        raise ValueError("Load event metadata does not match")

    record_key_column = DATASET_KEYS[dataset_name]
    inserted_count = 0
    skipped_count = 0

    for _, row in rejected_records.iterrows():
        row_number = int(row["row_number"])
        rejection_reason = str(row["rejection_reason"]).strip()

        if row_number < 1 or not rejection_reason:
            raise ValueError("Invalid row number or rejection reason")

        raw_record = {
            column: _json_safe(value)
            for column, value in row.drop(
                labels=["row_number", "rejection_reason"]
            ).items()
        }

        record_key = raw_record.get(record_key_column)

        quarantine_id = deterministic_id(
            "quarantine",
            load_event["load_event_id"],
            row_number,
            rejection_reason,
        )

        cursor = connection.execute(
            """
            INSERT INTO quarantine_records (
                quarantine_id,
                dataset_id,
                load_event_id,
                run_id,
                source_file,
                row_number,
                record_key,
                raw_record_json,
                rejection_reason,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(load_event_id, row_number, rejection_reason)
            DO NOTHING
            """,
            (
                quarantine_id,
                event["dataset_id"],
                event["load_event_id"],
                event["run_id"],
                event["source_file"],
                row_number,
                record_key,
                json.dumps(
                    raw_record,
                    sort_keys=True,
                    allow_nan=False,
                ),
                rejection_reason,
                utc_now(),
            ),
        )

        if cursor.rowcount == 1:
            inserted_count += 1
        else:
            skipped_count += 1

    return {
        "input_count": len(rejected_records),
        "inserted_count": inserted_count,
        "skipped_count": skipped_count,
    }
