# DataPulse Data Dictionary

## 1. Purpose

This document describes the source datasets, implemented validation rules,
transformations, operational database tables, and pipeline metadata.

Source CSV values are initially read as tabular data by Pandas. The database
types below describe the SQLite schema, not necessarily the original CSV
storage representation.

## 2. Source CSV datasets

### 2.1 Customers — customers.csv

| Column | Meaning | Validation |
|---|---|---|
| customer_id | Unique customer identifier | Required; duplicates rejected |
| first_name | Customer first name | Required; cannot be blank |
| last_name | Customer last name | Required; cannot be blank |
| email | Customer email address | Required; must match email pattern |
| phone | Customer phone number | Generated; not currently validated by the pipeline |
| city | Customer city | Required; cannot be blank |
| created_at | Customer creation date | Generated; not currently validated by the pipeline |

### 2.2 Products — products.csv

| Column | Meaning |
|---|---|
| product_id | Product identifier |
| product_name | Product name |
| category | Product category |
| unit_price | Product unit price |
| stock_quantity | Available stock quantity |
| created_at | Product creation date |

Products are generated as synthetic data. They are not currently processed
by the end-to-end publishing pipeline.

### 2.3 Orders — orders.csv

| Column | Meaning | Validation |
|---|---|---|
| order_id | Unique order identifier | Required; duplicates rejected |
| customer_id | Customer associated with the order | Required; must exist in published customers |
| product_id | Product associated with the order | Generated; not currently validated by the pipeline |
| order_date | Date of the order | Required; must use YYYY-MM-DD |
| quantity | Number of units ordered | Generated; not independently validated by the current pipeline |
| unit_price | Price per unit | Generated; not independently validated by the current pipeline |
| total_amount | Total order amount | Required; must be numeric and greater than zero |
| status | Order status | Required; must be PLACED, SHIPPED, DELIVERED, or CANCELLED |

### 2.4 Payments — payments.csv

| Column | Meaning |
|---|---|
| payment_id | Payment identifier |
| order_id | Associated order identifier |
| payment_date | Payment date |
| amount | Payment amount |
| payment_method | Payment method |
| payment_status | Payment status |

Payments are generated as synthetic data. They are not currently processed
by the end-to-end publishing pipeline.

## 3. Validation and transformation rules

### Customers

- Reject blank customer IDs.
- Reject duplicate customer IDs within the input batch.
- Reject blank first names and last names.
- Reject missing or invalid email addresses.
- Reject blank city values.
- Combine first_name and last_name into customer_name.
- Trim and normalize whitespace in text values.
- Convert email addresses to lowercase.

### Orders

- Reject blank order IDs and duplicate order IDs within the input batch.
- Reject blank customer IDs.
- Reject customer references that do not exist in published customer records.
- Reject non-numeric, missing, zero, or negative total_amount values.
- Reject invalid order dates.
- Accept only PLACED, SHIPPED, DELIVERED, and CANCELLED statuses.
- Normalize text and uppercase order status.
- Convert total_amount to the published numeric amount field.

### Schema validation boundary

The validator checks that all required columns are present and rejects
unexpected columns for the supported customers and orders datasets.

Known optional source columns are allowed:
- Customers: phone, created_at
- Orders: product_id, quantity, unit_price

The allowed column sets are explicitly defined in the validation module.
A new or misspelled column causes a clear schema error before row-level
validation. The project does not yet use externally versioned schema files.

## 4. Published target tables

### customer_target

| Column | SQLite type | Meaning |
|---|---|---|
| customer_id | TEXT | Primary key |
| customer_name | TEXT | Combined customer name |
| email | TEXT | Normalized email |
| source_event_id | TEXT | Related load event |
| run_id | TEXT | Pipeline execution identifier |
| source_file | TEXT | Source CSV file |
| loaded_at | TEXT | Publication timestamp |

### orders_target

| Column | SQLite type | Meaning |
|---|---|---|
| order_id | TEXT | Primary key |
| customer_id | TEXT | Foreign key to customer_target |
| order_date | TEXT | Standardized order date |
| amount | REAL | Published order amount |
| order_status | TEXT | Normalized order status |
| source_event_id | TEXT | Related load event |
| run_id | TEXT | Pipeline execution identifier |
| source_file | TEXT | Source CSV file |
| loaded_at | TEXT | Publication timestamp |

The current publishing implementation inserts new records and skips records
whose primary keys already exist. It does not overwrite existing records.

## 5. Operational database tables

The operational database is `data/datapulse_phase2.db`.

### datasets

| Column | SQLite type | Meaning |
|---|---|---|
| dataset_id | TEXT | Primary key |
| dataset_name | TEXT | Unique dataset name |
| source_system | TEXT | Source system identifier |
| source_path | TEXT | Configured source path |
| expected_arrival_time | TEXT | Expected local arrival time |
| timezone | TEXT | Dataset timezone |
| arrival_grace_minutes | INTEGER | Allowed arrival delay |
| completion_sla_minutes | INTEGER | Processing completion SLA |
| freshness_sla_minutes | INTEGER | Freshness threshold |
| is_active | INTEGER | Active/inactive flag |
| created_at | TEXT | Creation timestamp |
| updated_at | TEXT | Last update timestamp |

### pipeline_runs

| Column | SQLite type | Meaning |
|---|---|---|
| run_id | TEXT | Primary key |
| dataset_id | TEXT | Related dataset |
| source_file | TEXT | Input file |
| started_at | TEXT | Run start timestamp |
| completed_at | TEXT | Run completion timestamp |
| status | TEXT | RUNNING, SUCCESS, FAILED, or PARTIAL |
| records_received | INTEGER | Records read for processing |
| records_loaded | INTEGER | Records successfully inserted |
| records_rejected | INTEGER | Records rejected by validation |
| error_message | TEXT | Failure details, if any |

**Metric interpretation:** A run created during ingestion may have a `SUCCESS` status even though publishing has not yet occurred. In that case, `records_loaded` and `records_rejected` can both be zero. For completed processing runs, the expected reconciliation is `records_received = records_loaded + records_rejected`. Existing target records skipped because of duplicate IDs are not counted as newly loaded.

### load_events

| Column | SQLite type | Meaning |
|---|---|---|
| load_event_id | TEXT | Primary key |
| dataset_id | TEXT | Related dataset |
| run_id | TEXT | Related pipeline run |
| source_file | TEXT | Source file |
| attempt_number | INTEGER | Attempt number for this file |
| expected_arrival_at | TEXT | Expected arrival timestamp |
| actual_arrival_at | TEXT | Actual arrival timestamp |
| completion_at | TEXT | Processing completion timestamp |
| status | TEXT | Arrival and processing status |
| rows_received | INTEGER | Rows received |
| rows_loaded | INTEGER | Rows loaded |
| rows_rejected | INTEGER | Rows rejected |
| error_message | TEXT | Error details |
| created_at | TEXT | Event creation timestamp |

A unique constraint applies to dataset_id, source_file, and attempt_number.

### quarantine_records

| Column | SQLite type | Meaning |
|---|---|---|
| quarantine_id | TEXT | Primary key |
| dataset_id | TEXT | Related dataset |
| load_event_id | TEXT | Related load event |
| run_id | TEXT | Related pipeline run |
| source_file | TEXT | Original source file |
| row_number | INTEGER | Original CSV row number |
| record_key | TEXT | Record identifier, when available |
| raw_record_json | TEXT | Original rejected record |
| rejection_reason | TEXT | Validation rejection reason |
| created_at | TEXT | Quarantine timestamp |

### alerts

| Column | SQLite type | Meaning |
|---|---|---|
| alert_id | TEXT | Primary key |
| dataset_id | TEXT | Related dataset |
| load_event_id | TEXT | Related load event, if applicable |
| run_id | TEXT | Related pipeline run, if applicable |
| alert_type | TEXT | Type of SLA or pipeline alert |
| severity | TEXT | LOW, MEDIUM, HIGH, or CRITICAL |
| message | TEXT | Alert description |
| status | TEXT | OPEN, ACKNOWLEDGED, or RESOLVED |
| detected_at | TEXT | Detection timestamp |
| resolved_at | TEXT | Resolution timestamp |
| fingerprint | TEXT | Unique alert fingerprint |

## 6. Data lineage and traceability

Pipeline records use run_id and source_file to identify an execution and its
input. Load events preserve individual attempts. Published and quarantined
records retain references to their originating load event and pipeline run.

This supports investigation of which file and execution produced a record
or caused a rejection.

## 7. Important scope boundaries

- End-to-end publishing currently supports customers and orders.
- Products and payments are generated but are not end-to-end pipeline targets.
- Order product_id, quantity, and unit_price are not independently validated
  by the current order validator.
- SLA checks are manually triggered.
- The operational database is local SQLite.
- Unexpected source columns are rejected; schema definitions are maintained
  in Python rather than external versioned schema files.

## 8. Database constraints and indexes
### 8.1 Primary and unique constraints

All seven database tables have primary keys.

Additional unique constraints:
- `datasets.dataset_name`
- `load_events(dataset_id, source_file, attempt_number)`
- `quarantine_records(load_event_id, row_number, rejection_reason)`
- `alerts.fingerprint`

These constraints prevent duplicate dataset names, repeated load attempts,
duplicate quarantine entries for the same row and reason, and duplicate alerts.

### 8.2 Foreign-key relationships

- `pipeline_runs.dataset_id` references `datasets.dataset_id`.
- `load_events.dataset_id` references `datasets.dataset_id`.
- `load_events.run_id` references `pipeline_runs.run_id`.
- `customer_target.source_event_id` references `load_events.load_event_id`.
- `customer_target.run_id` references `pipeline_runs.run_id`.
- `orders_target.customer_id` references `customer_target.customer_id`.
- `orders_target.source_event_id` references `load_events.load_event_id`.
- `orders_target.run_id` references `pipeline_runs.run_id`.
- `quarantine_records.dataset_id` references `datasets.dataset_id`.
- `quarantine_records.load_event_id` references `load_events.load_event_id`.
- `quarantine_records.run_id` references `pipeline_runs.run_id`.
- `alerts.dataset_id` references `datasets.dataset_id`.
- `alerts.load_event_id` references `load_events.load_event_id`.
- `alerts.run_id` references `pipeline_runs.run_id`.

SQLite foreign-key enforcement is enabled for database connections.

### 8.3 CHECK constraints

The schema enforces the following rules:

- Dataset arrival grace must be non-negative.
- Completion and freshness SLA durations must be positive.
- Dataset active status must be 0 or 1.
- Pipeline run status must be RUNNING, SUCCESS, FAILED, or PARTIAL.
- Pipeline record counters must be non-negative.
- Pipeline completion cannot precede its start.
- Load attempt numbers must be at least 1.
- Load-event status must be EXPECTED, ARRIVED, PROCESSING, SUCCESS, FAILED, LATE, or MISSING.
- Load-event record counters must be non-negative.
- Load completion cannot precede actual arrival when both timestamps exist.
- Published order amount must be non-negative.
- Quarantine row numbers must be at least 1.
- Alert type, severity, and status must use their defined allowed values.
- Alert resolution cannot precede detection.

The source validation rule for order total_amount is stricter than the
database constraint: source values must be greater than zero, while the
published database column permits zero or greater.

### 8.4 Database indexes

The schema creates 11 indexes for common monitoring, filtering, and
relationship queries:

| Index | Table | Indexed columns |
|---|---|---|
| idx_runs_dataset_started | pipeline_runs | dataset_id, started_at |
| idx_runs_status | pipeline_runs | status |
| idx_loads_dataset_expected | load_events | dataset_id, expected_arrival_at |
| idx_loads_status | load_events | status |
| idx_loads_run | load_events | run_id |
| idx_customers_source_event | customer_target | source_event_id |
| idx_orders_customer | orders_target | customer_id |
| idx_orders_source_event | orders_target | source_event_id |
| idx_quarantine_dataset_created | quarantine_records | dataset_id, created_at |
| idx_alerts_status_detected | alerts | status, detected_at |
| idx_alerts_dataset | alerts | dataset_id |

