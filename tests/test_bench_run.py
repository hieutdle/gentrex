"""Tests of gentrex-bench/run.py, which runs and scores the benchmark."""

import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "gentrex-bench"))

import run  # noqa: E402


def test_only_the_pdfs_of_the_split_are_read(tmp_path):
    """Tuning runs must not spend GPU time on the test reports."""
    for name, split in (("SYN-0001", "dev"), ("SYN-0101", "test")):
        truth = tmp_path / "truth" / f"{name}.json"
        truth.parent.mkdir(exist_ok=True)
        truth.write_text(json.dumps({"case": {"split": split}}))
        pdf = tmp_path / "pdf" / "scan" / f"{name}.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(b"%PDF")

    linked = run.link_pdfs(tmp_path, "scan", "dev", tmp_path / "out")

    assert linked == 1
    assert [p.name for p in (tmp_path / "out").iterdir()] == ["SYN-0001.pdf"]
    assert (tmp_path / "out" / "SYN-0001.pdf").read_bytes() == b"%PDF"


def test_a_command_with_failed_files_is_counted(tmp_path):
    """A model server that died halfway must not look like a clean run."""
    folder = tmp_path / "extract" / "20261110-120000"
    folder.mkdir(parents=True)
    (folder / "log.txt").write_text(
        "2026-11-10 12:00:00,000 INFO writing results\n"
        "2026-11-10 12:05:00,000 ERROR failed files: SYN-0001.pdf, SYN-0002.pdf\n"
    )
    scores = {
        "runs": {"extract": {"path": str(folder)}},
        "performance": {"commands": {"extract": {}}},
    }

    failures = run.add_failures(scores, {"extract": 1})

    assert failures == 1
    assert scores["performance"]["commands"]["extract"] == {
        "exit_status": 1,
        "failed_files": 2,
    }


def test_a_run_goes_on_after_the_command_of_a_finished_run_folder(tmp_path):
    """A crash in gentrex extract must not cost the GPU time of the commands before."""
    steps: list[tuple[str, str | None, str | None]] = [
        (name, None, None) for name in ("transcribe", "select", "extract")
    ]
    folder = tmp_path / "select" / "20261110-120000"
    folder.mkdir(parents=True)
    (folder / "run.yaml").write_text("input: x\n")

    assert run.steps_after(steps, folder) == steps[2:]
    with pytest.raises(ValueError, match="not a run folder"):
        run.steps_after(steps, tmp_path)
