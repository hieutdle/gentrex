import datetime
import importlib.metadata
import re
import types

import pytest
import yaml

from gentrex import records
from gentrex import runs


class _SameSecond(datetime.datetime):
    @classmethod
    def now(cls, tz: datetime.tzinfo | None = None) -> "_SameSecond":
        return cls(2026, 11, 5, 4, 26, 12)


def test_run_records_the_input_run_it_read(tmp_path, monkeypatch):
    """`latest` moves on, so the record must name the run actually read."""
    monkeypatch.chdir(tmp_path)
    with runs.new_run("transcribe", tmp_path, {}) as transcribe_dir:
        pass

    with runs.new_run("select", runs.latest("transcribe"), {}) as select_dir:
        pass

    record = yaml.safe_load((select_dir / "run.yaml").read_text())
    assert record["input"] == str(transcribe_dir.resolve())


def test_crashed_run_does_not_become_latest(tmp_path, monkeypatch):
    """`gentrex select` must not read a run that stopped halfway."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError), runs.new_run("transcribe", tmp_path, {}):
        raise RuntimeError("model server stopped")

    assert not runs.latest("transcribe").exists()


def test_a_run_records_the_gentrex_version_and_commit(tmp_path, monkeypatch):
    """A result must be traceable to the code that produced it."""
    monkeypatch.chdir(tmp_path)

    with runs.new_run("transcribe", tmp_path, {}) as run_dir:
        pass

    record = yaml.safe_load((run_dir / "run.yaml").read_text())
    assert record["gentrex"]["version"] == importlib.metadata.version("gentrex")
    assert re.fullmatch(r"[0-9a-f]{40}", record["gentrex"]["commit"])


def test_runs_in_the_same_second_get_folders_of_their_own(tmp_path, monkeypatch):
    """Scripts run fast commands back to back, and the second must not crash."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runs, "datetime", types.SimpleNamespace(datetime=_SameSecond))

    with runs.new_run("export/fhir", tmp_path, {}) as first:
        pass
    with runs.new_run("export/fhir", tmp_path, {}) as second:
        pass

    assert (first.name, second.name) == ("20261105-042612", "20261105-042612-2")


def test_retry_refuses_a_run_with_other_settings(tmp_path, monkeypatch):
    """Records from another model would mix two kinds of results in one run."""
    monkeypatch.chdir(tmp_path)
    with runs.new_run("extract", tmp_path, {"model": "gemma"}) as run_dir:
        pass

    with pytest.raises(runs.RetryError, match="other settings"):
        runs.earlier(run_dir, "extract", {"model": "another model"})


def test_retry_allows_the_limits_that_made_reports_fail(tmp_path, monkeypatch):
    """Raising max_tokens or timeout_seconds is how failed reports are fixed."""
    monkeypatch.chdir(tmp_path)
    settings = {"model": "gemma", "max_tokens": 4096, "timeout_seconds": 300}
    with runs.new_run("extract", tmp_path, settings) as run_dir:
        pass

    earlier = runs.earlier(
        run_dir, "extract", {**settings, "max_tokens": 8192, "timeout_seconds": 600}
    )

    assert earlier.input_path == tmp_path.resolve()


def test_a_run_that_stopped_halfway_is_read_up_to_its_last_whole_line(tmp_path):
    """A job killed at its time limit can leave half a line behind."""
    record = records.ReportExtraction("a.pdf", [1], {"mrn": "SYN-MRN-0001"})
    path = tmp_path / "extractions.jsonl"
    path.write_text(record.to_json() + "\n" + record.to_json()[:20])

    assert runs.read_earlier(path, records.ReportExtraction) == [record]
