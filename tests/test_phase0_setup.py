"""Phase 0 tests: config loading and logging setup."""
from pathlib import Path

import pytest

from datapulse.config import load_settings
from datapulse.logging_setup import get_logger


def test_load_settings_returns_expected_keys():
    settings = load_settings()
    for key in ("database_path", "landing_dir", "log_dir", "log_level"):
        assert key in settings


def test_load_settings_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "does_not_exist.yaml")


def test_get_logger_writes_to_file(tmp_path):
    logger = get_logger("datapulse.test_file", log_dir=str(tmp_path))
    logger.info("hello from test")
    for handler in logger.handlers:
        handler.flush()
    log_file = Path(tmp_path) / "datapulse.log"
    assert log_file.exists()
    assert "hello from test" in log_file.read_text(encoding="utf-8")


def test_get_logger_does_not_duplicate_handlers(tmp_path):
    first = get_logger("datapulse.test_dupes", log_dir=str(tmp_path))
    count = len(first.handlers)
    second = get_logger("datapulse.test_dupes", log_dir=str(tmp_path))
    assert len(second.handlers) == count