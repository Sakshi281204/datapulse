import pandas as pd


def _check_columns(dataframe: pd.DataFrame, required_columns: set[str]) -> None:
    missing = required_columns - set(dataframe.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )


def _clean_text(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )


def transform_customers(valid_records: pd.DataFrame) -> pd.DataFrame:
    """Transform validated customer records into customer_target format."""

    required = {
        "customer_id", "first_name", "last_name", "email"
    }
    _check_columns(valid_records, required)

    result = pd.DataFrame()

    result["customer_id"] = _clean_text(valid_records["customer_id"])

    first_name = _clean_text(valid_records["first_name"])
    last_name = _clean_text(valid_records["last_name"])

    result["customer_name"] = (
        first_name + " " + last_name
    ).str.strip()

    result["email"] = _clean_text(
        valid_records["email"]
    ).str.lower()

    return result.reset_index(drop=True)


def transform_orders(valid_records: pd.DataFrame) -> pd.DataFrame:
    """Transform validated order records into orders_target format."""

    required = {
        "order_id", "customer_id", "total_amount",
        "order_date", "status"
    }
    _check_columns(valid_records, required)

    result = pd.DataFrame()

    result["order_id"] = _clean_text(valid_records["order_id"])
    result["customer_id"] = _clean_text(valid_records["customer_id"])

    dates = pd.to_datetime(
        valid_records["order_date"],
        format="%Y-%m-%d",
        errors="raise"
    )
    result["order_date"] = dates.dt.strftime("%Y-%m-%d")

    result["amount"] = pd.to_numeric(
        valid_records["total_amount"],
        errors="raise"
    )

    result["order_status"] = (
        _clean_text(valid_records["status"]).str.upper()
    )

    return result.reset_index(drop=True)