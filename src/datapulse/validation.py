
"""Data quality validation for DataPulse source CSV datasets."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


CUSTOMER_REQUIRED_COLUMNS = {
    "customer_id",
    "first_name",
    "last_name",
    "email",
    "city",
}

ORDER_REQUIRED_COLUMNS = {
    "order_id",
    "customer_id",
    "total_amount",
    "order_date",
    "status",
}

VALID_ORDER_STATUSES = {
    "PLACED",
    "SHIPPED",
    "DELIVERED",
    "CANCELLED",
}


@dataclass
class ValidationResult:
    """Results of validating one source dataset."""

    dataset_name: str
    valid_records: pd.DataFrame
    rejected_records: pd.DataFrame
    input_count: int

    @property
    def valid_count(self) -> int:
        return len(self.valid_records)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected_records)


def _check_columns(
    dataframe: pd.DataFrame,
    required_columns: set[str],
    dataset_name: str,
) -> None:
    """Raise an informative error if required source columns are missing."""
    missing = sorted(required_columns - set(dataframe.columns))

    if missing:
        raise ValueError(
            f"{dataset_name} is missing required columns: "
            f"{', '.join(missing)}"
        )


def _is_blank(series: pd.Series) -> pd.Series:
    """Identify null, empty and whitespace-only values."""
    return (
        series.isna()
        | series.astype("string").str.strip().eq("").fillna(True)
    )


def _build_result(
    dataset_name: str,
    dataframe: pd.DataFrame,
    errors: list[list[str]],
) -> ValidationResult:
    """Separate valid and rejected rows without modifying the input."""
    valid_mask = [not row_errors for row_errors in errors]

    valid_records = dataframe.loc[valid_mask].copy()
    rejected_records = dataframe.loc[
        [not is_valid for is_valid in valid_mask]
    ].copy()

    rejected_positions = [
        index for index, row_errors in enumerate(errors) if row_errors
    ]

    rejected_records.insert(
        0,
        "row_number",
        [position + 2 for position in rejected_positions],
    )

    rejected_records["rejection_reason"] = [
        "; ".join(errors[position])
        for position in rejected_positions
    ]

    return ValidationResult(
        dataset_name=dataset_name,
        valid_records=valid_records,
        rejected_records=rejected_records,
        input_count=len(dataframe),
    )


def validate_customers(dataframe: pd.DataFrame) -> ValidationResult:
    """Validate customer source records."""
    _check_columns(
        dataframe,
        CUSTOMER_REQUIRED_COLUMNS,
        "customers",
    )

    errors: list[list[str]] = [[] for _ in range(len(dataframe))]

    def add_error(mask: pd.Series, message: str) -> None:
        for position, invalid in enumerate(mask.tolist()):
            if invalid:
                errors[position].append(message)

    customer_ids = dataframe["customer_id"].astype("string").str.strip()

    add_error(
        _is_blank(dataframe["customer_id"]),
        "MISSING_CUSTOMER_ID",
    )

    duplicate_ids = (
        customer_ids.notna()
        & customer_ids.ne("")
        & customer_ids.duplicated(keep="first")
    )
    add_error(duplicate_ids, "DUPLICATE_CUSTOMER_ID")

    add_error(
        _is_blank(dataframe["first_name"]),
        "MISSING_FIRST_NAME",
    )
    add_error(
        _is_blank(dataframe["last_name"]),
        "MISSING_LAST_NAME",
    )

    emails = dataframe["email"].astype("string").str.strip()
    valid_email = emails.str.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        na=False,
    )
    add_error(~valid_email, "INVALID_EMAIL")

    add_error(
        _is_blank(dataframe["city"]),
        "MISSING_CITY",
    )

    return _build_result("customers", dataframe, errors)


def validate_orders(
    dataframe: pd.DataFrame,
    valid_customer_ids: set[str],
) -> ValidationResult:
    """Validate order records and their customer references."""
    _check_columns(
        dataframe,
        ORDER_REQUIRED_COLUMNS,
        "orders",
    )

    errors: list[list[str]] = [[] for _ in range(len(dataframe))]

    def add_error(mask: pd.Series, message: str) -> None:
        for position, invalid in enumerate(mask.tolist()):
            if invalid:
                errors[position].append(message)

    order_ids = dataframe["order_id"].astype("string").str.strip()

    add_error(
        _is_blank(dataframe["order_id"]),
        "MISSING_ORDER_ID",
    )

    duplicate_ids = (
        order_ids.notna()
        & order_ids.ne("")
        & order_ids.duplicated(keep="first")
    )
    add_error(duplicate_ids, "DUPLICATE_ORDER_ID")

    customer_ids = (
        dataframe["customer_id"].astype("string").str.strip()
    )

    add_error(
        _is_blank(dataframe["customer_id"]),
        "MISSING_CUSTOMER_ID",
    )

    invalid_references = (
        customer_ids.notna()
        & customer_ids.ne("")
        & ~customer_ids.isin(valid_customer_ids)
    )
    add_error(
        invalid_references,
        "INVALID_CUSTOMER_REFERENCE",
    )

    amounts = pd.to_numeric(
        dataframe["total_amount"],
        errors="coerce",
    )

    add_error(
        amounts.isna() | (amounts <= 0),
        "INVALID_ORDER_AMOUNT",
    )

    dates = pd.to_datetime(
        dataframe["order_date"],
        format="%Y-%m-%d",
        errors="coerce",
    )

    add_error(
        dates.isna(),
        "INVALID_ORDER_DATE",
    )

    statuses = dataframe["status"].astype("string").str.strip().str.upper()

    invalid_statuses = (
        statuses.isna()
        | statuses.eq("")
        | ~statuses.isin(VALID_ORDER_STATUSES)
    )

    add_error(
        invalid_statuses,
        "INVALID_ORDER_STATUS",
    )

    return _build_result("orders", dataframe, errors)


def validate_dataset(
    dataset_name: str,
    dataframe: pd.DataFrame,
    valid_customer_ids: set[str] | None = None,
) -> ValidationResult:
    """Validate a supported source dataset."""
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("dataframe must be a pandas DataFrame")

    if dataset_name == "customers":
        return validate_customers(dataframe)

    if dataset_name == "orders":
        if valid_customer_ids is None:
            raise ValueError(
                "valid_customer_ids is required to validate orders."
            )

        return validate_orders(dataframe, valid_customer_ids)

    raise ValueError(
        f"Unsupported dataset: {dataset_name}. "
        "Supported datasets: customers, orders."
    )
