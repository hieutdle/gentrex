"""Command-line entry point for Gentrex."""

import argparse
import logging
import os
import pathlib
import sys

from gentrex import config
from gentrex.transcribe import ocr as ocr_lib
from gentrex.transcribe import run as transcribe_run

_logger = logging.getLogger(__name__)

_OCR_BASE_URL_ENV = "GENTREX_OCR_BASE_URL"
_OCR_API_KEY_ENV = "GENTREX_OCR_API_KEY"


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

    failed = transcribe_run.run(
        pdf_paths, args.output, settings["native_min_chars"], ocr
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
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("results/pages.jsonl"),
    )
    stage1.add_argument(
        "--no-ocr",
        action="store_true",
        help="Skip OCR; scanned pages are written with empty text.",
    )
    stage1.set_defaults(func=_run_stage1)
    return parser


def main() -> None:
    """Runs the command given on the command line."""
    logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s")
    # Progress from Gentrex only: libraries log a line for every request.
    logging.getLogger("gentrex").setLevel(logging.INFO)
    args = _build_parser().parse_args()
    sys.exit(args.func(args))
