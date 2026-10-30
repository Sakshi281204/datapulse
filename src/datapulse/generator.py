"""Generate reproducible synthetic CSV datasets for DataPulse."""

from __future__ import annotations

import argparse
import csv
import random
import uuid

from datetime import date, timedelta
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ID_NAMESPACE = uuid.UUID("8f1c4d2a-5b6e-4c90-9a1d-2e7f6b8c3d40")

CUSTOMER_FIELDS = [
    "customer_id", "first_name", "last_name", "email",
    "phone", "city", "created_at",
]

PRODUCT_FIELDS = [
    "product_id", "product_name", "category",
    "unit_price", "stock_quantity", "created_at",
]

ORDER_FIELDS = [
    "order_id", "customer_id", "product_id", "order_date",
    "quantity", "unit_price", "total_amount", "status",
]

PAYMENT_FIELDS = [
    "payment_id", "order_id", "payment_date",
    "amount", "payment_method", "payment_status",
]

LABEL_FIELDS = [
    "dataset", "row_number", "record_id",
    "issue_type", "expected_outcome",
]

FIRST_NAMES = [
    "Aarav", "Aditi", "Ananya", "Arjun", "Diya",
    "Ishaan", "Kavya", "Meera", "Neha", "Rohan",
    "Sakshi", "Vedant", "Vihaan", "Zara",
]

LAST_NAMES = [
    "Sharma", "Patil", "Deshmukh", "Kulkarni",
    "Joshi", "Pawar", "Shinde", "More",
]

CITIES = [
    "Pune", "Mumbai", "Nashik", "Nagpur",
    "Kolhapur", "Satara", "Aurangabad",
]

PRODUCTS = [
    ("Wireless Mouse", "Electronics", 599.00),
    ("Keyboard", "Electronics", 899.00),
    ("Notebook", "Stationery", 79.00),
    ("Water Bottle", "Home", 249.00),
    ("Backpack", "Accessories", 1299.00),
    ("Desk Lamp", "Home", 749.00),
    ("USB Cable", "Electronics", 199.00),
    ("Pen Set", "Stationery", 149.00),
]

ORDER_STATUSES = ["PLACED", "SHIPPED", "DELIVERED", "CANCELLED"]
PAYMENT_METHODS = ["UPI", "CARD", "NET_BANKING", "CASH"]
PAYMENT_STATUSES = ["SUCCESS", "PENDING", "FAILED"]


def deterministic_id(prefix: str, seed: int, index: int) -> str:
    """Return a stable ID for the same entity, seed, and index."""
    value = f"{prefix}|{seed}|{index}"
    generated = uuid.uuid5(ID_NAMESPACE, value)
    return f"{prefix}_{generated.hex}"


def _random_date(rng: random.Random) -> str:
    """Return a reproducible date within the previous year."""
    start = date(2025, 1, 1)
    offset = rng.randint(0, 364)
    return (start + timedelta(days=offset)).isoformat()


def _write_csv(
    path: Path,
    fieldnames: list[str],
    rows: Any,
) -> None:
    """Write rows to CSV one at a time."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_label(
    writer: csv.DictWriter,
    dataset: str,
    index: int,
    record_id: str,
    issue_type: str,
) -> None:
    """Write one expected data-quality issue to the labels CSV."""
    writer.writerow({
        "dataset": dataset,
        "row_number": index + 2,
        "record_id": record_id,
        "issue_type": issue_type,
        "expected_outcome": "INVALID",
    })


def generate_datasets(
    output_dir: Path | str = PROJECT_ROOT / "data" / "sample",
    expected_dir: Path | str = PROJECT_ROOT / "data" / "expected",
    record_count: int = 100,
    seed: int = 42,
    include_invalid: bool = True,
) -> dict[str, Path]:
    """
    Generate customers, products, orders, payments, and validation labels.

    include_invalid=True creates controlled data-quality issues.
    include_invalid=False creates clean datasets only.
    """
    if isinstance(record_count, bool) or record_count < 1:
        raise ValueError("record_count must be a positive integer")

    if not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    output_dir = Path(output_dir)
    expected_dir = Path(expected_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    expected_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)

    paths = {
        "customers": output_dir / "customers.csv",
        "products": output_dir / "products.csv",
        "orders": output_dir / "orders.csv",
        "payments": output_dir / "payments.csv",
        "labels": expected_dir / "validation_labels.csv",
    }

    # Keep the labels outside the source data directory.
    with paths["labels"].open(
        "w", newline="", encoding="utf-8"
    ) as label_file:
        label_writer = csv.DictWriter(
            label_file, fieldnames=LABEL_FIELDS
        )
        label_writer.writeheader()

        # 1. Customers
        def customer_rows():
            for i in range(record_count):
                customer_id = deterministic_id("CUS", seed, i)
                email = (
                    f"customer{i + 1}_{seed}@example.com"
                )
                created_at = _random_date(rng)

                if include_invalid:
                    if i == 1:
                        customer_id = deterministic_id("CUS", seed, 0)
                        _write_label(
                            label_writer, "customers", i,
                            customer_id, "DUPLICATE_CUSTOMER_ID",
                        )
                    if i == 2:
                        email = ""
                        _write_label(
                            label_writer, "customers", i,
                            customer_id, "NULL_EMAIL",
                        )
                    if i == 3:
                        created_at = "not-a-date"
                        _write_label(
                            label_writer, "customers", i,
                            customer_id, "INVALID_CREATED_DATE",
                        )

                yield {
                    "customer_id": customer_id,
                    "first_name": rng.choice(FIRST_NAMES),
                    "last_name": rng.choice(LAST_NAMES),
                    "email": email,
                    "phone": f"9{rng.randint(100000000, 999999999)}",
                    "city": rng.choice(CITIES),
                    "created_at": created_at,
                }

        _write_csv(paths["customers"], CUSTOMER_FIELDS, customer_rows())

        # 2. Products
        def product_rows():
            for i in range(record_count):
                product_id = deterministic_id("PRD", seed, i)
                name, category, price = PRODUCTS[i % len(PRODUCTS)]
                created_at = _random_date(rng)

                if include_invalid:
                    if i == 1:
                        product_id = deterministic_id("PRD", seed, 0)
                        _write_label(
                            label_writer, "products", i,
                            product_id, "DUPLICATE_PRODUCT_ID",
                        )
                    if i == 2:
                        category = ""
                        _write_label(
                            label_writer, "products", i,
                            product_id, "NULL_CATEGORY",
                        )
                    if i == 3:
                        price = -abs(price)
                        _write_label(
                            label_writer, "products", i,
                            product_id, "NEGATIVE_UNIT_PRICE",
                        )
                    if i == 4:
                        created_at = "31-31-2025"
                        _write_label(
                            label_writer, "products", i,
                            product_id, "INVALID_CREATED_DATE",
                        )

                yield {
                    "product_id": product_id,
                    "product_name": name,
                    "category": category,
                    "unit_price": f"{price:.2f}",
                    "stock_quantity": rng.randint(0, 500),
                    "created_at": created_at,
                }

        _write_csv(paths["products"], PRODUCT_FIELDS, product_rows())

        # 3. Orders
        def order_rows():
            for i in range(record_count):
                order_id = deterministic_id("ORD", seed, i)
                customer_ref_index = 0 if include_invalid and i == 1 else i
                product_ref_index = 0 if include_invalid and i == 1 else i

                customer_id = deterministic_id("CUS", seed, customer_ref_index)
                product_id = deterministic_id("PRD", seed, product_ref_index)

                _, _, price = PRODUCTS[product_ref_index % len(PRODUCTS)]
                quantity = (i % 5) + 1      
                total = price * quantity
                order_date = _random_date(rng)
                status = rng.choice(ORDER_STATUSES)

                if include_invalid:
                    if i == 1:
                        order_id = deterministic_id("ORD", seed, 0)
                        _write_label(
                            label_writer, "orders", i,
                            order_id, "DUPLICATE_ORDER_ID",
                        )
                    if i == 2:
                        customer_id = "CUS_INVALID_REFERENCE"
                        _write_label(
                            label_writer, "orders", i,
                            order_id, "INVALID_CUSTOMER_REFERENCE",
                        )
                    if i == 3:
                        product_id = "PRD_INVALID_REFERENCE"
                        _write_label(
                            label_writer, "orders", i,
                            order_id, "INVALID_PRODUCT_REFERENCE",
                        )
                    if i == 4:
                        order_date = "not-a-date"
                        _write_label(
                            label_writer, "orders", i,
                            order_id, "INVALID_ORDER_DATE",
                        )
                    if i == 5:
                        quantity = -2
                        total = price * quantity
                        _write_label(
                            label_writer, "orders", i,
                            order_id, "NEGATIVE_QUANTITY",
                        )
                    if i == 6:
                        status = "UNKNOWN_STATUS"
                        _write_label(
                            label_writer, "orders", i,
                            order_id, "INVALID_ORDER_STATUS",
                        )
                    if i == 7:
                        total = -abs(total)
                        _write_label(
                            label_writer, "orders", i,
                            order_id, "NEGATIVE_TOTAL_AMOUNT",
                        )

                yield {
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "product_id": product_id,
                    "order_date": order_date,
                    "quantity": quantity,
                    "unit_price": f"{price:.2f}",
                    "total_amount": f"{total:.2f}",
                    "status": status,
                }

        _write_csv(paths["orders"], ORDER_FIELDS, order_rows())

        # 4. Payments
        def payment_rows():
            for i in range(record_count):
                payment_id = deterministic_id("PAY", seed, i)
                order_ref_index = 0 if include_invalid and i == 1 else i
                order_id = deterministic_id("ORD", seed, order_ref_index)

                _, _, price = PRODUCTS[order_ref_index % len(PRODUCTS)]
                quantity = -2 if include_invalid and order_ref_index == 5 else (order_ref_index % 5) + 1
                amount = price * quantity

                if include_invalid and order_ref_index == 7:
                    amount = -abs(amount)
                payment_date = _random_date(rng)
                method = rng.choice(PAYMENT_METHODS)
                status = rng.choice(PAYMENT_STATUSES)

                if include_invalid:
                    if i == 1:
                        payment_id = deterministic_id("PAY", seed, 0)
                        _write_label(
                            label_writer, "payments", i,
                            payment_id, "DUPLICATE_PAYMENT_ID",
                        )
                    if i == 2:
                        order_id = "ORD_INVALID_REFERENCE"
                        _write_label(
                            label_writer, "payments", i,
                            payment_id, "INVALID_ORDER_REFERENCE",
                        )
                    if i == 3:
                        amount = -abs(amount)
                        _write_label(
                            label_writer, "payments", i,
                            payment_id, "NEGATIVE_PAYMENT_AMOUNT",
                        )
                    if i == 4:
                        payment_date = "not-a-date"
                        _write_label(
                            label_writer, "payments", i,
                            payment_id, "INVALID_PAYMENT_DATE",
                        )
                    if i == 5:
                        status = "UNKNOWN_STATUS"
                        _write_label(
                            label_writer, "payments", i,
                            payment_id, "INVALID_PAYMENT_STATUS",
                        )
                    if i == 6:
                        method = ""
                        _write_label(
                            label_writer, "payments", i,
                            payment_id, "NULL_PAYMENT_METHOD",
                        )

                yield {
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "payment_date": payment_date,
                    "amount": f"{amount:.2f}",
                    "payment_method": method,
                    "payment_status": status,
                }

        _write_csv(paths["payments"], PAYMENT_FIELDS, payment_rows())

    return paths


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic DataPulse CSV datasets."
    )
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Generate valid data without injected quality issues.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "sample",
    )
    parser.add_argument(
        "--expected-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "expected",
    )

    args = parser.parse_args()

    paths = generate_datasets(
        output_dir=args.output_dir,
        expected_dir=args.expected_dir,
        record_count=args.count,
        seed=args.seed,
        include_invalid=not args.clean,
    )

    print("DataPulse synthetic datasets generated.")
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()