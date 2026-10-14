"""Command-line entry point for Gentrex."""

import argparse
import logging
import os
import pathlib
import sys

from gentrex import config
from gentrex import llm
from gentrex import runs
from gentrex.extract import extractor
from gentrex.extract import run as extract_run
from gentrex.pagedecide import run as pagedecide_run
from gentrex.pagedecide import score
from gentrex.transcribe import ocr as ocr_lib
from gentrex.transcribe import run as transcribe_run

_logger = logging.getLogger(__name__)

_OCR_BASE_URL_ENV = "GENTREX_OCR_BASE_URL"
_OCR_API_KEY_ENV = "GENTREX_OCR_API_KEY"
_LLM_BASE_URL_ENV = "GENTREX_LLM_BASE_URL"
_LLM_API_KEY_ENV = "GENTREX_LLM_API_KEY"


def _run_stage1(args: argparse.Namespace) -> int:
    pdf_paths = sorted(
        path for path in args.input_dir.iterdir() if path.suffix.lower() == ".pdf"
    )
    if not pdf_paths:
        _logger.error("no PDFs in %s", args.input_dir)
        return 1

    settings = config.load_settings()["transcribe"]
    ocr = None
    if not args.no_ocr:
        base_url = os.environ.get(_OCR_BASE_URL_ENV)
        if not base_url:
            _logger.error("%s is not set (see .env.example)", _OCR_BASE_URL_ENV)
            return 2
        ocr = ocr_lib.OcrEngine(
            ocr_lib.OcrConfig(**settings["ocr"]),
            base_url,
            os.environ.get(_OCR_API_KEY_ENV) or "EMPTY",
        )

    with runs.new_run("transcribe", args.input_dir, settings) as run_dir:
        failed = transcribe_run.run(
            pdf_paths, run_dir / "pages.jsonl", settings["native_min_chars"], ocr
        )
        if failed:
            _logger.error("failed files: %s", ", ".join(failed))
            return 1
    return 0


def _run_stage2(args: argparse.Namespace) -> int:
    pages_path = args.input / "pages.jsonl"
    if not pages_path.is_file():
        _logger.error("%s not found; run stage 1 first", pages_path)
        return 1
    base_url = os.environ.get(_LLM_BASE_URL_ENV)
    if not base_url:
        _logger.error("%s is not set (see .env.example)", _LLM_BASE_URL_ENV)
        return 2

    settings = config.load_settings()["pagedecide"]
    decide_config = score.DecideConfig(**settings)
    client = llm.make_client(
        base_url,
        os.environ.get(_LLM_API_KEY_ENV) or "EMPTY",
        decide_config.timeout_seconds,
    )
    with runs.new_run("pagedecide", args.input, settings) as run_dir:
        failed = pagedecide_run.run(
            pages_path,
            run_dir / "decisions.jsonl",
            run_dir / "pages.jsonl",
            score.PageScorer(decide_config, client),
        )
        if failed:
            _logger.error("failed files: %s", ", ".join(failed))
            return 1
    return 0


def _run_stage3(args: argparse.Namespace) -> int:
    pages_path = args.input / "pages.jsonl"
    if not pages_path.is_file():
        _logger.error("%s not found; run stage 2 first", pages_path)
        return 1
    base_url = os.environ.get(_LLM_BASE_URL_ENV)
    if not base_url:
        _logger.error("%s is not set (see .env.example)", _LLM_BASE_URL_ENV)
        return 2

    # Added to the settings, so that run.yaml records it for every run.
    settings = {**config.load_settings()["extract"], "schema": config.load_schema()}
    extract_config = extractor.ExtractConfig(**settings)
    client = llm.make_client(
        base_url,
        os.environ.get(_LLM_API_KEY_ENV) or "EMPTY",
        extract_config.timeout_seconds,
    )
    with runs.new_run("extract", args.input, settings) as run_dir:
        failed = extract_run.run(
            pages_path,
            run_dir / "extractions.jsonl",
            extractor.ReportExtractor(extract_config, client),
        )
        if failed:
            _logger.error("failed files: %s", ", ".join(failed))
            return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gentrex", description=__doc__)
    subparsers = parser.add_subparsers(required=True)

    stage1 = subparsers.add_parser("stage1", help="PDFs to per-page text.")
    stage1.add_argument(
        "--input-dir", type=pathlib.Path, default=pathlib.Path("data/raw")
    )
    stage1.add_argument(
        "--no-ocr",
        action="store_true",
        help="Skip OCR; scanned pages are written with empty text.",
    )
    stage1.set_defaults(func=_run_stage1)

    stage2 = subparsers.add_parser(
        "stage2", help="Per-page text to keep/drop decisions."
    )
    stage2.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("transcribe"),
        help="Stage 1 run folder to read.",
    )
    stage2.set_defaults(func=_run_stage2)

    stage3 = subparsers.add_parser(
        "stage3", help="Kept pages to one structured record per report."
    )
    stage3.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("pagedecide"),
        help="Stage 2 run folder to read.",
    )
    stage3.set_defaults(func=_run_stage3)
    return parser


def main() -> None:
    """Runs the command given on the command line."""
    logging.basicConfig(format=runs.LOG_FORMAT)
    # Progress from Gentrex only: libraries log a line for every request.
    logging.getLogger("gentrex").setLevel(logging.INFO)
    args = _build_parser().parse_args()
    sys.exit(args.func(args))
