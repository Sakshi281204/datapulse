-- 1. Dataset configurations
SELECT
    dataset_id,
    dataset_name,
    expected_arrival_time,
    timezone,
    arrival_grace_minutes,
    completion_sla_minutes,
    freshness_sla_minutes
FROM datasets
ORDER BY expected_arrival_time;


-- 2. Pipeline execution history
SELECT
    run_id,
    dataset_id,
    source_file,
    started_at,
    completed_at,
    status
FROM pipeline_runs;


-- 3. Load arrival and attempt history
SELECT
    load_event_id,
    dataset_id,
    source_file,
    attempt_number,
    expected_arrival_at,
    actual_arrival_at,
    completion_at,
    status
FROM load_events;


-- 4. Published customers
SELECT * FROM customer_target;


-- 5. Published orders
SELECT * FROM orders_target;


-- 6. Quarantined records
SELECT
    quarantine_id,
    dataset_id,
    source_file,
    row_number,
    rejection_reason
FROM quarantine_records;


-- 7. Alerts
SELECT
    alert_id,
    dataset_id,
    alert_type,
    severity,
    status,
    detected_at
FROM alerts;


-- Check foreign-key integrity
PRAGMA foreign_key_check;


-- Check all indexes
SELECT name, tbl_name
FROM sqlite_master
WHERE type = 'index'
  AND name NOT LIKE 'sqlite_%'
ORDER BY tbl_name, name;