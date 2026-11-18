"""Run Gentrex on benchmark reports, from the PDFs to the scores.

    uv run --extra hpo --env-file .env python gentrex-bench/run.py --version v1

Runs gentrex transcribe, select, extract and normalize on one copy of the
reports of one split, and scores the result with scorer/score.py. The scores
go to a new folder under results/gentrex-bench/. With --serve, the script
starts the model server of each command and stops it afterwards, so that one
machine can serve the three models in turn. --settings and --no-select run
another setup, to compare it with the default one. --from-run goes on after a
command that already finished, so that a run that stopped doesn't repeat it.
docs/development/run-benchmark.md explains it.
"""

import argparse
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).parent / "scorer"))

import score  # noqa: E402

from gentrex import config  # noqa: E402
from gentrex import runs  # noqa: E402
from gentrex import servers  # noqa: E402

_logger = logging.getLogger("run")
_DATA_DIR = pathlib.Path("data/gentrex-bench")
# A command, the variable with its server's address and its model.
type _Step = tuple[str, str | None, str | None]


def link_pdfs(
    version_dir: pathlib.Path, copy: str, split: str, folder: pathlib.Path
) -> int:
    """Links one copy of the PDFs of a split into a new folder.

    Args:
        version_dir: Folder of the benchmark version.
        copy: Folder under pdf/, such as native or scan.
        split: The split, as the truth files name it, or "all".
        folder: The folder to create.

    Returns:
        The number of PDFs linked.
    """
    folder.mkdir()
    linked = 0
    for path in sorted((version_dir / "truth").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8")).get("case", {})
        if split in ("all", case.get("split")):
            pdf = version_dir / "pdf" / copy / f"{path.stem}.pdf"
            (folder / pdf.name).symlink_to(pdf.resolve())
            linked += 1
    return linked


def _server_version(base_url: str | None) -> str | None:
    """Returns the version that a vLLM server reports, or None for other servers."""
    if not base_url:
        return None
    try:
        url = base_url.rstrip("/").removesuffix("/v1") + "/version"
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.load(response).get("version")
    except (OSError, ValueError, AttributeError):
        return None


def _gpu_names() -> list[str]:
    """Returns the names of this machine's NVIDIA GPUs."""
    if not shutil.which("nvidia-smi"):
        return []
    listed = subprocess.run(
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
        capture_output=True,
        text=True,
    )
    return listed.stdout.split("\n")[:-1] if listed.returncode == 0 else []


def _gentrex(
    command: str, arguments: list[str], env: dict[str, str]
) -> tuple[pathlib.Path | None, int]:
    """Runs a Gentrex command.

    Returns:
        The command's run folder, or None if it didn't finish, and its exit
        status.
    """
    latest = runs.latest(command)
    before = latest.resolve() if latest.exists() else None
    gentrex = pathlib.Path(sys.executable).with_name("gentrex")
    status = subprocess.run([str(gentrex), command, *arguments], env=env).returncode
    after = latest.resolve() if latest.exists() else None
    if after is None or after == before:
        _logger.error("gentrex %s did not finish (exit code %d)", command, status)
        return None, status
    if status:
        _logger.warning(
            "gentrex %s had failed files; the run goes on and is scored", command
        )
    return after, status


def steps_after(steps: list[_Step], run_dir: pathlib.Path) -> list[_Step]:
    """Returns the steps that come after the command that wrote a run folder.

    Raises:
        ValueError: The folder is not a run folder of an earlier step.
    """
    names = [command for command, _, _ in steps]
    command = run_dir.resolve().parent.name
    if command not in names[:-1] or not (run_dir / "run.yaml").is_file():
        raise ValueError(
            f"{run_dir} is not a run folder of gentrex {' or '.join(names[:-1])}"
        )
    return steps[names.index(command) + 1 :]


def add_failures(scores: dict[str, Any], statuses: dict[str, int]) -> int:
    """Adds each command's exit status and failed files to the scores.

    The failed files are those that the command's log names. A command that
    this run didn't start, because of --from-run, has no exit status.

    Returns:
        The number of commands with failed files or an exit status other
        than 0.
    """
    failures = 0
    for name, command in scores["performance"]["commands"].items():
        log = pathlib.Path(scores["runs"][name]["path"]) / "log.txt"
        text = log.read_text(encoding="utf-8") if log.is_file() else ""
        listed = re.findall(r"^.* ERROR failed files: (.+)$", text, re.MULTILINE)
        command["exit_status"] = statuses.get(name)
        command["failed_files"] = len(listed[-1].split(", ")) if listed else 0
        failures += bool(command["failed_files"] or command["exit_status"])
    return failures


def main() -> int:
    """Runs and scores the benchmark named on the command line."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description="Run Gentrex on benchmark reports.")
    parser.add_argument(
        "--version", default="v1", help="Benchmark version, a folder under data/."
    )
    parser.add_argument(
        "--copy",
        default="native",
        help="Copy of the reports to read: native, scan, fax, mixed or image.",
    )
    score.add_arguments(parser)
    parser.add_argument(
        "--serve",
        type=pathlib.Path,
        help="Script that starts the model server of a command, given the"
        " model's name and a port.",
    )
    parser.add_argument(
        "--no-hpo",
        action="store_true",
        help="Run gentrex normalize without HPO terms, which are then not scored.",
    )
    parser.add_argument(
        "--settings",
        type=pathlib.Path,
        help="YAML file with the settings that differ from Gentrex's defaults,"
        " for every command.",
    )
    parser.add_argument(
        "--no-select",
        action="store_true",
        help="Skip gentrex select, so that gentrex extract reads every page.",
    )
    parser.add_argument(
        "--from-run",
        type=pathlib.Path,
        help="Finished run folder of gentrex transcribe, select or extract. The"
        " run starts with the command after it.",
    )
    args = parser.parse_args()

    version_dir = _DATA_DIR / args.version
    if not args.from_run and not (version_dir / "pdf" / args.copy).is_dir():
        _logger.error("%s not found", version_dir / "pdf" / args.copy)
        return 1
    try:
        settings = config.load_settings(args.settings)
    except config.SettingsError as exc:
        _logger.error("%s", exc)
        return 1
    steps: list[_Step] = [
        ("transcribe", "GENTREX_OCR_BASE_URL", settings["transcribe"]["ocr"]["model"]),
        ("select", "GENTREX_LLM_BASE_URL", settings["select"]["model"]),
        ("extract", "GENTREX_LLM_BASE_URL", settings["extract"]["model"]),
        ("normalize", None, None),
    ]
    if args.no_select:
        del steps[1]
    out = score.new_folder()
    if args.from_run:
        try:
            steps = steps_after(steps, args.from_run)
        except ValueError as exc:
            _logger.error("%s", exc)
            out.rmdir()
            return 1
        run_dir = args.from_run
    else:
        run_dir = out / args.copy
        if not link_pdfs(version_dir, args.copy, args.split, run_dir):
            _logger.error(
                "%s has no truth files of the split %s", version_dir, args.split
            )
            shutil.rmtree(out)
            return 1
    versions: dict[str, Any] = {}
    statuses: dict[str, int] = {}
    starts: dict[str, float] = {}
    for command, variable, model in steps:
        arguments = ["--input-dir" if command == "transcribe" else "--input"]
        arguments.append(str(run_dir))
        if command == "normalize" and args.no_hpo:
            arguments.append("--no-hpo")
        if args.settings:
            arguments += ["--settings", str(args.settings)]
        env = dict(os.environ)
        try:
            started = time.perf_counter()
            script = args.serve if model else None
            with servers.served(script, model or "") as base_url:
                if variable and base_url:
                    env[variable] = base_url
                    starts[command] = round(time.perf_counter() - started, 1)
                if variable:
                    versions[command] = _server_version(env.get(variable))
                found, statuses[command] = _gentrex(command, arguments, env)
        except RuntimeError as exc:
            _logger.error("%s", exc)
            return 1
        if found is None:
            return 1
        run_dir = found

    scores, errors = score.score(
        version_dir / "truth", run_dir, args.split, args.gpus, args.label
    )
    scores["performance"]["server_versions"] = versions
    scores["performance"]["gpu_names"] = _gpu_names() if args.serve else []
    # The time a server took to load its model, which `seconds` leaves out.
    for name, command in scores["performance"]["commands"].items():
        command["server_start_seconds"] = starts.get(name)
    failures = add_failures(scores, statuses)
    score.write(out, scores, errors)
    _logger.info(
        "report accuracy %s on %d reports; wrote %s",
        score.percent(scores["main"]["report_accuracy"]["value"]),
        scores["reports"],
        out,
    )
    if failures:
        _logger.error(
            "%d commands had failed files; see failed_files in scores.json", failures
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
