import pandas as pd
import pytest

from datapulse.transformation import (
    transform_customers,
    transform_orders,
)


def test_transform_customers():
    source = pd.DataFrame({
        "customer_id": [" C001 "],
        "first_name": ["  Sakshi  "],
        "last_name": ["  Gurule "],
        "email": [" SAKSHI@EXAMPLE.COM "],
        "city": ["Pune"],
    })

    result = transform_customers(source)

    assert result.iloc[0]["customer_id"] == "C001"
    assert result.iloc[0]["customer_name"] == "Sakshi Gurule"
    assert result.iloc[0]["email"] == "sakshi@example.com"
    assert list(result.columns) == [
        "customer_id", "customer_name", "email"
    ]


def test_transform_orders():
    source = pd.DataFrame({
        "order_id": [" O001 "],
        "customer_id": [" C001 "],
        "total_amount": ["1500.50"],
        "order_date": ["2026-10-30"],
        "status": [" delivered "],
    })

    result = transform_orders(source)

    assert result.iloc[0]["order_id"] == "O001"
    assert result.iloc[0]["customer_id"] == "C001"
    assert result.iloc[0]["amount"] == 1500.50
    assert result.iloc[0]["order_date"] == "2026-10-30"
    assert result.iloc[0]["order_status"] == "DELIVERED"
    assert list(result.columns) == [
        "order_id", "customer_id", "order_date",
        "amount", "order_status"
    ]


def test_customer_transformation_does_not_modify_source():
    source = pd.DataFrame({
        "customer_id": [" C001 "],
        "first_name": ["Sakshi"],
        "last_name": ["Gurule"],
        "email": ["SAKSHI@EXAMPLE.COM"],
    })

    original = source.copy(deep=True)

    transform_customers(source)

    pd.testing.assert_frame_equal(source, original)


def test_order_transformation_does_not_modify_source():
    source = pd.DataFrame({
        "order_id": ["O001"],
        "customer_id": ["C001"],
        "total_amount": [100],
        "order_date": ["2026-10-30"],
        "status": ["pending"],
    })

    original = source.copy(deep=True)

    transform_orders(source)

    pd.testing.assert_frame_equal(source, original)


def test_customer_transformation_rejects_missing_columns():
    source = pd.DataFrame({
        "customer_id": ["C001"],
        "first_name": ["Sakshi"],
    })

    with pytest.raises(ValueError, match="Missing required columns"):
        transform_customers(source)


def test_order_transformation_rejects_missing_columns():
    source = pd.DataFrame({
        "order_id": ["O001"],
        "customer_id": ["C001"],
    })

    with pytest.raises(ValueError, match="Missing required columns"):
        transform_orders(source)