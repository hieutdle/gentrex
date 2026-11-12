"""Run Gentrex on benchmark reports, from the PDFs to the scores.

    uv run --extra hpo --env-file .env python gentrex-bench/run.py --version v1

Runs gentrex transcribe, select, extract and normalize on one copy of the
reports of one split, and scores the result with scorer/score.py. The scores
go to a new folder under results/gentrex-bench/. With --serve, the script
starts the model server of each command and stops it afterwards, so that one
machine can serve the three models in turn. --settings and --no-select run
another setup, to compare it with the default one.
docs/development/run-benchmark.md explains it.
"""

import argparse
import contextlib
import json
import logging
import os
import pathlib
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).parent / "scorer"))

import score  # noqa: E402

from gentrex import config  # noqa: E402
from gentrex import runs  # noqa: E402

_logger = logging.getLogger("run")
_DATA_DIR = pathlib.Path("data/gentrex-bench")
_POLL_SECONDS = 5.0


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


def _answers(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5):
            return True
    except OSError:
        return False


@contextlib.contextmanager
def served(script: pathlib.Path | None, model: str) -> Iterator[str | None]:
    """Starts the model server of one command, and stops it afterwards.

    The script gets the model's name and a free port, and must serve the
    model there until it is stopped.

    Args:
        script: The script that starts a model server, or None to use the
            servers that are already running.
        model: The model's name in settings.yaml.

    Yields:
        The server's address, or None without a script.

    Raises:
        RuntimeError: The script ended before the server answered.
    """
    if script is None:
        yield None
        return
    with socket.socket() as probe:
        probe.bind(("", 0))
        port = probe.getsockname()[1]
    base_url = f"http://localhost:{port}/v1"
    # In a process group of its own, so that stopping reaches its children.
    server = subprocess.Popen(
        [str(script.resolve()), model, str(port)], start_new_session=True
    )
    try:
        _logger.info("waiting for %s at %s", model, base_url)
        while not _answers(f"{base_url}/models"):
            if server.poll() is not None:
                raise RuntimeError(f"{script} ended before {model} was ready")
            time.sleep(_POLL_SECONDS)
        yield base_url
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(server.pid, signal.SIGTERM)
        server.wait()


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
) -> pathlib.Path | None:
    """Runs a Gentrex command, and returns its run folder if it finished."""
    latest = runs.latest(command)
    before = latest.resolve() if latest.exists() else None
    gentrex = pathlib.Path(sys.executable).with_name("gentrex")
    status = subprocess.run([str(gentrex), command, *arguments], env=env).returncode
    after = latest.resolve() if latest.exists() else None
    if after is None or after == before:
        _logger.error("gentrex %s did not finish (exit code %d)", command, status)
        return None
    if status:
        _logger.warning("gentrex %s had failed files, which count as missed", command)
    return after


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
    args = parser.parse_args()

    version_dir = _DATA_DIR / args.version
    if not (version_dir / "pdf" / args.copy).is_dir():
        _logger.error("%s not found", version_dir / "pdf" / args.copy)
        return 1
    try:
        settings = config.load_settings(args.settings)
    except config.SettingsError as exc:
        _logger.error("%s", exc)
        return 1
    out = score.new_folder()
    pdfs = out / args.copy
    if not link_pdfs(version_dir, args.copy, args.split, pdfs):
        _logger.error("%s has no truth files of the split %s", version_dir, args.split)
        shutil.rmtree(out)
        return 1

    steps: list[tuple[str, str | None, str | None]] = [
        ("transcribe", "GENTREX_OCR_BASE_URL", settings["transcribe"]["ocr"]["model"]),
        ("select", "GENTREX_LLM_BASE_URL", settings["select"]["model"]),
        ("extract", "GENTREX_LLM_BASE_URL", settings["extract"]["model"]),
        ("normalize", None, None),
    ]
    if args.no_select:
        del steps[1]
    versions: dict[str, Any] = {}
    run_dir = pdfs
    for command, variable, model in steps:
        arguments = ["--input-dir" if command == "transcribe" else "--input"]
        arguments.append(str(run_dir))
        if command == "normalize" and args.no_hpo:
            arguments.append("--no-hpo")
        if args.settings:
            arguments += ["--settings", str(args.settings)]
        env = dict(os.environ)
        try:
            with served(args.serve if model else None, model or "") as base_url:
                if variable and base_url:
                    env[variable] = base_url
                if variable:
                    versions[command] = _server_version(env.get(variable))
                found = _gentrex(command, arguments, env)
        except RuntimeError as exc:
            _logger.error("%s", exc)
            return 1
        if found is None:
            return 1
        run_dir = found

    scores, errors = score.score(version_dir / "truth", run_dir, args.split, args.gpus)
    scores["performance"]["server_versions"] = versions
    scores["performance"]["gpu_names"] = _gpu_names() if args.serve else []
    score.write(out, scores, errors)
    _logger.info(
        "report accuracy %s on %d reports; wrote %s",
        score.percent(scores["main"]["report_accuracy"]["value"]),
        scores["reports"],
        out,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
