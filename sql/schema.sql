-- DataPulse control-plane schema. Safe to run repeatedly (IF NOT EXISTS).
-- All timestamps are stored as text: 'YYYY-MM-DD HH:MM:SS' in the pipeline's single timezone.

-- 1. Which datasets we monitor and what "on time" means for each.
CREATE TABLE IF NOT EXISTS dataset_registry (
    dataset_id                 TEXT PRIMARY KEY,
    description                TEXT,
    frequency                  TEXT NOT NULL CHECK (frequency IN ('DAILY')),
    expected_arrival_time      TEXT NOT NULL,
    sla_deadline_time          TEXT NOT NULL,
    freshness_threshold_hours  INTEGER NOT NULL CHECK (freshness_threshold_hours > 0),
    file_pattern               TEXT NOT NULL,
    target_table               TEXT NOT NULL,
    business_key               TEXT NOT NULL,
    is_active                  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at                 TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                 TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (expected_arrival_time < sla_deadline_time)
);

-- 2. Data quality rules attached to a dataset.
CREATE TABLE IF NOT EXISTS dq_rules (
    rule_id      TEXT PRIMARY KEY,
    dataset_id   TEXT NOT NULL REFERENCES dataset_registry (dataset_id),
    column_name  TEXT NOT NULL,
    rule_type    TEXT NOT NULL CHECK (rule_type IN
                    ('not_null', 'unique', 'range', 'regex', 'allowed_values')),
    rule_params  TEXT,
    severity     TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (severity IN
                    ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    is_active    INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

-- 3. One row per load attempt. Never deleted.
CREATE TABLE IF NOT EXISTS load_history (
    run_id          TEXT PRIMARY KEY,
    dataset_id      TEXT NOT NULL REFERENCES dataset_registry (dataset_id),
    batch_date      TEXT NOT NULL,
    attempt_no      INTEGER NOT NULL CHECK (attempt_no >= 1),
    file_name       TEXT NOT NULL,
    file_hash       TEXT NOT NULL,
    arrival_ts      TEXT,
    completion_ts   TEXT,
    status          TEXT NOT NULL CHECK (status IN
                       ('SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'SKIPPED_DUPLICATE')),
    rows_read       INTEGER NOT NULL DEFAULT 0,
    rows_loaded     INTEGER NOT NULL DEFAULT 0,
    rows_rejected   INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (dataset_id, batch_date, file_hash, attempt_no)
);
CREATE INDEX IF NOT EXISTS idx_load_history_dataset_batch
    ON load_history (dataset_id, batch_date);

-- 4. Every rejected row, kept forever.
CREATE TABLE IF NOT EXISTS rejected_records (
    reject_id          TEXT PRIMARY KEY,
    run_id             TEXT NOT NULL REFERENCES load_history (run_id),
    dataset_id         TEXT NOT NULL REFERENCES dataset_registry (dataset_id),
    source_row_number  INTEGER NOT NULL,
    raw_record         TEXT NOT NULL,
    rule_name          TEXT NOT NULL,
    reject_reason      TEXT NOT NULL,
    rejected_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (run_id, source_row_number, rule_name)
);

-- 5. Outcome of each rule in each run.
CREATE TABLE IF NOT EXISTS dq_results (
    run_id        TEXT NOT NULL REFERENCES load_history (run_id),
    rule_id       TEXT NOT NULL REFERENCES dq_rules (rule_id),
    rows_checked  INTEGER NOT NULL,
    rows_failed   INTEGER NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('PASSED', 'FAILED')),
    PRIMARY KEY (run_id, rule_id)
);

-- 6. Daily SLA verdict per dataset.
CREATE TABLE IF NOT EXISTS sla_status (
    dataset_id            TEXT NOT NULL REFERENCES dataset_registry (dataset_id),
    batch_date            TEXT NOT NULL,
    expected_arrival_ts   TEXT NOT NULL,
    actual_arrival_ts     TEXT,
    sla_deadline_ts       TEXT NOT NULL,
    actual_completion_ts  TEXT,
    sla_status            TEXT NOT NULL CHECK (sla_status IN
                             ('ON_TIME', 'LATE_ARRIVAL', 'SLA_BREACH', 'MISSING', 'PENDING')),
    delay_minutes         INTEGER NOT NULL DEFAULT 0,
    evaluated_at          TEXT NOT NULL,
    PRIMARY KEY (dataset_id, batch_date)
);

-- 7. Actionable alerts, deduplicated by dedupe_key.
CREATE TABLE IF NOT EXISTS alerts (
    alert_id            TEXT PRIMARY KEY,
    dedupe_key          TEXT NOT NULL UNIQUE,
    dataset_id          TEXT NOT NULL REFERENCES dataset_registry (dataset_id),
    batch_date          TEXT NOT NULL,
    alert_type          TEXT NOT NULL CHECK (alert_type IN
                           ('MISSING_LOAD', 'LATE_LOAD', 'STALE_DATA', 'DQ_FAILURE', 'LOAD_FAILED')),
    severity            TEXT NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    message             TEXT NOT NULL,
    recommended_action  TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'RESOLVED')),
    created_at          TEXT NOT NULL,
    resolved_at         TEXT
);