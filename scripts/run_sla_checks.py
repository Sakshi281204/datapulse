"""Run DataPulse SLA monitoring checks."""

from contextlib import closing

from datapulse.database import DATABASE_PATH, get_connection
from datapulse.sla_monitor import run_sla_checks


def main():
    with closing(get_connection(DATABASE_PATH)) as connection:
        result = run_sla_checks(connection)
        connection.commit()

    print("\nDataPulse SLA Monitoring Report")
    print("-" * 35)
    print(f"Checked at: {result['checked_at']}")
    print(f"Datasets checked: {result['datasets_checked']}")
    print(f"Load events checked: {result['load_events_checked']}")
    print(f"New alerts created: {result['alerts_created']}")

    print("\nDataset Results:")

    for dataset in result["datasets"]:
        print(f"\nDataset ID: {dataset['dataset_id']}")
        print(f"Freshness: {dataset['freshness']}")
        print(f"Missing load: {dataset['missing_load']}")

    print("\nLoad Event Results:")

    for event in result["load_events"]:
        print(f"\nLoad Event ID: {event['load_event_id']}")
        print(f"Late arrival: {event['late_arrival']}")
        print(f"Completion SLA: {event['completion_sla']}")


if __name__ == "__main__":
    main()