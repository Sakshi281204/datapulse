"""SQLite connection and schema initialisation."""
import sqlite3
from pathlib import Path

from datapulse.config import PROJECT_ROOT, load_settings
from datapulse.logging_setup import get_logger

SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"
logger = get_logger("datapulse.db")


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys enforced.

    With no argument it uses database_path from config/settings.yaml.
    Pass ":memory:" for a throwaway database (used by tests).
    """
    if db_path is None:
        db_path = PROJECT_ROOT / load_settings()["database_path"]
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    """Create all control tables if they do not exist. Safe to call repeatedly."""
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    try:
        connection.executescript(schema_sql)
    except sqlite3.Error:
        logger.exception("Schema initialisation failed")
        raise
    logger.info("Database schema ready")