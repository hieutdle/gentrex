"""Run folders: every run of a command writes to a new folder under results/."""

import contextlib
import dataclasses
import datetime
import importlib.metadata
import json
import logging
import pathlib
import shlex
import subprocess
import sys
from collections.abc import Iterator
from typing import Any

import yaml

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

_RESULTS_DIR = pathlib.Path("results")
# Settings that only limit how long Gentrex waits for an answer, how many
# requests it sends at once and how long an answer may be. A good record
# stays the same under other values, so a retry may change them.
_LIMITS = frozenset({"timeout_seconds", "concurrency", "max_tokens"})

_logger = logging.getLogger(__name__)


class RetryError(Exception):
    """An earlier run whose records a new run can't reuse."""


@dataclasses.dataclass(frozen=True)
class Earlier:
    """An earlier run of a command, whose good records a new run reuses.

    Attributes:
        run_dir: The earlier run's folder.
        input_path: The file or folder that the earlier run read.
    """

    run_dir: pathlib.Path
    input_path: pathlib.Path


def latest(name: str) -> pathlib.Path:
    """Returns the link to the newest finished run in results/<name>/."""
    return _RESULTS_DIR / name / "latest"


def source() -> dict[str, Any]:
    """Returns the version of Gentrex and, when it runs from a clone, its commit.

    `modified` says whether the code in src/gentrex differs from the commit.
    Changes to settings.yaml and schema.yaml don't count, because run.yaml
    records the settings and the schema.
    """
    found: dict[str, Any] = {"version": importlib.metadata.version("gentrex")}
    package = pathlib.Path(__file__).resolve().parent

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(package), *args],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    try:
        top = pathlib.Path(git("rev-parse", "--show-toplevel")).resolve()
        if top / "src" / "gentrex" == package:
            found["commit"] = git("rev-parse", "HEAD")
            found["modified"] = bool(
                git(
                    "status",
                    "--porcelain",
                    "--untracked-files=no",
                    "--",
                    ".",
                    ":(exclude)defaults",
                )
            )
    except (OSError, subprocess.CalledProcessError):
        pass  # Installed from a package, or git is missing.
    return found


@contextlib.contextmanager
def new_run(
    name: str,
    input_path: pathlib.Path,
    settings: dict[str, Any],
    retry: pathlib.Path | None = None,
) -> Iterator[pathlib.Path]:
    """Creates results/<name>/<start time>/ for one run.

    The folder gets run.yaml, recording the command, the version of Gentrex,
    the input with links resolved, the settings and the earlier run that a
    retry reuses, and log.txt, a copy of the log. A second run that starts in
    the same second gets the folder name with "-2" added. latest(name) is
    pointed at the folder when the run finishes without raising.

    Args:
        name: Folder under results/ that holds the command's runs.
        input_path: File or folder the run reads.
        settings: The command's settings, as used.
        retry: The earlier run whose records this run reuses, if any.

    Yields:
        The run folder.
    """
    stem = started = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    number = 2
    while True:
        run_dir = _RESULTS_DIR / name / stem
        try:
            run_dir.mkdir(parents=True)
            break
        except FileExistsError:
            stem, number = f"{started}-{number}", number + 1
    record = {
        "command": shlex.join(["gentrex", *sys.argv[1:]]),
        "gentrex": source(),
        "input": str(input_path.resolve()),
        "settings": settings,
    }
    if retry is not None:
        record["retry"] = str(retry.resolve())
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
    link = latest(name)
    link.unlink(missing_ok=True)
    link.symlink_to(run_dir.name)


def earlier(run_dir: pathlib.Path, name: str, settings: dict[str, Any]) -> Earlier:
    """Returns an earlier run of a command, after checking that it can be reused.

    Args:
        run_dir: The earlier run's folder, finished or stopped halfway.
        name: The command's folder under results/, such as "extract".
        settings: The settings of the new run.

    Raises:
        RetryError: `run_dir` isn't a run of the command, used other settings
            apart from the limits in _LIMITS, or its input no longer exists.
    """
    record_path = run_dir / "run.yaml"
    if run_dir.resolve().parent.name != name or not record_path.is_file():
        raise RetryError(f"{run_dir} is not a run folder of gentrex {name}")
    record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
    if _without_limits(record["settings"]) != _without_limits(settings):
        raise RetryError(
            f"{run_dir} used other settings, so its records don't fit this run;"
            f" run gentrex {name} without --retry"
        )
    input_path = pathlib.Path(record["input"])
    if not input_path.exists():
        raise RetryError(
            f"{input_path}, which {run_dir} read, no longer exists, so Gentrex"
            f" can't tell which records changed; run gentrex {name} without --retry"
        )
    return Earlier(run_dir, input_path)


def read_earlier[T](path: pathlib.Path, record_type: type[T]) -> list[T]:
    """Reads the records in a file of an earlier run.

    A run that was stopped halfway, such as a job that reached its time
    limit, may end with half a line or have no file yet. The records before
    that are returned.
    """
    if not path.is_file():
        return []
    found = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                found.append(record_type(**json.loads(line)))
            except json.JSONDecodeError:
                break
    return found


def _without_limits(settings: Any) -> Any:
    if isinstance(settings, dict):
        return {
            key: _without_limits(value)
            for key, value in settings.items()
            if key not in _LIMITS
        }
    return settings
