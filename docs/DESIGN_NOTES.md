# Design Notes: Retry, Restart, Backfill, Optimization and Trade-offs

This note explains how DataPulse behaves when things go wrong or run twice,
the one optimization that is implemented, and the main design trade-offs.

## 1. Rerun, retry, restart and backfill

- **Rerun of the same file:** every execution gets a new `run_id` and load
  event. Target inserts use `ON CONFLICT DO NOTHING` on the primary key, so a
  rerun inserts 0 new rows and reports the rows as skipped.
  Test: `test_customer_pipeline_rerun_does_not_duplicate_records`.
- **Retry after a failed run:** failed attempts are never overwritten. Each
  attempt keeps its own run and load event with `FAILED` status and the error
  message, and a retry creates a new run with the next attempt number.
  Tests: `test_pipeline_recovers_after_failed_ingestion`,
  `test_retry_gets_attempt_number_two`.
- **Failure during processing:** the transaction is rolled back so no partial
  target rows remain. The `FAILED` status and error message are then written
  on a separate connection so the failure record survives the rollback.
  Test: `test_pipeline_rolls_back_when_publishing_fails`.
- **Interrupted run (for example Ctrl+C):** an interruption that bypasses the
  normal failure handler leaves that run as `RUNNING` and its load event as
  `ARRIVED`; they are not marked `FAILED`. No partial target rows remain. A
  restart of the same file creates attempt 2 and completes normally, and the
  stale `RUNNING` row stays as history. Marking stale runs as failed after a
  timeout is a next step. Test:
  `test_pipeline_restarts_safely_after_interrupted_run`.
- **Backfill:** a later file with overlapping IDs is additive. New IDs are
  inserted and existing IDs are skipped, never overwritten (first write wins).
  Test: `test_backfill_file_is_additive_and_never_overwrites_customers`.
- **Unexpected schema change:** a source file with unexpected columns fails the
  whole run with `FAILED` status and the error recorded, and loads no rows.
  Tests: `test_unexpected_customer_column_is_rejected`,
  `test_pipeline_fails_on_unexpected_schema_change`.

## 2. Optimization

Target publishing uses batched `executemany` inserts inside one transaction
per run, committed once, instead of one INSERT and commit per row. This limits
per-row overhead and keeps the load atomic. A separate row-by-row comparison
was not benchmarked, so no speedup figure is claimed for it.

## 3. Trade-offs

- **First write wins:** `ON CONFLICT DO NOTHING` makes reruns and backfills
  safe, but a corrected record for an existing ID is skipped, not applied.
- **Schema change fails the batch:** unexpected columns signal an upstream
  contract change, so the batch fails loudly instead of quarantining every
  row. The cost is that a harmless extra column also blocks the load.
- **History is kept in control tables:** `pipeline_runs`, `load_events` and
  quarantine records preserve attempts and rejects rather than overwriting.
- **SQLite and pandas:** chosen for a reproducible local setup. Files are read
  fully into memory and SQLite has a single writer, which limits scale.
- **SLA checks are separate from the dashboard:** refreshing the dashboard
  never changes alert state.
- **Expected loads come from dataset configuration:** there is no separate
  expected-loads table, so a missing file is detected from the schedule and
  grace period, but per-day expected-load history is not stored.

## 4. Known limitations and next steps

- Products and payments are generated and registered for SLA monitoring but
  are not processed by the end-to-end pipeline.
- Pipeline failures are recorded in `pipeline_runs` and `load_events`; alerts
  come from the SLA monitor (missing, late, stale and completion checks).
  Raising an alert directly on a pipeline failure is a next step.
- Changed values for existing IDs are skipped. Tracking them as history is a
  next step.
- Next steps: process products and payments, read large files in chunks,
  schedule the SLA checks, mark stale RUNNING runs as failed, and benchmark
  batched versus row-by-row inserts.
