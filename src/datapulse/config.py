"""Loads project settings from config/settings.yaml."""
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"


def load_settings(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """Read the YAML settings file and return it as a dict.

    Raises FileNotFoundError with a clear message if the file is missing.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Settings file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)