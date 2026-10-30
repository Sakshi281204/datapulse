"""Dataset registry: validate dataset definitions and sync them into SQLite."""
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import yaml

from datapulse.config import PROJECT_ROOT
from datapulse.logging_setup import get_logger

logger = get_logger("datapulse.registry")

DEFAULT_DATASETS_PATH = PROJECT_ROOT / "config" / "datasets.yaml"
REQUIRED_FIELDS = (
    "dataset_id",
    "frequency",
    "expected_arrival_time",
    "sla_deadline_time",
    "freshness_threshold_hours",
    "file_pattern",
    "target_table",
    "business_key",
)
ALLOWED_FREQUENCIES = {"DAILY"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

UPSERT_SQL = """
INSERT INTO dataset_registry (
    dataset_id, description, frequency, expected_arrival_time, sla_deadline_time,
    freshness_threshold_hours, file_pattern, target_table, business_key, is_active
) VALUES (
    :dataset_id, :description, :frequency, :expected_arrival_time, :sla_deadline_time,
    :freshness_threshold_hours, :file_pattern, :target_table, :business_key, :is_active
)
ON CONFLICT (dataset_id) DO UPDATE SET
    description               = excluded.description,
    frequency                 = excluded.frequency,
    expected_arrival_time     = excluded.expected_arrival_time,
    sla_deadline_time         = excluded.sla_deadline_time,
    freshness_threshold_hours = excluded.freshness_threshold_hours,
    file_pattern              = excluded.file_pattern,
    target_table              = excluded.target_table,
    business_key              = excluded.business_key,
    is_active                 = excluded.is_active,
    updated_at                = datetime('now')
"""


def _parse_time(value: object, field_name: str) -> datetime:
    """Parse an 'HH:MM' string, raising ValueError with a clear message."""
    try:
        return datetime.strptime(value, "%H:%M")
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a string like '06:00', got {value!r}") from error


def validate_dataset(dataset: dict) -> dict:
    """Check one dataset definition. Returns it unchanged or raises ValueError."""
    name = dataset.get("dataset_id", "<unknown>")
    missing = [field for field in REQUIRED_FIELDS if field not in dataset]
    if missing:
        raise ValueError(f"Dataset {name!r} is missing fields: {missing}")

    if not ID_PATTERN.match(str(dataset["dataset_id"])):
        raise ValueError(f"dataset_id {name!r} must be snake_case (a-z, 0-9, _)")
    if dataset["frequency"] not in ALLOWED_FREQUENCIES:
        raise ValueError(f"Dataset {name!r}: frequency must be one of {sorted(ALLOWED_FREQUENCIES)}")

    arrival = _parse_time(dataset["expected_arrival_time"], "expected_arrival_time")
    deadline = _parse_time(dataset["sla_deadline_time"], "sla_deadline_time")
    if arrival >= deadline:
        raise ValueError(f"Dataset {name!r}: expected_arrival_time must be before sla_deadline_time")

    threshold = dataset["freshness_threshold_hours"]
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold <= 0:
        raise ValueError(f"Dataset {name!r}: freshness_threshold_hours must be a positive integer")
    if "{batch_date}" not in dataset["file_pattern"]:
        raise ValueError(f"Dataset {name!r}: file_pattern must contain '{{batch_date}}'")
    return dataset


def load_datasets_config(path: Path = DEFAULT_DATASETS_PATH) -> list[dict]:
    """Read and validate config/datasets.yaml. Returns the list of dataset dicts."""
    if not path.exists():
        raise FileNotFoundError(f"Datasets file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        content = yaml.safe_load(file) or {}
    datasets = content.get("datasets")
    if not datasets:
        raise ValueError(f"No datasets defined in {path}")

    validated = [validate_dataset(dataset) for dataset in datasets]
    ids = [dataset["dataset_id"] for dataset in validated]
    duplicates = sorted({dataset_id for dataset_id in ids if ids.count(dataset_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate dataset_id values: {duplicates}")
    return validated


def sync_registry(connection: sqlite3.Connection, datasets: list[dict]) -> int:
    """Upsert dataset definitions into dataset_registry. Returns how many were synced.

    Running this repeatedly never creates duplicate rows: dataset_id is the key.
    """
    rows = [{"description": None, "is_active": 1, **dataset} for dataset in datasets]
    try:
        with connection:
            connection.executemany(UPSERT_SQL, rows)
    except sqlite3.Error:
        logger.exception("Failed to sync dataset registry")
        raise
    logger.info("Synced %d dataset definitions into dataset_registry", len(rows))
    return len(rows)