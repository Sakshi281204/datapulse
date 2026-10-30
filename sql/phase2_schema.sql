PRAGMA foreign_keys = ON;

-- 1. Dataset configuration and SLA definitions
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id TEXT PRIMARY KEY,
    dataset_name TEXT NOT NULL UNIQUE,
    source_system TEXT NOT NULL,
    source_path TEXT NOT NULL,

    expected_arrival_time TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',

    arrival_grace_minutes INTEGER NOT NULL DEFAULT 15
        CHECK (arrival_grace_minutes >= 0),

    completion_sla_minutes INTEGER NOT NULL
        CHECK (completion_sla_minutes > 0),

    freshness_sla_minutes INTEGER NOT NULL
        CHECK (freshness_sla_minutes > 0),

    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);


-- 2. Pipeline execution history
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    source_file TEXT NOT NULL,

    started_at TEXT NOT NULL,
    completed_at TEXT,

    status TEXT NOT NULL
        CHECK (
            status IN (
                'RUNNING',
                'SUCCESS',
                'FAILED',
                'PARTIAL'
            )
        ),

    records_received INTEGER NOT NULL DEFAULT 0
        CHECK (records_received >= 0),

    records_loaded INTEGER NOT NULL DEFAULT 0
        CHECK (records_loaded >= 0),

    records_rejected INTEGER NOT NULL DEFAULT 0
        CHECK (records_rejected >= 0),

    error_message TEXT,

    FOREIGN KEY (dataset_id)
        REFERENCES datasets(dataset_id),

    CHECK (
        completed_at IS NULL
        OR completed_at >= started_at
    )
);


-- 3. Historical load arrival and processing attempts
CREATE TABLE IF NOT EXISTS load_events (
    load_event_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    run_id TEXT NOT NULL,

    source_file TEXT NOT NULL,
    attempt_number INTEGER NOT NULL
        CHECK (attempt_number >= 1),

    expected_arrival_at TEXT NOT NULL,
    actual_arrival_at TEXT,
    completion_at TEXT,

    status TEXT NOT NULL
        CHECK (
            status IN (
                'EXPECTED',
                'ARRIVED',
                'PROCESSING',
                'SUCCESS',
                'FAILED',
                'LATE',
                'MISSING'
            )
        ),

    rows_received INTEGER NOT NULL DEFAULT 0
        CHECK (rows_received >= 0),

    rows_loaded INTEGER NOT NULL DEFAULT 0
        CHECK (rows_loaded >= 0),

    rows_rejected INTEGER NOT NULL DEFAULT 0
        CHECK (rows_rejected >= 0),

    error_message TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (dataset_id)
        REFERENCES datasets(dataset_id),

    FOREIGN KEY (run_id)
        REFERENCES pipeline_runs(run_id),

    UNIQUE (dataset_id, source_file, attempt_number),

    CHECK (
        completion_at IS NULL
        OR actual_arrival_at IS NULL
        OR completion_at >= actual_arrival_at
    )
);


-- 4. Successfully published customer records
CREATE TABLE IF NOT EXISTS customer_target (
    customer_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    email TEXT,

    source_event_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    source_file TEXT NOT NULL,

    loaded_at TEXT NOT NULL,

    FOREIGN KEY (source_event_id)
        REFERENCES load_events(load_event_id),

    FOREIGN KEY (run_id)
        REFERENCES pipeline_runs(run_id)
);


-- 5. Successfully published order records
CREATE TABLE IF NOT EXISTS orders_target (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,

    order_date TEXT NOT NULL,
    amount REAL NOT NULL
        CHECK (amount >= 0),

    order_status TEXT NOT NULL,

    source_event_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    source_file TEXT NOT NULL,

    loaded_at TEXT NOT NULL,

    FOREIGN KEY (customer_id)
        REFERENCES customer_target(customer_id),

    FOREIGN KEY (source_event_id)
        REFERENCES load_events(load_event_id),

    FOREIGN KEY (run_id)
        REFERENCES pipeline_runs(run_id)
);


-- 6. Rejected records and validation details
CREATE TABLE IF NOT EXISTS quarantine_records (
    quarantine_id TEXT PRIMARY KEY,

    dataset_id TEXT NOT NULL,
    load_event_id TEXT NOT NULL,
    run_id TEXT NOT NULL,

    source_file TEXT NOT NULL,
    row_number INTEGER NOT NULL
        CHECK (row_number >= 1),

    record_key TEXT,
    raw_record_json TEXT NOT NULL,
    rejection_reason TEXT NOT NULL,

    created_at TEXT NOT NULL,

    FOREIGN KEY (dataset_id)
        REFERENCES datasets(dataset_id),

    FOREIGN KEY (load_event_id)
        REFERENCES load_events(load_event_id),

    FOREIGN KEY (run_id)
        REFERENCES pipeline_runs(run_id),

    UNIQUE (load_event_id, row_number, rejection_reason)
);


-- 7. Operational and SLA alerts
CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,

    dataset_id TEXT NOT NULL,
    load_event_id TEXT,
    run_id TEXT,

    alert_type TEXT NOT NULL
        CHECK (
            alert_type IN (
                'MISSING_LOAD',
                'LATE_ARRIVAL',
                'COMPLETION_SLA_BREACH',
                'FRESHNESS_BREACH',
                'PIPELINE_FAILURE',
                'DATA_QUALITY_FAILURE'
            )
        ),

    severity TEXT NOT NULL
        CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),

    message TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')),

    detected_at TEXT NOT NULL,
    resolved_at TEXT,

    fingerprint TEXT NOT NULL UNIQUE,

    FOREIGN KEY (dataset_id)
        REFERENCES datasets(dataset_id),

    FOREIGN KEY (load_event_id)
        REFERENCES load_events(load_event_id),

    FOREIGN KEY (run_id)
        REFERENCES pipeline_runs(run_id),

    CHECK (
        resolved_at IS NULL
        OR resolved_at >= detected_at
    )
);


-- Indexes for common monitoring and dashboard queries
CREATE INDEX IF NOT EXISTS idx_runs_dataset_started
    ON pipeline_runs(dataset_id, started_at);

CREATE INDEX IF NOT EXISTS idx_runs_status
    ON pipeline_runs(status);

CREATE INDEX IF NOT EXISTS idx_loads_dataset_expected
    ON load_events(dataset_id, expected_arrival_at);

CREATE INDEX IF NOT EXISTS idx_loads_status
    ON load_events(status);

CREATE INDEX IF NOT EXISTS idx_loads_run
    ON load_events(run_id);

CREATE INDEX IF NOT EXISTS idx_customers_source_event
    ON customer_target(source_event_id);

CREATE INDEX IF NOT EXISTS idx_orders_customer
    ON orders_target(customer_id);

CREATE INDEX IF NOT EXISTS idx_orders_source_event
    ON orders_target(source_event_id);

CREATE INDEX IF NOT EXISTS idx_quarantine_dataset_created
    ON quarantine_records(dataset_id, created_at);

CREATE INDEX IF NOT EXISTS idx_alerts_status_detected
    ON alerts(status, detected_at);

CREATE INDEX IF NOT EXISTS idx_alerts_dataset
    ON alerts(dataset_id);