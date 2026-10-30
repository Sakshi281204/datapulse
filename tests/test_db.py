"""Phase 1 tests: database schema and constraints."""
import sqlite3

import pytest

from datapulse.db import init_db
from datapulse.registry import sync_registry

EXPECTED_TABLES = {
    "alerts", "dataset_registry", "dq_results", "dq_rules",
    "load_history", "rejected_records", "sla_status",
}


def _table_names(connection):
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )
    return {row["name"] for row in rows}


def test_control_tables_created(db):
    assert _table_names(db) == EXPECTED_TABLES


def test_init_db_is_idempotent(db):
    init_db(db)
    init_db(db)
    assert _table_names(db) == EXPECTED_TABLES


def test_foreign_key_is_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO dq_rules (rule_id, dataset_id, column_name, rule_type) "
            "VALUES ('r1', 'no_such_dataset', 'order_id', 'not_null')"
        )


def test_invalid_load_status_is_rejected(db, sample_dataset):
    sync_registry(db, [sample_dataset])
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO load_history (run_id, dataset_id, batch_date, attempt_no, "
            "file_name, file_hash, status) "
            "VALUES ('run1', 'orders', '2026-10-30', 1, 'f.csv', 'abc', 'BOGUS')"
        )