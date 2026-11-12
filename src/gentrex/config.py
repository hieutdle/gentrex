"""Packaged default settings, and the settings file that changes them."""

import pathlib
from typing import Any

import yaml

_SETTINGS_PATH = pathlib.Path(__file__).parent / "defaults" / "settings.yaml"
_SCHEMA_PATH = pathlib.Path(__file__).parent / "defaults" / "schema.yaml"
# The questions of gentrex select have names of the user's choosing, so the
# questions of a settings file replace the default ones.
_REPLACED = frozenset({("select", "questions")})


class SettingsError(Exception):
    """A settings file that Gentrex can't use."""


def _change(
    settings: dict[str, Any], changes: dict[str, Any], path: tuple[str, ...]
) -> None:
    """Sets the values of `changes` in `settings`, key by key."""
    for key, value in changes.items():
        here = (*path, str(key))
        if key not in settings:
            raise SettingsError(f"{'.'.join(here)} is not a setting of Gentrex")
        both = isinstance(value, dict) and isinstance(settings[key], dict)
        if both and here not in _REPLACED:
            _change(settings[key], value, here)
        else:
            settings[key] = value


def load_settings(path: pathlib.Path | None = None) -> dict[str, Any]:
    """Returns the settings in defaults/settings.yaml, changed by a file of your own.

    Args:
        path: A YAML file with the settings to change, laid out as
            defaults/settings.yaml. It needs only the settings that differ.

    Raises:
        SettingsError: The file can't be read, or names a setting that
            defaults/settings.yaml doesn't have.
    """
    with _SETTINGS_PATH.open(encoding="utf-8") as fh:
        settings = yaml.safe_load(fh)
    if path is None:
        return settings
    try:
        changes = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SettingsError(f"can't read {path}: {exc}") from exc
    if not isinstance(changes, dict):
        raise SettingsError(f"{path} has no settings")
    try:
        _change(settings, changes, ())
    except SettingsError as exc:
        raise SettingsError(f"{path}: {exc}") from None
    return settings


def load_schema() -> dict[str, Any]:
    """Returns the extraction schema in defaults/schema.yaml."""
    with _SCHEMA_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)
