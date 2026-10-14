import pytest
import yaml

from gentrex import runs


def test_run_records_the_input_run_it_read(tmp_path, monkeypatch):
    """`latest` moves on, so the record must name the run actually read."""
    monkeypatch.chdir(tmp_path)
    with runs.new_run("transcribe", tmp_path, {}) as transcribe_dir:
        pass

    with runs.new_run("pagedecide", runs.latest("transcribe"), {}) as decide_dir:
        pass

    record = yaml.safe_load((decide_dir / "run.yaml").read_text())
    assert record["input"] == str(transcribe_dir.resolve())


def test_crashed_run_does_not_become_latest(tmp_path, monkeypatch):
    """The next stage must not read a run that stopped halfway."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError), runs.new_run("transcribe", tmp_path, {}):
        raise RuntimeError("model server stopped")

    assert not runs.latest("transcribe").exists()
