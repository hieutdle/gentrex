"""Run folders: every stage run writes to a new folder under results/."""

import contextlib
import datetime
import logging
import pathlib
import shlex
import sys
from collections.abc import Iterator
from typing import Any

import yaml

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

_RESULTS_DIR = pathlib.Path("results")

_logger = logging.getLogger(__name__)


def latest(stage: str) -> pathlib.Path:
    """Returns the link to the newest finished run of `stage`."""
    return _RESULTS_DIR / stage / "latest"


@contextlib.contextmanager
def new_run(
    stage: str, input_path: pathlib.Path, settings: dict[str, Any]
) -> Iterator[pathlib.Path]:
    """Creates results/<stage>/<start time>/ for one run.

    The folder gets run.yaml, recording the command, the input with links
    resolved and the settings, and log.txt, a copy of the log. latest(stage)
    is pointed at the folder when the run finishes without raising.

    Args:
        stage: Folder under results/ that holds the stage's runs.
        input_path: File or folder the run reads.
        settings: The stage's settings, as used.

    Yields:
        The run folder.
    """
    started = datetime.datetime.now()
    run_dir = _RESULTS_DIR / stage / started.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True)
    record = {
        "command": shlex.join(["gentrex", *sys.argv[1:]]),
        "input": str(input_path.resolve()),
        "settings": settings,
    }
    (run_dir / "run.yaml").write_text(
        yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    log_file = logging.FileHandler(run_dir / "log.txt", encoding="utf-8")
    log_file.setFormatter(logging.Formatter(LOG_FORMAT))
    root = logging.getLogger()
    root.addHandler(log_file)
    try:
        _logger.info("writing %s", run_dir)
        yield run_dir
    finally:
        root.removeHandler(log_file)
        log_file.close()
    link = latest(stage)
    link.unlink(missing_ok=True)
    link.symlink_to(run_dir.name)
