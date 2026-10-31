
"""SLA monitoring and alert management for DataPulse."""

from datetime import datetime, timedelta, timezone
import sqlite3
from datapulse.database import deterministic_id, utc_now
from zoneinfo import ZoneInfo


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC."""

    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        raise ValueError(
            "Timestamp must include timezone information."
        )

    return parsed.astimezone(timezone.utc)


def create_alert(
    connection: sqlite3.Connection,
    dataset_id: str,
    alert_type: str,
    severity: str,
    message: str,
    fingerprint: str,
    load_event_id: str | None = None,
    run_id: str | None = None,
    detected_at: str | None = None,
) -> dict:
    """Create an alert once, using its fingerprint for deduplication."""

    detected_at = detected_at or utc_now()

    alert_id = deterministic_id(
        "alert",
        fingerprint,
    )

    cursor = connection.execute(
        """
        INSERT INTO alerts (
            alert_id,
            dataset_id,
            load_event_id,
            run_id,
            alert_type,
            severity,
            message,
            status,
            detected_at,
            fingerprint
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
        ON CONFLICT(fingerprint) DO NOTHING
        """,
        (
            alert_id,
            dataset_id,
            load_event_id,
            run_id,
            alert_type,
            severity,
            message,
            detected_at,
            fingerprint,
        ),
    )

    return {
        "alert_id": alert_id,
        "created": cursor.rowcount == 1,
        "fingerprint": fingerprint,
    }



def check_completion_sla(
    connection: sqlite3.Connection,
    load_event_id: str,
) -> dict:
    """Check whether processing exceeded the configured completion SLA."""

    event = connection.execute(
        """
        SELECT
            le.load_event_id,
            le.dataset_id,
            le.run_id,
            le.actual_arrival_at,
            le.completion_at,
            d.dataset_name,
            d.completion_sla_minutes
        FROM load_events le
        JOIN datasets d
            ON d.dataset_id = le.dataset_id
        WHERE le.load_event_id = ?
        """,
        (load_event_id,),
    ).fetchone()

    if event is None:
        raise ValueError(f"Load event not found: {load_event_id}")

    if not event["actual_arrival_at"] or not event["completion_at"]:
        return {
            "breached": False,
            "reason": "Arrival or completion timestamp is missing.",
            "alert_created": False,
        }

    actual = parse_timestamp(event["actual_arrival_at"])
    completed = parse_timestamp(event["completion_at"])

    duration_minutes = (
        completed - actual
    ).total_seconds() / 60

    allowed_minutes = event["completion_sla_minutes"]

    if duration_minutes <= allowed_minutes:
        return {
            "breached": False,
            "duration_minutes": round(duration_minutes, 2),
            "alert_created": False,
        }

    breach_minutes = round(
        duration_minutes - allowed_minutes,
        2,
    )

    fingerprint = (
        f"{event['dataset_name']}|COMPLETION_SLA_BREACH|"
        f"{event['load_event_id']}"
    )

    alert = create_alert(
        connection=connection,
        dataset_id=event["dataset_id"],
        load_event_id=event["load_event_id"],
        run_id=event["run_id"],
        alert_type="COMPLETION_SLA_BREACH",
        severity="HIGH",
        message=(
            f"{event['dataset_name']} processing took "
            f"{duration_minutes:.2f} minutes, exceeding "
            f"its {allowed_minutes}-minute SLA by "
            f"{breach_minutes:.2f} minutes."
        ),
        fingerprint=fingerprint,
    )

    return {
        "breached": True,
        "duration_minutes": round(duration_minutes, 2),
        "breach_minutes": breach_minutes,
        "alert_created": alert["created"],
        "alert_id": alert["alert_id"],
    }

def check_late_arrival(
    connection: sqlite3.Connection,
    load_event_id: str,
) -> dict:
    """Check whether a load event arrived after its allowed grace period."""

    event = connection.execute(
        """
        SELECT
            le.load_event_id,
            le.dataset_id,
            le.run_id,
            le.expected_arrival_at,
            le.actual_arrival_at,
            d.dataset_name,
            d.arrival_grace_minutes
        FROM load_events le
        JOIN datasets d
            ON d.dataset_id = le.dataset_id
        WHERE le.load_event_id = ?
        """,
        (load_event_id,),
    ).fetchone()

    if event is None:
        raise ValueError(f"Load event not found: {load_event_id}")

    if not event["actual_arrival_at"]:
        return {
            "late": False,
            "reason": "Actual arrival time is not available.",
            "alert_created": False,
        }

    expected = parse_timestamp(event["expected_arrival_at"])
    actual = parse_timestamp(event["actual_arrival_at"])

    deadline = expected + timedelta(
        minutes=event["arrival_grace_minutes"]
    )

    if actual <= deadline:
        return {
            "late": False,
            "reason": "Load arrived within the allowed grace period.",
            "alert_created": False,
        }

    delay_minutes = round(
        (actual - deadline).total_seconds() / 60,
        2,
    )

    fingerprint = (
        f"{event['dataset_name']}|LATE_ARRIVAL|"
        f"{event['expected_arrival_at']}"
    )

    alert = create_alert(
        connection=connection,
        dataset_id=event["dataset_id"],
        load_event_id=event["load_event_id"],
        run_id=event["run_id"],
        alert_type="LATE_ARRIVAL",
        severity="HIGH",
        message=(
            f"{event['dataset_name']} arrived "
            f"{delay_minutes} minutes after its SLA deadline."
        ),
        fingerprint=fingerprint,
    )

    connection.execute(
        """
        UPDATE load_events
        SET status = 'LATE'
        WHERE load_event_id = ?
        """,
        (load_event_id,),
    )

    return {
        "late": True,
        "delay_minutes": delay_minutes,
        "alert_created": alert["created"],
        "alert_id": alert["alert_id"],
    }


def check_freshness(
    connection: sqlite3.Connection,
    dataset_id: str,
    now: str | None = None,
) -> dict:
    """Check whether the latest successful dataset load is stale."""

    now = now or utc_now()

    dataset = connection.execute(
        """
        SELECT dataset_id, dataset_name, freshness_sla_minutes
        FROM datasets
        WHERE dataset_id = ?
        """,
        (dataset_id,),
    ).fetchone()

    if dataset is None:
        raise ValueError(f"Dataset not found: {dataset_id}")

    latest_load = connection.execute(
        """
        SELECT completion_at, load_event_id, run_id
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

    if latest_load is None:
        return {
            "stale": True,
            "reason": "No successful completed load is available.",
            "alert_created": False,
        }

    current_time = parse_timestamp(now)
    completed_at = parse_timestamp(latest_load["completion_at"])

    age_minutes = (
        current_time - completed_at
    ).total_seconds() / 60

    allowed_minutes = dataset["freshness_sla_minutes"]

    if age_minutes <= allowed_minutes:
        return {
            "stale": False,
            "age_minutes": round(age_minutes, 2),
            "alert_created": False,
        }

    stale_minutes = round(age_minutes - allowed_minutes, 2)

    fingerprint = (
        f"{dataset['dataset_name']}|FRESHNESS_BREACH|"
        f"{latest_load['completion_at']}"
    )

    alert = create_alert(
        connection=connection,
        dataset_id=dataset_id,
        load_event_id=latest_load["load_event_id"],
        run_id=latest_load["run_id"],
        alert_type="FRESHNESS_BREACH",
        severity="HIGH",
        message=(
            f"{dataset['dataset_name']} is stale. "
            f"Latest load age is {age_minutes:.2f} minutes, "
            f"exceeding its freshness SLA by "
            f"{stale_minutes:.2f} minutes."
        ),
        fingerprint=fingerprint,
        detected_at=now,
    )

    return {
        "stale": True,
        "age_minutes": round(age_minutes, 2),
        "stale_minutes": stale_minutes,
        "alert_created": alert["created"],
        "alert_id": alert["alert_id"],
    }


def check_missing_load(
    connection: sqlite3.Connection,
    dataset_id: str,
    now: str | None = None,
) -> dict:
    """Detect a dataset that has not arrived after its grace period."""

    now = now or utc_now()
    current_time = parse_timestamp(now)

    dataset = connection.execute(
        """
        SELECT
            dataset_id,
            dataset_name,
            expected_arrival_time,
            timezone,
            arrival_grace_minutes,
            is_active
        FROM datasets
        WHERE dataset_id = ?
        """,
        (dataset_id,),
    ).fetchone()

    if dataset is None:
        raise ValueError(f"Dataset not found: {dataset_id}")

    if not dataset["is_active"]:
        return {
            "missing": False,
            "reason": "Dataset is inactive.",
            "alert_created": False,
        }

    dataset_timezone = ZoneInfo(dataset["timezone"])
    local_now = current_time.astimezone(dataset_timezone)

    expected_arrival = datetime.combine(
        local_now.date(),
        datetime.strptime(
            dataset["expected_arrival_time"],
            "%H:%M",
        ).time(),
        tzinfo=dataset_timezone,
    )

    deadline = expected_arrival + timedelta(
        minutes=dataset["arrival_grace_minutes"]
    )

    if current_time <= deadline.astimezone(timezone.utc):
        return {
            "missing": False,
            "reason": "The arrival deadline has not passed.",
            "alert_created": False,
        }

    existing_events = connection.execute(
        """
        SELECT expected_arrival_at,actual_arrival_at
        FROM load_events
        WHERE dataset_id = ?
        """,
        (dataset_id,),
    ).fetchall()

    for event in existing_events:
        if (
            event["expected_arrival_at"]
            and event["actual_arrival_at"]
            and parse_timestamp(event["expected_arrival_at"])
            == expected_arrival.astimezone(timezone.utc)
        ):
            return {
                "missing": False,
                "reason": "A load event exists for this scheduled arrival.",
                "alert_created": False,
            }

    expected_utc = expected_arrival.astimezone(timezone.utc)
    fingerprint = (
        f"{dataset['dataset_name']}|MISSING_LOAD|"
        f"{expected_utc.isoformat()}"
    )

    alert = create_alert(
        connection=connection,
        dataset_id=dataset_id,
        alert_type="MISSING_LOAD",
        severity="HIGH",
        message=(
            f"{dataset['dataset_name']} has not arrived by its "
            f"scheduled deadline of {deadline.isoformat()}."
        ),
        fingerprint=fingerprint,
        detected_at=now,
    )

    return {
        "missing": True,
        "alert_created": alert["created"],
        "alert_id": alert["alert_id"],
        "expected_arrival_at": expected_arrival.isoformat(),
        "deadline": deadline.isoformat(),
    }

def run_sla_checks(
    connection: sqlite3.Connection,
    now: str | None = None,
) -> dict:
    """Run all SLA checks for active datasets and recorded load events."""

    now = now or utc_now()

    datasets = connection.execute(
        """
        SELECT dataset_id
        FROM datasets
        WHERE is_active = 1
        ORDER BY dataset_id
        """
    ).fetchall()

    events = connection.execute(
        """
        SELECT load_event_id, actual_arrival_at, completion_at
        FROM load_events
        ORDER BY created_at
        """
    ).fetchall()

    event_results = []

    for event in events:
        if event["actual_arrival_at"]:
            late_result = check_late_arrival(
                connection,
                event["load_event_id"],
            )
        else:
            late_result = {
                "late": False,
                "reason": "Actual arrival time is not available.",
            }

        completion_result = None

        if event["completion_at"]:
            completion_result = check_completion_sla(
                connection,
                event["load_event_id"],
            )

        event_results.append({
            "load_event_id": event["load_event_id"],
            "late_arrival": late_result,
            "completion_sla": completion_result,
        })

    dataset_results = []

    for dataset in datasets:
        dataset_id = dataset["dataset_id"]

        freshness_result = check_freshness(
            connection,
            dataset_id,
            now,
        )

        missing_result = check_missing_load(
            connection,
            dataset_id,
            now,
        )

        dataset_results.append({
            "dataset_id": dataset_id,
            "freshness": freshness_result,
            "missing_load": missing_result,
        })

    alerts_created = sum(
        bool(result.get("alert_created"))
        for item in event_results
        for result in (
            item["late_arrival"],
            item["completion_sla"],
        )
        if result is not None
    )

    alerts_created += sum(
        bool(result.get("alert_created"))
        for item in dataset_results
        for result in (
            item["freshness"],
            item["missing_load"],
        )
    )
    return {
        "checked_at": now,
        "datasets_checked": len(datasets),
        "load_events_checked": len(events),
        "datasets": dataset_results,
        "load_events": event_results,
        "alerts_created": alerts_created,
    }
