"""Phase 1 tests: dataset registry validation and syncing."""
import pytest

from datapulse.registry import load_datasets_config, sync_registry, validate_dataset


def test_validate_accepts_valid_dataset(sample_dataset):
    assert validate_dataset(sample_dataset) == sample_dataset


def test_validate_rejects_missing_fields(sample_dataset):
    del sample_dataset["sla_deadline_time"]
    with pytest.raises(ValueError, match="missing fields"):
        validate_dataset(sample_dataset)


def test_validate_rejects_bad_time_format(sample_dataset):
    sample_dataset["expected_arrival_time"] = "7am"
    with pytest.raises(ValueError, match="HH:MM|like '06:00'"):
        validate_dataset(sample_dataset)


def test_validate_rejects_arrival_not_before_deadline(sample_dataset):
    sample_dataset["expected_arrival_time"] = "08:00"
    sample_dataset["sla_deadline_time"] = "07:00"
    with pytest.raises(ValueError, match="before"):
        validate_dataset(sample_dataset)


def test_validate_rejects_non_snake_case_id(sample_dataset):
    sample_dataset["dataset_id"] = "Orders-Daily"
    with pytest.raises(ValueError, match="snake_case"):
        validate_dataset(sample_dataset)


def test_load_datasets_config_reads_project_file():
    datasets = load_datasets_config()
    assert {d["dataset_id"] for d in datasets} == {"customers", "products", "orders", "payments"}


def test_load_datasets_config_rejects_duplicate_ids(tmp_path, sample_dataset):
    import yaml

    path = tmp_path / "datasets.yaml"
    path.write_text(yaml.safe_dump({"datasets": [sample_dataset, sample_dataset]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_datasets_config(path)


def test_sync_registry_is_idempotent(db, sample_dataset):
    assert sync_registry(db, [sample_dataset]) == 1
    assert sync_registry(db, [sample_dataset]) == 1
    count = db.execute("SELECT COUNT(*) AS n FROM dataset_registry").fetchone()["n"]
    assert count == 1


def test_sync_registry_updates_changed_values(db, sample_dataset):
    sync_registry(db, [sample_dataset])
    sample_dataset["freshness_threshold_hours"] = 12
    sync_registry(db, [sample_dataset])
    row = db.execute("SELECT freshness_threshold_hours AS h FROM dataset_registry").fetchone()
    assert row["h"] == 12
    count = db.execute("SELECT COUNT(*) AS n FROM dataset_registry").fetchone()["n"]
    assert count == 1