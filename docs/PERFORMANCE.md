# DataPulse Performance and Benchmark Evidence

## 1. Purpose

This document records performance measurements for the DataPulse
synthetic data generator and end-to-end pipeline processing.

It includes CSV generation time, output size, pipeline execution time,
database publishing results, and integrity verification.

## 2. Test Environment

| Item | Value |
|---|---|
| Operating system | Windows |
| Python version | 3.14.2 |
| Generator | `datapulse.generator` |
| Random seed | 42 |
| Generation mode | Clean (`--clean`) |
| Rows per dataset | 100,000 |

Hardware specifications were not recorded. Results are specific to the
test environment and are not a hardware-independent guarantee.

## 3. Benchmark Method

The generator was executed with:
- `--count 100000`
- `--seed 42`
- `--clean`
- Separate temporary output and expected-data directories.

PowerShell `Measure-Command` was used to measure execution duration.
The process completed successfully with exit code 0.

## 4. Results

| Dataset | Data rows | Columns | File size (bytes) |
|---|---:|---:|---:|
| customers.csv | 100,000 | 7 | 10,947,648 |
| orders.csv | 100,000 | 8 | 14,817,291 |
| payments.csv | 100,000 | 6 | 10,759,749 |
| products.csv | 100,000 | 6 | 8,015,600 |
| validation_labels.csv | 0 | 5 | 58 |

- Total source rows: 400,000
- Total CSV output size: 44,540,288 bytes (approximately 42.5 MiB).
- Measured generation duration: 12.477 seconds (approximately 12.48 seconds).

The validation labels file contained no data rows because clean generation
was requested. Its header was present.

## 5. Interpretation

The result demonstrates that the synthetic generator created four
100,000-row datasets in approximately 12.48 seconds on the recorded
test environment.

The generator supports configurable row counts, deterministic seeds,
clean generation, and separate output directories.

This result does not prove that the complete DataPulse pipeline can
process 400,000 records in the same time.

## 6. Performance Limitations and Future Work

The end-to-end benchmark establishes measured performance for the
customers and orders datasets, including validation, processing,
and SQLite publishing.

The following remain unmeasured:
- Equivalent end-to-end performance for products and payments.
- Separate timing for individual pipeline stages.
- Peak memory usage.
- Performance under concurrent pipeline execution.
- Performance at larger dataset sizes.

## 7. Reproducibility

The benchmark can be repeated with the same generator options and
fresh output directories. Results may vary with CPU, storage, operating
system, Python version, and system load.

## 8. End-to-End Pipeline Benchmark

### 8.1 Test Configuration

A separate benchmark was executed using:
- 100,000 customer records.
- 100,000 order records.
- Random seed: 42.
- Clean synthetic data generation.
- A fresh, isolated SQLite database.
- Customers processed before orders to satisfy foreign-key dependencies.

The original project database was not used.

### 8.2 Pipeline Results

| Metric | Customers | Orders |
|---|---:|---:|
| Records received | 100,000 | 100,000 |
| Records loaded | 100,000 | 100,000 |
| Records rejected | 0 | 0 |
| Execution time (seconds) | 1.45 | 3.76 |
| Pipeline status | SUCCESS | SUCCESS |

**Total pipeline execution time: 5.21 seconds.**

Total records processed: 200,000.

### 8.3 Database Verification

| Verification | Result |
|---|---:|
| customer_target | 100,000 |
| orders_target | 100,000 |
| pipeline_runs | 2 |
| load_events | 2 |
| quarantine_records | 0 |
| SQLite integrity check | ok |
| Foreign-key violations | 0 |
| Record reconciliation | Passed |

Record reconciliation confirmed:

`records_received = records_loaded + records_rejected`

for both datasets.

### 8.4 Interpretation

The benchmark demonstrates successful end-to-end processing of
200,000 customer and order records in 5.21 seconds in the recorded
test environment.

Both datasets were successfully published to SQLite without rejected
records or foreign-key violations.

These results apply only to the customers and orders pipelines tested.
They do not establish equivalent throughput for products and payments.

Hardware specifications were not recorded. Execution times are
environment-dependent and should not be treated as guaranteed
production performance.


