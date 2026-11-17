import pytest

from gentrex import config


def test_settings_file_changes_only_the_settings_it_names(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text(
        "extract:\n  model: other/model\n"
        "select:\n  questions:\n    has_variant: Does this page list a variant?\n"
    )
    defaults = config.load_settings()

    settings = config.load_settings(path)

    assert settings["extract"]["model"] == "other/model"
    assert settings["extract"]["max_tokens"] == defaults["extract"]["max_tokens"]
    assert list(settings["select"]["questions"]) == ["has_variant"]
    assert settings["transcribe"] == defaults["transcribe"]


def test_settings_file_with_an_unknown_setting_is_refused(tmp_path):
    """A misspelled setting would otherwise leave the default in place unnoticed."""
    path = tmp_path / "settings.yaml"
    path.write_text("extract:\n  modle: other/model\n")

    with pytest.raises(config.SettingsError, match="extract.modle is not a setting"):
        config.load_settings(path)


def test_schema_of_your_own_replaces_the_packaged_one(tmp_path):
    path = tmp_path / "schema.yaml"
    path.write_text("type: object\nproperties:\n  mrn:\n    type: [string, 'null']\n")

    assert list(config.load_schema(path)["properties"]) == ["mrn"]
    assert "variants" in config.load_schema()["properties"]


def test_file_that_holds_no_schema_is_refused(tmp_path):
    """A settings file passed as the schema would otherwise extract nothing."""
    path = tmp_path / "schema.yaml"
    path.write_text("extract:\n  model: other/model\n")

    with pytest.raises(config.SettingsError, match="has no fields"):
        config.load_schema(path)
