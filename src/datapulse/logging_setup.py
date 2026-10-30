"""Central logging configuration for DataPulse."""
import logging
from pathlib import Path


def get_logger(name: str, log_dir: str = "logs", level: str = "INFO") -> logging.Logger:
    """Return a logger that writes to the console and to <log_dir>/datapulse.log.

    Calling this repeatedly with the same name does not add duplicate handlers.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(Path(log_dir) / "datapulse.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger