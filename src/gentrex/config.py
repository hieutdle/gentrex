"""Packaged default settings."""

import pathlib
from typing import Any

import yaml

_SETTINGS_PATH = pathlib.Path(__file__).parent / "defaults" / "settings.yaml"


def load_settings() -> dict[str, Any]:
    """Returns the settings in defaults/settings.yaml."""
    with _SETTINGS_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)
