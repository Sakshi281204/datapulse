import streamlit as st

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from datapulse.database import get_connection


st.set_page_config(
    page_title="DataPulse",
    page_icon="DP",
    layout="wide",
)

st.title("DataPulse")
st.subheader("Automated Data Pipeline Monitoring and SLA Management")
st.caption("Live overview from the existing DataPulse SQLite database.")

st.divider()


def get_table_count(connection, table_name):
    """Return the number of records in a database table."""
    result = connection.execute(
        f"SELECT COUNT(*) FROM {table_name}"
    ).fetchone()

    return result[0]


def parse_timestamp(value):
    """Parse a timezone-aware ISO timestamp."""
    if not value:
        return None

    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include timezone information.")

    return parsed.astimezone(timezone.utc)


def display_timestamp(value, dataset_timezone):
    """Format timestamps in the dataset's configured timezone."""
    parsed = parse_timestamp(value)

    if parsed is None:
        return "Not available"

    return parsed.astimezone(
        ZoneInfo(dataset_timezone)
    ).strftime("%Y-%m-%d %H:%M:%S")


try:
    connection = get_connection()

    counts = {
        "Datasets": get_table_count(connection, "datasets"),
        "Pipeline Runs": get_table_count(connection, "pipeline_runs"),
        "Load Events": get_table_count(connection, "load_events"),
        "Customer Records": get_table_count(connection, "customer_target"),
        "Order Records": get_table_count(connection, "orders_target"),
        "Quarantined Records": get_table_count(connection, "quarantine_records"),
        "Alerts": get_table_count(connection, "alerts"),
    }

    recent_runs = connection.execute(
        """
        SELECT
            run_id,
            dataset_id,
            source_file,
            started_at,
            completed_at,
            status,
            records_received,
            records_loaded,
            records_rejected
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT 20
        """
    ).fetchall()

    datasets = connection.execute(
        """
        SELECT
            dataset_id,
            dataset_name,
            expected_arrival_time,
            timezone,
            arrival_grace_minutes,
            completion_sla_minutes,
            freshness_sla_minutes,
            is_active
        FROM datasets
        ORDER BY dataset_id
        """
    ).fetchall()

    current_time = datetime.now(timezone.utc)
    sla_rows = []

    for dataset in datasets:
        dataset_id = dataset["dataset_id"]
        dataset_timezone = dataset["timezone"]
        local_timezone = ZoneInfo(dataset_timezone)

        latest_event = connection.execute(
            """
            SELECT
                load_event_id,
                expected_arrival_at,
                actual_arrival_at,
                completion_at,
                status,
                rows_loaded
            FROM load_events
            WHERE dataset_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (dataset_id,),
        ).fetchone()

        latest_success = connection.execute(
            """
            SELECT completion_at
            FROM load_events
            WHERE dataset_id = ?
              AND completion_at IS NOT NULL
              AND rows_loaded > 0
              AND status IN ('SUCCESS', 'LATE')
            ORDER BY completion_at DESC
            LIMIT 1
            """,
            (dataset_id,),
        ).fetchone()

        arrival_status = "No load event"
        actual_arrival = "Not available"
        completion_status = "Not available"
        completion_duration = "Not available"

        if latest_event:
            expected = parse_timestamp(
                latest_event["expected_arrival_at"]
            )

            actual = parse_timestamp(
                latest_event["actual_arrival_at"]
            )

            if expected:
                deadline = expected + timedelta(
                    minutes=dataset["arrival_grace_minutes"]
                )

                if actual:
                    actual_arrival = display_timestamp(
                        latest_event["actual_arrival_at"],
                        dataset_timezone,
                    )

                    arrival_status = (
                        "ON TIME" if actual <= deadline else "LATE"
                    )
                else:
                    arrival_status = (
                        "MISSING" if current_time > deadline
                        else "AWAITING"
                    )

            completed = parse_timestamp(
                latest_event["completion_at"]
            )

            if actual and completed:
                duration = (
                    completed - actual
                ).total_seconds() / 60

                completion_duration = round(duration, 2)

                completion_status = (
                    "WITHIN SLA"
                    if duration <= dataset["completion_sla_minutes"]
                    else "BREACHED"
                )

        freshness_status = "NO SUCCESSFUL LOAD"
        freshness_age = "Not available"

        if latest_success:
            completed = parse_timestamp(
                latest_success["completion_at"]
            )

            age = (
                current_time - completed
            ).total_seconds() / 60

            freshness_age = round(age, 2)

            freshness_status = (
                "FRESH"
                if age <= dataset["freshness_sla_minutes"]
                else "STALE"
            )

        sla_rows.append({
            "Dataset": dataset["dataset_name"],
            "Expected Arrival": dataset["expected_arrival_time"],
            "Grace (min)": dataset["arrival_grace_minutes"],
            "Actual Arrival": actual_arrival,
            "Arrival Status": arrival_status,
            "Completion Duration (min)": completion_duration,
            "Completion SLA": completion_status,
            "Freshness Age (min)": freshness_age,
            "Freshness Status": freshness_status,
            "Active": bool(dataset["is_active"]),
        })


    quality_summary = connection.execute(
        """
        SELECT
            d.dataset_name,
            COUNT(le.load_event_id) AS load_attempts,
            COALESCE(SUM(le.rows_received), 0) AS records_received,
            COALESCE(SUM(le.rows_loaded), 0) AS records_loaded,
            COALESCE(SUM(le.rows_rejected), 0) AS records_rejected
        FROM datasets d
        LEFT JOIN load_events le
            ON d.dataset_id = le.dataset_id
        GROUP BY d.dataset_id, d.dataset_name
        ORDER BY d.dataset_name
        """
    ).fetchall()

    rejection_breakdown = connection.execute(
        """
        SELECT
            d.dataset_name,
            q.rejection_reason,
            COUNT(*) AS rejected_records
        FROM quarantine_records q
        JOIN datasets d
            ON q.dataset_id = d.dataset_id
        GROUP BY d.dataset_name, q.rejection_reason
        ORDER BY rejected_records DESC
        """
    ).fetchall()

    recent_quarantine = connection.execute(
        """
        SELECT
            d.dataset_name,
            q.source_file,
            q.row_number,
            q.record_key,
            q.rejection_reason,
            q.created_at
        FROM quarantine_records q
        JOIN datasets d
            ON q.dataset_id = d.dataset_id
        ORDER BY q.created_at DESC
        LIMIT 50
        """
    ).fetchall()
    recent_quarantine = connection.execute(
        """
        SELECT
            d.dataset_name,
            q.source_file,
            q.row_number,
            q.record_key,
            q.rejection_reason,
            q.created_at
        FROM quarantine_records q
        JOIN datasets d
            ON q.dataset_id = d.dataset_id
        ORDER BY q.created_at DESC
        LIMIT 50
        """
    ).fetchall()
    alert_summary = connection.execute(
        """
        SELECT
            severity,
            status,
            COUNT(*) AS alert_count
        FROM alerts
        GROUP BY severity, status
        ORDER BY severity, status
        """
    ).fetchall()

    recent_alerts = connection.execute(
        """
        SELECT
            d.dataset_name,
            a.alert_type,
            a.severity,
            a.message,
            a.status,
            a.detected_at,
            a.resolved_at
        FROM alerts a
        JOIN datasets d
            ON a.dataset_id = d.dataset_id
        ORDER BY a.detected_at DESC
        LIMIT 50
        """
    ).fetchall()
    connection.close()

    st.subheader("Pipeline Overview")

    first_row = st.columns(4)

    first_row[0].metric("Datasets", counts["Datasets"])
    first_row[1].metric("Pipeline Runs", counts["Pipeline Runs"])
    first_row[2].metric("Load Events", counts["Load Events"])
    first_row[3].metric("Total Alerts", counts["Alerts"])

    second_row = st.columns(3)

    second_row[0].metric("Customer Records", counts["Customer Records"])
    second_row[1].metric("Order Records", counts["Order Records"])
    second_row[2].metric("Quarantined Records", counts["Quarantined Records"])

    st.success("Database connection successful.")

    st.divider()

    st.subheader("Recent Pipeline Runs")

    if recent_runs:
        st.dataframe(
            [dict(row) for row in recent_runs],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No pipeline runs found.")

    st.divider()

    st.subheader("Dataset SLA Monitoring")

    st.caption(
        "SLA statuses are calculated for display only. "
        "Opening this dashboard does not execute SLA checks or create alerts."
    )

    if sla_rows:
        st.dataframe(
            sla_rows,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No datasets configured.")
        st.divider()

    st.subheader("Data Quality Monitoring")

    total_received = sum(
        row["records_received"] for row in quality_summary
    )

    total_loaded = sum(
        row["records_loaded"] for row in quality_summary
    )

    total_rejected = sum(
        row["records_rejected"] for row in quality_summary
    )

    acceptance_rate = (
        total_loaded / total_received * 100
        if total_received > 0
        else 0
    )

    quality_columns = st.columns(4)

    quality_columns[0].metric(
        "Records Received",
        total_received,
    )

    quality_columns[1].metric(
        "Records Loaded",
        total_loaded,
    )

    quality_columns[2].metric(
        "Records Rejected",
        total_rejected,
    )

    quality_columns[3].metric(
        "Acceptance Rate",
        f"{acceptance_rate:.2f}%",
    )

    st.subheader("Data Quality by Dataset")

    st.dataframe(
        [dict(row) for row in quality_summary],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Rejection Reasons")

    if rejection_breakdown:
        st.dataframe(
            [dict(row) for row in rejection_breakdown],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No rejected records found.")

    st.subheader("Recent Quarantined Records")

    if recent_quarantine:
        st.dataframe(
            [dict(row) for row in recent_quarantine],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No quarantined records found.")
        st.divider()

    st.subheader("Alerts Monitoring")

    total_alerts = sum(
        row["alert_count"] for row in alert_summary
    )

    open_alerts = sum(
        row["alert_count"]
        for row in alert_summary
        if row["status"].upper() == "OPEN"
    )

    resolved_alerts = sum(
        row["alert_count"]
        for row in alert_summary
        if row["status"].upper() == "RESOLVED"
    )

    alert_columns = st.columns(3)

    alert_columns[0].metric(
        "Total Alerts",
        total_alerts,
    )

    alert_columns[1].metric(
        "Open Alerts",
        open_alerts,
    )

    alert_columns[2].metric(
        "Resolved Alerts",
        resolved_alerts,
    )

    st.subheader("Alerts by Severity and Status")

    if alert_summary:
        st.dataframe(
            [dict(row) for row in alert_summary],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No alerts found.")

    st.subheader("Recent Alert History")

    if recent_alerts:
        st.dataframe(
            [dict(row) for row in recent_alerts],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No alert history available.")

except Exception as error:
    st.error(f"Unable to load dashboard data: {error}")
