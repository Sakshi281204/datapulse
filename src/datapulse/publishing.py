import sqlite3

import pandas as pd

from datapulse.database import utc_now


def _verify_load_event(
    connection: sqlite3.Connection,
    load_event: dict,
    expected_dataset: str,
):
    """Verify that the load event belongs to the expected dataset."""

    event = connection.execute(
        """
        SELECT
            le.load_event_id,
            le.dataset_id,
            le.run_id,
            le.source_file,
            d.dataset_name
        FROM load_events AS le
        JOIN datasets AS d
            ON d.dataset_id = le.dataset_id
        WHERE le.load_event_id = ?
        """,
        (load_event.get("load_event_id"),),
    ).fetchone()

    if event is None:
        raise ValueError("Load event does not exist.")

    if event["dataset_name"] != expected_dataset:
        raise ValueError(
            f"Expected {expected_dataset} load event."
        )

    for field in ("run_id", "source_file", "dataset_id"):
        if load_event.get(field) != event[field]:
            raise ValueError(
                f"Load event metadata mismatch: {field}"
            )

    return event


def _check_columns(
    records: pd.DataFrame,
    required_columns: set[str],
) -> None:
    missing = required_columns - set(records.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )


def publish_customers(
    connection: sqlite3.Connection,
    records: pd.DataFrame,
    load_event: dict,
) -> dict:
    """Publish transformed customers without overwriting existing IDs."""

    required = {"customer_id", "customer_name", "email"}
    _check_columns(records, required)

    event = _verify_load_event(
        connection, load_event, "customers"
    )

    loaded_at = utc_now()

    rows = [
        (
            str(row.customer_id),
            str(row.customer_name),
            None if pd.isna(row.email) else str(row.email),
            event["load_event_id"],
            event["run_id"],
            event["source_file"],
            loaded_at,
        )
        for row in records.itertuples(index=False)
    ]

    cursor = connection.executemany(
        """
        INSERT INTO customer_target (
            customer_id,
            customer_name,
            email,
            source_event_id,
            run_id,
            source_file,
            loaded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(customer_id) DO NOTHING
        """,
        rows,
    )

    inserted = cursor.rowcount

    return {
        "input_count": len(rows),
        "inserted_count": inserted,
        "skipped_count": len(rows) - inserted,
    }


def publish_orders(
    connection: sqlite3.Connection,
    records: pd.DataFrame,
    load_event: dict,
) -> dict:
    """Publish transformed orders without overwriting existing IDs."""

    required = {
        "order_id",
        "customer_id",
        "order_date",
        "amount",
        "order_status",
    }
    _check_columns(records, required)

    event = _verify_load_event(
        connection, load_event, "orders"
    )

    loaded_at = utc_now()

    rows = [
        (
            str(row.order_id),
            str(row.customer_id),
            str(row.order_date),
            float(row.amount),
            str(row.order_status),
            event["load_event_id"],
            event["run_id"],
            event["source_file"],
            loaded_at,
        )
        for row in records.itertuples(index=False)
    ]

    cursor = connection.executemany(
        """
        INSERT INTO orders_target (
            order_id,
            customer_id,
            order_date,
            amount,
            order_status,
            source_event_id,
            run_id,
            source_file,
            loaded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(order_id) DO NOTHING
        """,
        rows,
    )

    inserted = cursor.rowcount

    return {
        "input_count": len(rows),
        "inserted_count": inserted,
        "skipped_count": len(rows) - inserted,
    }