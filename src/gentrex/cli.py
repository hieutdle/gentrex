"""Command-line entry point for Gentrex."""

import argparse
import logging
import os
import pathlib
import sys

import sqlalchemy as sa

from gentrex import config
from gentrex import llm
from gentrex import runs
from gentrex.extract import extractor
from gentrex.extract import run as extract_run
from gentrex.load import hpo as hpo_lib
from gentrex.load import run as load_run
from gentrex.normalize import genes
from gentrex.normalize import phenotypes
from gentrex.normalize import run as normalize_run
from gentrex.pagedecide import run as pagedecide_run
from gentrex.pagedecide import score
from gentrex.transcribe import ocr as ocr_lib
from gentrex.transcribe import run as transcribe_run

_logger = logging.getLogger(__name__)

_OCR_BASE_URL_ENV = "GENTREX_OCR_BASE_URL"
_OCR_API_KEY_ENV = "GENTREX_OCR_API_KEY"
_LLM_BASE_URL_ENV = "GENTREX_LLM_BASE_URL"
_LLM_API_KEY_ENV = "GENTREX_LLM_API_KEY"
_DATABASE_URL_ENV = "GENTREX_DATABASE_URL"


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


def _run_stage4(args: argparse.Namespace) -> int:
    extractions_path = args.input / "extractions.jsonl"
    if not extractions_path.is_file():
        _logger.error("%s not found; run stage 3 first", extractions_path)
        return 1

    settings = config.load_settings()["normalize"]
    hgnc_path = pathlib.Path(settings["hgnc_path"])
    if not hgnc_path.is_file():
        _logger.error("%s not found; download it as docs/stage4.md shows", hgnc_path)
        return 1
    try:
        hgnc = genes.HgncIndex.from_tsv(hgnc_path)
    except ValueError as exc:
        _logger.error("%s; download it again as docs/stage4.md shows", exc)
        return 1
    hpo = None
    if not args.no_hpo:
        hpo_path = pathlib.Path(settings["hpo"]["path"])
        if not hpo_path.is_file():
            _logger.error(
                "%s not found; build it as docs/stage4.md shows, or use --no-hpo",
                hpo_path,
            )
            return 1
        try:
            hpo = phenotypes.HpoIndex(
                hpo_path, settings["hpo"]["models"], settings["hpo"]["top_k"]
            )
        except ValueError as exc:
            _logger.error("%s; build it again as docs/stage4.md shows", exc)
            return 1
        except ImportError as exc:
            _logger.error("%s; run stage 4 with uv run --extra hpo", exc)
            return 1

    # Added to the settings, so that run.yaml records the HGNC version used.
    record = {**settings, "hgnc_sha256": hgnc.sha256}
    with runs.new_run("normalize", args.input, record) as run_dir:
        failed = normalize_run.run(
            extractions_path, run_dir / "normalized.jsonl", hgnc, hpo
        )
        if failed:
            _logger.error("failed files: %s", ", ".join(failed))
            return 1
    return 0


def _run_stage5(args: argparse.Namespace) -> int:
    normalized_path = args.input / "normalized.jsonl"
    if not normalized_path.is_file():
        _logger.error("%s not found; run stage 4 first", normalized_path)
        return 1
    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        _logger.error("%s is not set (see .env.example)", _DATABASE_URL_ENV)
        return 2

    settings = config.load_settings()["load"]
    release = pathlib.Path(settings["hpo_release"])
    if not release.is_file():
        _logger.error("%s not found; download it as docs/stage4.md shows", release)
        return 1
    try:
        engine = load_run.make_engine(database_url)
        with engine.connect():
            pass
    except ValueError as exc:
        _logger.error("%s: %s (see docs/stage5.md)", _DATABASE_URL_ENV, exc)
        return 1
    except sa.exc.OperationalError as exc:
        _logger.error("can't connect to the database: %s", exc.orig)
        return 1
    tree = hpo_lib.HpoTree.from_release(release)

    # Added to the settings, so that run.yaml records the HPO release used.
    record = {**settings, "hpo_sha256": tree.sha256}
    with runs.new_run("load", args.input, record):
        failed = load_run.run(normalized_path, engine, tree)
        if failed:
            _logger.error("failed files: %s", ", ".join(failed))
            return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gentrex", description=__doc__)
    subparsers = parser.add_subparsers(required=True)

    stage1 = subparsers.add_parser("stage1", help="Transcribe PDF pages.")
    stage1.add_argument(
        "--input-dir", type=pathlib.Path, default=pathlib.Path("data/raw")
    )
    stage1.add_argument(
        "--no-ocr",
        action="store_true",
        help="Skip OCR; scanned pages are written with empty text.",
    )
    stage1.set_defaults(func=_run_stage1)

    stage2 = subparsers.add_parser("stage2", help="Decide which pages to keep.")
    stage2.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("transcribe"),
        help="Stage 1 run folder to read.",
    )
    stage2.set_defaults(func=_run_stage2)

    stage3 = subparsers.add_parser("stage3", help="Extract report data.")
    stage3.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("pagedecide"),
        help="Stage 2 run folder to read.",
    )
    stage3.set_defaults(func=_run_stage3)

    stage4 = subparsers.add_parser("stage4", help="Normalize report data.")
    stage4.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("extract"),
        help="Stage 3 run folder to read.",
    )
    stage4.add_argument(
        "--no-hpo",
        action="store_true",
        help="Leave the clinical features without HPO terms.",
    )
    stage4.set_defaults(func=_run_stage4)

    stage5 = subparsers.add_parser("stage5", help="Load report data into a database.")
    stage5.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("normalize"),
        help="Stage 4 run folder to read.",
    )
    stage5.set_defaults(func=_run_stage5)
    return parser


def main() -> None:
    """Runs the command given on the command line."""
    logging.basicConfig(format=runs.LOG_FORMAT)
    # Progress from Gentrex only: libraries log a line for every request.
    logging.getLogger("gentrex").setLevel(logging.INFO)
    args = _build_parser().parse_args()
    sys.exit(args.func(args))
