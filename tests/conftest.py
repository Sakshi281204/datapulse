"""Shared pytest fixtures."""
import pytest

from datapulse.db import get_connection, init_db


@pytest.fixture
def db():
    """A fresh in-memory database with the schema applied."""
    connection = get_connection(":memory:")
    init_db(connection)
    yield connection
    connection.close()


@pytest.fixture
def sample_dataset():
    """A valid dataset definition (a new copy for every test)."""
    return {
        "dataset_id": "orders",
        "description": "Test orders",
        "frequency": "DAILY",
        "expected_arrival_time": "07:00",
        "sla_deadline_time": "08:00",
        "freshness_threshold_hours": 26,
        "file_pattern": "orders_{batch_date}.csv",
        "target_table": "orders",
        "business_key": "order_id",
    }