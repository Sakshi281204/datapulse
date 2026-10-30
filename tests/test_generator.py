
"""Phase 3 tests: synthetic data generation."""

import csv
from collections import Counter

import pytest

from datapulse.generator import (
    CUSTOMER_FIELDS,
    PRODUCT_FIELDS,
    ORDER_FIELDS,
    PAYMENT_FIELDS,
    LABEL_FIELDS,
    generate_datasets,
)


def read_csv(path):
    """Read a generated CSV file."""
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def duplicate_count(rows, field):
    """Count duplicate values in a CSV column."""
    counts = Counter(row[field] for row in rows)
    return sum(count - 1 for count in counts.values() if count > 1)


def test_generator_creates_all_expected_files(tmp_path):
    paths = generate_datasets(
        output_dir=tmp_path / "sample",
        expected_dir=tmp_path / "expected",
        record_count=100,
        seed=42,
    )

    assert len(paths) == 5
    assert all(path.exists() for path in paths.values())


def test_generator_creates_correct_headers_and_counts(tmp_path):
    paths = generate_datasets(
        output_dir=tmp_path / "sample",
        expected_dir=tmp_path / "expected",
        record_count=100,
        seed=42,
    )

    expected = {
        "customers": CUSTOMER_FIELDS,
        "products": PRODUCT_FIELDS,
        "orders": ORDER_FIELDS,
        "payments": PAYMENT_FIELDS,
        "labels": LABEL_FIELDS,
    }

    for name, fields in expected.items():
        with paths[name].open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            assert reader.fieldnames == fields
            assert len(list(reader)) == (100 if name != "labels" else 20)


def test_generator_is_reproducible_with_same_seed(tmp_path):
    first = generate_datasets(
        tmp_path / "first",
        tmp_path / "expected_first",
        record_count=100,
        seed=42,
    )

    second = generate_datasets(
        tmp_path / "second",
        tmp_path / "expected_second",
        record_count=100,
        seed=42,
    )

    for name in first:
        assert first[name].read_bytes() == second[name].read_bytes()


def test_different_seed_generates_different_data(tmp_path):
    first = generate_datasets(
        tmp_path / "first",
        tmp_path / "expected_first",
        record_count=100,
        seed=42,
    )

    second = generate_datasets(
        tmp_path / "second",
        tmp_path / "expected_second",
        record_count=100,
        seed=99,
    )

    assert first["customers"].read_bytes() != second["customers"].read_bytes()


def test_duplicate_ids_are_generated_and_labelled(tmp_path):
    paths = generate_datasets(
        tmp_path / "sample",
        tmp_path / "expected",
        record_count=100,
        seed=42,
    )

    expected_duplicates = {
        "customers": "customer_id",
        "products": "product_id",
        "orders": "order_id",
        "payments": "payment_id",
    }

    for dataset, field in expected_duplicates.items():
        rows = read_csv(paths[dataset])
        assert duplicate_count(rows, field) == 1

    labels = read_csv(paths["labels"])
    issue_types = {row["issue_type"] for row in labels}

    assert {
        "DUPLICATE_CUSTOMER_ID",
        "DUPLICATE_PRODUCT_ID",
        "DUPLICATE_ORDER_ID",
        "DUPLICATE_PAYMENT_ID",
    }.issubset(issue_types)


def test_invalid_references_are_generated_and_labelled(tmp_path):
    paths = generate_datasets(
        tmp_path / "sample",
        tmp_path / "expected",
        record_count=100,
        seed=42,
    )

    customers = read_csv(paths["customers"])
    products = read_csv(paths["products"])
    orders = read_csv(paths["orders"])
    payments = read_csv(paths["payments"])

    customer_ids = {row["customer_id"] for row in customers}
    product_ids = {row["product_id"] for row in products}
    order_ids = {row["order_id"] for row in orders}

    missing_customers = [
        row_number
        for row_number, row in enumerate(orders, start=2)
        if row["customer_id"] not in customer_ids
    ]

    missing_products = [
        row_number
        for row_number, row in enumerate(orders, start=2)
        if row["product_id"] not in product_ids
    ]

    missing_orders = [
        row_number
        for row_number, row in enumerate(payments, start=2)
        if row["order_id"] not in order_ids
    ]

    assert missing_customers == [4]
    assert missing_products == [5]
    assert missing_orders == [4]


def test_missing_values_and_invalid_data_are_generated(tmp_path):
    paths = generate_datasets(
        tmp_path / "sample",
        tmp_path / "expected",
        record_count=100,
        seed=42,
    )

    customers = read_csv(paths["customers"])
    products = read_csv(paths["products"])
    payments = read_csv(paths["payments"])
    orders = read_csv(paths["orders"])

    assert any(row["email"] == "" for row in customers)
    assert any(row["category"] == "" for row in products)
    assert any(row["payment_method"] == "" for row in payments)

    assert any(float(row["unit_price"]) < 0 for row in products)
    assert any(int(row["quantity"]) < 0 for row in orders)
    assert any(float(row["total_amount"]) < 0 for row in orders)
    assert any(float(row["amount"]) < 0 for row in payments)

    assert any(row["created_at"] == "not-a-date" for row in customers)
    assert any(row["order_date"] == "not-a-date" for row in orders)

    assert any(row["status"] == "UNKNOWN_STATUS" for row in orders)
    assert any(row["payment_status"] == "UNKNOWN_STATUS" for row in payments)


def test_validation_labels_are_separate(tmp_path):
    paths = generate_datasets(
        tmp_path / "sample",
        tmp_path / "expected",
        record_count=100,
        seed=42,
    )

    labels = read_csv(paths["labels"])

    assert paths["labels"].parent != paths["customers"].parent
    assert len(labels) == 20
    assert all(row["expected_outcome"] == "INVALID" for row in labels)


def test_clean_mode_has_valid_relationships_and_matching_amounts(tmp_path):
    paths = generate_datasets(
        tmp_path / "sample",
        tmp_path / "expected",
        record_count=100,
        seed=42,
        include_invalid=False,
    )

    customers = read_csv(paths["customers"])
    products = read_csv(paths["products"])
    orders = read_csv(paths["orders"])
    payments = read_csv(paths["payments"])
    labels = read_csv(paths["labels"])

    customer_ids = {row["customer_id"] for row in customers}
    product_ids = {row["product_id"] for row in products}
    order_ids = {row["order_id"] for row in orders}

    assert duplicate_count(customers, "customer_id") == 0
    assert duplicate_count(products, "product_id") == 0
    assert duplicate_count(orders, "order_id") == 0
    assert duplicate_count(payments, "payment_id") == 0

    assert all(row["customer_id"] in customer_ids for row in orders)
    assert all(row["product_id"] in product_ids for row in orders)
    assert all(row["order_id"] in order_ids for row in payments)

    order_amounts = {row["order_id"]: row["total_amount"] for row in orders}

    assert all(
        row["amount"] == order_amounts[row["order_id"]]
        for row in payments
    )

    assert labels == []


def test_clean_mode_has_no_missing_values(tmp_path):
    paths = generate_datasets(
        tmp_path / "sample",
        tmp_path / "expected",
        record_count=20,
        seed=42,
        include_invalid=False,
    )

    for name in ["customers", "products", "orders", "payments"]:
        rows = read_csv(paths[name])
        assert all(
            value != ""
            for row in rows
            for value in row.values()
        )


def test_generator_supports_large_dataset(tmp_path):
    paths = generate_datasets(
        tmp_path / "sample",
        tmp_path / "expected",
        record_count=10000,
        seed=42,
    )

    for name in ["customers", "products", "orders", "payments"]:
        assert len(read_csv(paths[name])) == 10000


@pytest.mark.parametrize("record_count", [0, -1, True])
def test_generator_rejects_invalid_record_count(tmp_path, record_count):
    with pytest.raises(ValueError, match="record_count"):
        generate_datasets(
            tmp_path / "sample",
            tmp_path / "expected",
            record_count=record_count,
        )
