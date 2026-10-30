"""One-command setup: create the database schema and load the dataset registry."""
import sqlite3

from datapulse.db import get_connection, init_db
from datapulse.logging_setup import get_logger
from datapulse.registry import load_datasets_config, sync_registry

logger = get_logger("datapulse.bootstrap")

TABLES_SQL = """
SELECT name FROM sqlite_master
WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
ORDER BY name
"""
REGISTRY_SQL = """
SELECT dataset_id, expected_arrival_time, sla_deadline_time, freshness_threshold_hours
FROM dataset_registry
ORDER BY expected_arrival_time
"""


def main() -> None:
    connection = get_connection()
    try:
        init_db(connection)
        sync_registry(connection, load_datasets_config())
        tables = [row["name"] for row in connection.execute(TABLES_SQL)]
        logger.info("Tables: %s", ", ".join(tables))
        for row in connection.execute(REGISTRY_SQL):
            logger.info(
                "Registered %s | arrives %s | SLA %s | freshness limit %sh",
                row["dataset_id"], row["expected_arrival_time"],
                row["sla_deadline_time"], row["freshness_threshold_hours"],
            )
    except (sqlite3.Error, ValueError, FileNotFoundError):
        logger.exception("Bootstrap failed")
        raise SystemExit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    main()