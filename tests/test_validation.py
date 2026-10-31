
"""Phase 5 tests: source data validation."""

import pandas as pd
import pytest

from datapulse.validation import (
    validate_customers,
    validate_orders,
    validate_dataset,
)


@pytest.fixture
def customers():
    return pd.DataFrame([
        {
            "customer_id": "CUS001",
            "first_name": "Aditi",
            "last_name": "Sharma",
            "email": "aditi@example.com",
            "phone": "9876543210",
            "city": "Pune",
            "created_at": "2025-01-01",
        },
        {
            "customer_id": "CUS002",
            "first_name": "Rahul",
            "last_name": "Patil",
            "email": "rahul@example.com",
            "phone": "9876543211",
            "city": "Nashik",
            "created_at": "2025-01-02",
        },
    ])


@pytest.fixture
def orders():
    return pd.DataFrame([
        {
            "order_id": "ORD001",
            "customer_id": "CUS001",
            "product_id": "PRD001",
            "order_date": "2025-02-01",
            "quantity": "2",
            "unit_price": "100",
            "total_amount": "200",
            "status": "PLACED",
        },
        {
            "order_id": "ORD002",
            "customer_id": "CUS002",
            "product_id": "PRD002",
            "order_date": "2025-02-02",
            "quantity": "1",
            "unit_price": "300",
            "total_amount": "300",
            "status": "DELIVERED",
        },
    ])


def test_valid_customers_are_accepted(customers):
    result = validate_customers(customers)

    assert result.input_count == 2
    assert result.valid_count == 2
    assert result.rejected_count == 0


def test_duplicate_customer_id_is_rejected(customers):
    duplicate = customers.iloc[[0]].copy()
    dataframe = pd.concat(
        [customers, duplicate],
        ignore_index=True,
    )

    result = validate_customers(dataframe)

    assert result.valid_count == 2
    assert result.rejected_count == 1
    assert "DUPLICATE_CUSTOMER_ID" in (
        result.rejected_records.iloc[0]["rejection_reason"]
    )


def test_missing_customer_fields_are_rejected(customers):
    customers.loc[0, "first_name"] = ""
    customers.loc[1, "city"] = None

    result = validate_customers(customers)

    assert result.rejected_count == 2
    assert "MISSING_FIRST_NAME" in (
        result.rejected_records.iloc[0]["rejection_reason"]
    )
    assert "MISSING_CITY" in (
        result.rejected_records.iloc[1]["rejection_reason"]
    )


def test_invalid_email_is_rejected(customers):
    customers.loc[0, "email"] = "not-an-email"

    result = validate_customers(customers)

    assert result.rejected_count == 1
    assert "INVALID_EMAIL" in (
        result.rejected_records.iloc[0]["rejection_reason"]
    )


def test_valid_orders_are_accepted(orders):
    result = validate_orders(
        orders,
        {"CUS001", "CUS002"},
    )

    assert result.valid_count == 2
    assert result.rejected_count == 0


@pytest.mark.parametrize(
    "status",
    ["UNKNOWN_STATUS", "", None, "INVALID"],
)
def test_invalid_order_status_is_rejected(orders, status):
    orders.loc[0, "status"] = status

    result = validate_orders(
        orders,
        {"CUS001", "CUS002"},
    )

    assert result.rejected_count == 1
    assert "INVALID_ORDER_STATUS" in (
        result.rejected_records.iloc[0]["rejection_reason"]
    )


def test_duplicate_order_id_is_rejected(orders):
    duplicate = orders.iloc[[0]].copy()
    dataframe = pd.concat(
        [orders, duplicate],
        ignore_index=True,
    )

    result = validate_orders(
        dataframe,
        {"CUS001", "CUS002"},
    )

    assert result.valid_count == 2
    assert result.rejected_count == 1
    assert "DUPLICATE_ORDER_ID" in (
        result.rejected_records.iloc[0]["rejection_reason"]
    )


def test_invalid_customer_reference_is_rejected(orders):
    orders.loc[0, "customer_id"] = "CUS_UNKNOWN"

    result = validate_orders(
        orders,
        {"CUS001", "CUS002"},
    )

    assert result.rejected_count == 1
    assert "INVALID_CUSTOMER_REFERENCE" in (
        result.rejected_records.iloc[0]["rejection_reason"]
    )


@pytest.mark.parametrize("amount", ["0", "-100", "invalid", ""])
def test_invalid_order_amount_is_rejected(orders, amount):
    orders.loc[0, "total_amount"] = amount

    result = validate_orders(
        orders,
        {"CUS001", "CUS002"},
    )

    assert result.rejected_count == 1
    assert "INVALID_ORDER_AMOUNT" in (
        result.rejected_records.iloc[0]["rejection_reason"]
    )


def test_invalid_order_date_is_rejected(orders):
    orders.loc[0, "order_date"] = "not-a-date"

    result = validate_orders(
        orders,
        {"CUS001", "CUS002"},
    )

    assert result.rejected_count == 1
    assert "INVALID_ORDER_DATE" in (
        result.rejected_records.iloc[0]["rejection_reason"]
    )


def test_missing_required_columns_raise_error():
    dataframe = pd.DataFrame({"customer_id": ["CUS001"]})

    with pytest.raises(ValueError, match="missing required columns"):
        validate_customers(dataframe)


def test_order_validation_requires_customer_ids(orders):
    with pytest.raises(ValueError, match="valid_customer_ids"):
        validate_dataset("orders", orders)


def test_original_dataframe_is_not_modified(customers):
    original = customers.copy(deep=True)

    validate_customers(customers)

    pd.testing.assert_frame_equal(customers, original)


def test_rejected_records_include_csv_row_numbers(customers):
    customers.loc[1, "email"] = "invalid"

    result = validate_customers(customers)

    assert result.rejected_records.iloc[0]["row_number"] == 3
