"""Packaged default settings."""

import pathlib
from typing import Any

import yaml

_SETTINGS_PATH = pathlib.Path(__file__).parent / "defaults" / "settings.yaml"
_SCHEMA_PATH = pathlib.Path(__file__).parent / "defaults" / "schema.yaml"


def load_settings() -> dict[str, Any]:
    """Returns the settings in defaults/settings.yaml."""
    with _SETTINGS_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_schema() -> dict[str, Any]:
    """Returns the extraction schema in defaults/schema.yaml."""
    with _SCHEMA_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)
