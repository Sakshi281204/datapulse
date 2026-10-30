from __future__ import annotations

import sqlite3
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATABASE_PATH = PROJECT_ROOT / "data" / "datapulse_phase2.db"
SCHEMA_PATH = PROJECT_ROOT / "sql" / "phase2_schema.sql"


# Stable namespace for deterministic IDs
DATAPULSE_NAMESPACE = uuid.UUID(
    "8f1c4d2a-5b6e-4c90-9a1d-2e7f6b8c3d40"
)


def utc_now() -> str:
    """Return the current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def deterministic_id(prefix: str, *parts: str) -> str:
    """
    Generate a stable ID from a prefix and input values.

    The same inputs always generate the same ID.
    """
    value = "|".join((prefix, *[str(part) for part in parts]))

    generated = uuid.uuid5(
        DATAPULSE_NAMESPACE,
        value
    )

    return f"{prefix}_{generated.hex}"


def get_connection(
    database_path: Path | str = DATABASE_PATH
) -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys enabled."""

    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)

    connection.row_factory = sqlite3.Row

    # SQLite does not enforce foreign keys unless enabled.
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database(
    database_path: Path | str = DATABASE_PATH
) -> None:
    """Create all Phase 2 tables and indexes."""

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"SQL schema not found: {SCHEMA_PATH}"
        )

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with get_connection(database_path) as connection:
        connection.executescript(schema_sql)


def seed_datasets(
    database_path: Path | str = DATABASE_PATH
) -> None:
    """
    Insert or update the sample dataset configurations.

    Dataset IDs remain stable across repeated executions.
    """

    now = utc_now()

    datasets: list[dict[str, Any]] = [
        {
            "dataset_id": "dataset_customers",
            "dataset_name": "customers",
            "source_system": "synthetic_source",
            "source_path": "data/incoming/customers",
            "expected_arrival_time": "06:00",
            "timezone": "Asia/Kolkata",
            "arrival_grace_minutes": 15,
            "completion_sla_minutes": 30,
            "freshness_sla_minutes": 1440,
        },
        {
            "dataset_id": "dataset_products",
            "dataset_name": "products",
            "source_system": "synthetic_source",
            "source_path": "data/incoming/products",
            "expected_arrival_time": "06:30",
            "timezone": "Asia/Kolkata",
            "arrival_grace_minutes": 15,
            "completion_sla_minutes": 30,
            "freshness_sla_minutes": 1440,
        },
        {
            "dataset_id": "dataset_orders",
            "dataset_name": "orders",
            "source_system": "synthetic_source",
            "source_path": "data/incoming/orders",
            "expected_arrival_time": "07:00",
            "timezone": "Asia/Kolkata",
            "arrival_grace_minutes": 15,
            "completion_sla_minutes": 45,
            "freshness_sla_minutes": 1440,
        },
        {
            "dataset_id": "dataset_payments",
            "dataset_name": "payments",
            "source_system": "synthetic_source",
            "source_path": "data/incoming/payments",
            "expected_arrival_time": "07:30",
            "timezone": "Asia/Kolkata",
            "arrival_grace_minutes": 15,
            "completion_sla_minutes": 45,
            "freshness_sla_minutes": 1440,
        },
    ]

    insert_sql = """
        INSERT INTO datasets (
            dataset_id,
            dataset_name,
            source_system,
            source_path,
            expected_arrival_time,
            timezone,
            arrival_grace_minutes,
            completion_sla_minutes,
            freshness_sla_minutes,
            is_active,
            created_at,
            updated_at
        )
        VALUES (
            :dataset_id,
            :dataset_name,
            :source_system,
            :source_path,
            :expected_arrival_time,
            :timezone,
            :arrival_grace_minutes,
            :completion_sla_minutes,
            :freshness_sla_minutes,
            1,
            :created_at,
            :updated_at
        )
        ON CONFLICT(dataset_id) DO UPDATE SET
            dataset_name = excluded.dataset_name,
            source_system = excluded.source_system,
            source_path = excluded.source_path,
            expected_arrival_time = excluded.expected_arrival_time,
            timezone = excluded.timezone,
            arrival_grace_minutes = excluded.arrival_grace_minutes,
            completion_sla_minutes = excluded.completion_sla_minutes,
            freshness_sla_minutes = excluded.freshness_sla_minutes,
            is_active = excluded.is_active,
            updated_at = excluded.updated_at
    """

    with get_connection(database_path) as connection:
        for dataset in datasets:
            dataset["created_at"] = now
            dataset["updated_at"] = now

            connection.execute(insert_sql, dataset)


def get_table_names(
    database_path: Path | str = DATABASE_PATH
) -> list[str]:
    """Return all user-created SQLite table names."""

    with get_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

    return [row["name"] for row in rows]


def main() -> None:
    """Initialize the database and insert sample configurations."""

    initialize_database()
    seed_datasets()

    print("DataPulse Phase 2 database initialized.")
    print(f"Database: {DATABASE_PATH}")

    print("\nTables:")
    for table_name in get_table_names():
        print(f"- {table_name}")

    with get_connection() as connection:
        dataset_count = connection.execute(
            "SELECT COUNT(*) FROM datasets"
        ).fetchone()[0]

    print(f"\nSample datasets inserted: {dataset_count}")


if __name__ == "__main__":
    main()