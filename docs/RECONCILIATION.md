# DataPulse — Data Reconciliation

## 1. Validation Accounting

Every input row is classified as either valid or rejected.

`Records Received = Valid Records + Records Rejected`

- `input_count`: total input rows.
- `valid_count`: rows passing validation.
- `rejected_count`: rows failing validation.

A row with multiple validation errors is counted once as rejected.

## 2. Publishing Accounting

Valid rows are passed to publishing.

- `inserted_count`: newly inserted target records.
- `skipped_count`: records skipped because their primary key already exists.
- Existing target records are not overwritten (`ON CONFLICT DO NOTHING`).

Complete batch reconciliation:

`Records Received = Records Inserted + Records Skipped + Records Rejected`

This applies when processing completes successfully.

## 3. Persisted Metrics

The pipeline_runs and load_events tables store received, loaded and rejected counts.

`records_loaded` / `rows_loaded` counts newly inserted records, not all valid records.

Skipped duplicates are returned by publishing but are not stored in these metric columns. Therefore, persisted metrics alone cannot fully reconcile batches containing skipped duplicates.

For batches without skipped duplicates:

`Records Received = Records Loaded + Records Rejected`

## 4. Quarantine and Traceability

Rejected rows are stored in quarantine_records with dataset, load event, run, source file, original row number, raw record and rejection reason.

## 5. Status Interpretation

- `SUCCESS`: processing completed without validation rejections.
- `PARTIAL`: processing completed with one or more rejected records.
- `FAILED`: processing failed before successful completion.

The current finalization logic sets load_events.status to SUCCESS after processing, even when pipeline_runs.status is PARTIAL. Use pipeline run status and metrics to assess data quality.

## 6. Duplicate Handling

Duplicate identifiers within an input batch are rejected by validation. Identifiers already present in target tables are skipped by publishing.

Customer conflicts use customer_id; order conflicts use order_id.

## 7. Verification

Run the complete suite from the project root:

`pytest -v`

The source-row reconciliation and traceability test is:

`pytest tests/test_pipeline.py::test_source_rows_reconcile_and_rejects_are_traceable -v`
