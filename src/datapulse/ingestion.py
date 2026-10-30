
"""CSV ingestion and pipeline-run tracking for DataPulse."""

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from contextlib import closing

import pandas as pd

from datapulse.database import DATABASE_PATH, get_connection, utc_now
from datapulse.logging_setup import get_logger


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LANDING_DIR = PROJECT_ROOT / "data" / "landing"

DATASET_IDS = {
    "customers": "dataset_customers",
    "orders": "dataset_orders",
}

logger = get_logger(
    __name__,
    log_dir=str(PROJECT_ROOT / "logs"),
)


@dataclass
class IngestionResult:
    """Structured result returned by one file-ingestion attempt."""

    run_id: str
    dataset_name: str
    source_file: str
    started_at: str
    completed_at: str
    status: str
    input_row_count: int
    columns: list[str]
    error_message: str | None = None
    data: pd.DataFrame | None = None


def generate_run_id() -> str:
    """Generate a unique ID for every ingestion attempt."""
    return f"run_{uuid4().hex}"


def get_source_file_name(file_path: Path) -> str:
    """Return a stable project-relative path when possible."""
    resolved_path = file_path.resolve()

    try:
        return resolved_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(resolved_path)


def validate_source_file(file_path: Path) -> None:
    """Check that the source exists, is a regular file, and can be opened."""
    if not file_path.exists():
        raise FileNotFoundError(f"Source file does not exist: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Source path is not a file: {file_path}")

    try:
        with file_path.open("rb"):
            pass
    except OSError as exc:
        raise OSError(f"Source file is not readable: {file_path}") from exc


def read_csv_file(file_path: Path) -> pd.DataFrame:
    """Read a CSV file and reject empty or malformed input."""
    try:
        dataframe = pd.read_csv(file_path, on_bad_lines="error")
    except pd.errors.EmptyDataError as exc:
        raise ValueError("CSV file is empty or has no header.") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(f"Malformed CSV file: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError("CSV file is not valid UTF-8 text.") from exc

    if dataframe.empty:
        raise ValueError("CSV file contains no data rows.")

    return dataframe


def create_pipeline_run(
    run_id: str,
    dataset_id: str,
    source_file: str,
    started_at: str,
    database_path: Path,
) -> None:
    """Insert a RUNNING record before attempting to read the file."""
    with closing(get_connection(database_path)) as connection:
        connection.execute(
            """
            INSERT INTO pipeline_runs (
                run_id,
                dataset_id,
                source_file,
                started_at,
                status,
                records_received,
                records_loaded,
                records_rejected
            )
            VALUES (?, ?, ?, ?, 'RUNNING', 0, 0, 0)
            """,
            (run_id, dataset_id, source_file, started_at),
        )
        connection.commit()

def complete_pipeline_run(
    run_id: str,
    status: str,
    completed_at: str,
    database_path: Path,
    input_row_count: int = 0,
    error_message: str | None = None,
) -> None:
    """Update the pipeline run with its final status and row count."""
    with closing(get_connection(database_path)) as connection:
        connection.execute(
            """
            UPDATE pipeline_runs
            SET completed_at = ?,
                status = ?,
                records_received = ?,
                error_message = ?
            WHERE run_id = ?
            """,
            (
                completed_at,
                status,
                input_row_count,
                error_message,
                run_id,
            ),
        )
        connection.commit()

def ingest_file(
    dataset_name: str,
    file_path: str | Path,
    database_path: str | Path = DATABASE_PATH,
) -> IngestionResult:
    """Ingest one CSV file and record both successful and failed attempts."""
    if dataset_name not in DATASET_IDS:
        raise ValueError(
            f"Unsupported dataset: {dataset_name}. "
            f"Supported datasets: {', '.join(DATASET_IDS)}"
        )

    file_path = Path(file_path)
    database_path = Path(database_path)

    run_id = generate_run_id()
    started_at = utc_now()
    source_file = get_source_file_name(file_path)
    dataset_id = DATASET_IDS[dataset_name]

    # Confirm that the dataset exists before inserting the run.
    with get_connection(database_path) as connection:
        dataset = connection.execute(
            "SELECT dataset_id FROM datasets WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchone()

    if dataset is None:
        raise ValueError(
            f"Dataset '{dataset_name}' is not registered in the database. "
            "Initialize and seed the database before ingestion."
        )

    create_pipeline_run(
        run_id,
        dataset_id,
        source_file,
        started_at,
        database_path,
    )

    logger.info(
        "Started ingestion | dataset=%s | run_id=%s | source=%s",
        dataset_name,
        run_id,
        source_file,
    )

    try:
        validate_source_file(file_path)
        dataframe = read_csv_file(file_path)

        completed_at = utc_now()
        row_count = len(dataframe)

        complete_pipeline_run(
            run_id=run_id,
            status="SUCCESS",
            completed_at=completed_at,
            database_path=database_path,
            input_row_count=row_count,
        )

        logger.info(
            "Ingestion successful | dataset=%s | run_id=%s | rows=%s",
            dataset_name,
            run_id,
            row_count,
        )

        return IngestionResult(
            run_id=run_id,
            dataset_name=dataset_name,
            source_file=source_file,
            started_at=started_at,
            completed_at=completed_at,
            status="SUCCESS",
            input_row_count=row_count,
            columns=dataframe.columns.tolist(),
            data=dataframe,
        )

    except (FileNotFoundError, ValueError, OSError) as exc:
        completed_at = utc_now()
        error_message = str(exc)

        complete_pipeline_run(
            run_id=run_id,
            status="FAILED",
            completed_at=completed_at,
            database_path=database_path,
            error_message=error_message,
        )

        logger.exception(
            "Ingestion failed | dataset=%s | run_id=%s",
            dataset_name,
            run_id,
        )

        return IngestionResult(
            run_id=run_id,
            dataset_name=dataset_name,
            source_file=source_file,
            started_at=started_at,
            completed_at=completed_at,
            status="FAILED",
            input_row_count=0,
            columns=[],
            error_message=error_message,
        )


def run_ingestion(
    landing_dir: str | Path = LANDING_DIR,
    database_path: str | Path = DATABASE_PATH,
) -> dict[str, IngestionResult]:
    """Run ingestion independently for customers and orders."""
    landing_dir = Path(landing_dir)

    results = {}

    for dataset_name in ("customers", "orders"):
        file_path = landing_dir / f"{dataset_name}.csv"

        results[dataset_name] = ingest_file(
            dataset_name=dataset_name,
            file_path=file_path,
            database_path=database_path,
        )

    return results


if __name__ == "__main__":
    ingestion_results = run_ingestion()

    for dataset_name, result in ingestion_results.items():
        print(
            f"{dataset_name}: {result.status} | "
            f"Rows: {result.input_row_count} | "
            f"Run ID: {result.run_id}"
        )

        if result.error_message:
            print(f"Error: {result.error_message}")
