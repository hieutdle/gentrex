"""Command-line entry point for Gentrex."""

import argparse
import importlib.metadata
import logging
import os
import pathlib
import sys

import yaml
from sqlalchemy import exc as sa_exc

from gentrex import config
from gentrex import llm
from gentrex import runs
from gentrex.export import omop
from gentrex.export import pseudonyms as pseudonyms_lib
from gentrex.export import run as export_run
from gentrex.extract import extractor
from gentrex.extract import run as extract_run
from gentrex.load import hpo as hpo_lib
from gentrex.load import run as load_run
from gentrex.normalize import diseases
from gentrex.normalize import genes
from gentrex.normalize import phenotypes
from gentrex.normalize import run as normalize_run
from gentrex.normalize import variants
from gentrex.select import run as select_run
from gentrex.select import score
from gentrex.transcribe import ocr as ocr_lib
from gentrex.transcribe import run as transcribe_run

_logger = logging.getLogger(__name__)

_OCR_BASE_URL_ENV = "GENTREX_OCR_BASE_URL"
_OCR_API_KEY_ENV = "GENTREX_OCR_API_KEY"
_LLM_BASE_URL_ENV = "GENTREX_LLM_BASE_URL"
_LLM_API_KEY_ENV = "GENTREX_LLM_API_KEY"
_DATABASE_URL_ENV = "GENTREX_DATABASE_URL"
_OMOP_DATABASE_URL_ENV = "GENTREX_OMOP_DATABASE_URL"
_PSEUDONYM_KEY_ENV = "GENTREX_PSEUDONYM_KEY"


def _run_transcribe(args: argparse.Namespace) -> int:
    pdf_paths = sorted(
        path for path in args.input_dir.iterdir() if path.suffix.lower() == ".pdf"
    )
    if not pdf_paths:
        _logger.error("no PDFs in %s", args.input_dir)
        return 1

    settings = config.load_settings(args.settings)["transcribe"]
    try:
        earlier = (
            runs.earlier(args.retry, "transcribe", settings) if args.retry else None
        )
    except runs.RetryError as exc:
        _logger.error("%s", exc)
        return 1
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

    with runs.new_run("transcribe", args.input_dir, settings, args.retry) as run_dir:
        failed = transcribe_run.run(
            pdf_paths,
            run_dir / "pages.jsonl",
            settings["native_min_chars"],
            ocr,
            earlier,
        )
        if failed:
            _logger.error("failed files: %s", ", ".join(failed))
            return 1
    return 0


def _run_select(args: argparse.Namespace) -> int:
    pages_path = args.input / "pages.jsonl"
    if not pages_path.is_file():
        _logger.error("%s not found; run gentrex transcribe first", pages_path)
        return 1
    base_url = os.environ.get(_LLM_BASE_URL_ENV)
    if not base_url:
        _logger.error("%s is not set (see .env.example)", _LLM_BASE_URL_ENV)
        return 2

    settings = config.load_settings(args.settings)["select"]
    try:
        earlier = runs.earlier(args.retry, "select", settings) if args.retry else None
    except runs.RetryError as exc:
        _logger.error("%s", exc)
        return 1
    select_config = score.SelectConfig(**settings)
    client = llm.make_client(
        base_url,
        os.environ.get(_LLM_API_KEY_ENV) or "EMPTY",
        select_config.timeout_seconds,
    )
    with runs.new_run("select", args.input, settings, args.retry) as run_dir:
        failed = select_run.run(
            pages_path,
            run_dir / "decisions.jsonl",
            run_dir / "pages.jsonl",
            score.PageScorer(select_config, client),
            earlier,
        )
        if failed:
            _logger.error("failed files: %s", ", ".join(failed))
            return 1
    return 0


def _run_extract(args: argparse.Namespace) -> int:
    pages_path = args.input / "pages.jsonl"
    if not pages_path.is_file():
        _logger.error("%s not found; run gentrex select first", pages_path)
        return 1
    base_url = os.environ.get(_LLM_BASE_URL_ENV)
    if not base_url:
        _logger.error("%s is not set (see .env.example)", _LLM_BASE_URL_ENV)
        return 2

    # Added to the settings, so that run.yaml records it for every run.
    settings = {
        **config.load_settings(args.settings)["extract"],
        "schema": config.load_schema(),
    }
    try:
        earlier = runs.earlier(args.retry, "extract", settings) if args.retry else None
    except runs.RetryError as exc:
        _logger.error("%s", exc)
        return 1
    extract_config = extractor.ExtractConfig(**settings)
    client = llm.make_client(
        base_url,
        os.environ.get(_LLM_API_KEY_ENV) or "EMPTY",
        extract_config.timeout_seconds,
    )
    with runs.new_run("extract", args.input, settings, args.retry) as run_dir:
        failed = extract_run.run(
            pages_path,
            run_dir / "extractions.jsonl",
            extractor.ReportExtractor(extract_config, client),
            earlier,
        )
        if failed:
            _logger.error("failed files: %s", ", ".join(failed))
            return 1
    return 0


def _run_normalize(args: argparse.Namespace) -> int:
    extractions_path = args.input / "extractions.jsonl"
    if not extractions_path.is_file():
        _logger.error("%s not found; run gentrex extract first", extractions_path)
        return 1

    settings = config.load_settings(args.settings)["normalize"]
    hgnc_path = pathlib.Path(settings["hgnc_path"])
    if not hgnc_path.is_file():
        _logger.error(
            "%s not found; download it as docs/user-guide/normalize.md shows",
            hgnc_path,
        )
        return 1
    try:
        hgnc = genes.HgncIndex.from_tsv(hgnc_path)
    except ValueError as exc:
        _logger.error(
            "%s; download it again as docs/user-guide/normalize.md shows", exc
        )
        return 1
    mondo_path = pathlib.Path(settings["mondo_path"])
    if not mondo_path.is_file():
        _logger.error(
            "%s not found; download it as docs/user-guide/normalize.md shows",
            mondo_path,
        )
        return 1
    mondo = diseases.MondoIndex.from_release(mondo_path)
    hpo = None
    if not args.no_hpo:
        hpo_path = pathlib.Path(settings["hpo"]["path"])
        if not hpo_path.is_file():
            _logger.error(
                "%s not found; build it as docs/user-guide/normalize.md shows,"
                " or use --no-hpo",
                hpo_path,
            )
            return 1
        try:
            hpo = phenotypes.HpoIndex(
                hpo_path, settings["hpo"]["models"], settings["hpo"]["top_k"]
            )
        except ValueError as exc:
            _logger.error(
                "%s; build it again as docs/user-guide/normalize.md shows", exc
            )
            return 1
        except ImportError as exc:
            _logger.error("%s; run gentrex normalize with uv run --extra hpo", exc)
            return 1

    clinvar = None
    if settings["clinvar_path"]:
        clinvar_path = pathlib.Path(settings["clinvar_path"])
        if not clinvar_path.is_file():
            _logger.error(
                "%s not found; download it as docs/user-guide/normalize.md shows",
                clinvar_path,
            )
            return 1
        try:
            clinvar = variants.ClinvarIndex(clinvar_path)
        except ValueError as exc:
            _logger.error(
                "%s; download it again as docs/user-guide/normalize.md shows", exc
            )
            return 1

    # Added to the settings, so that run.yaml records the versions used.
    record = {
        **settings,
        "hgnc_sha256": hgnc.sha256,
        "mondo_version": mondo.version,
        "hpo_version": hpo.version if hpo else None,
        "clinvar_sha256": clinvar.sha256 if clinvar else None,
    }
    with runs.new_run("normalize", args.input, record) as run_dir:
        failed = normalize_run.run(
            extractions_path,
            run_dir / "normalized.jsonl",
            hgnc,
            mondo,
            hpo,
            clinvar,
            settings["day_first"],
        )
        if failed:
            _logger.error("failed files: %s", ", ".join(failed))
            return 1
    return 0


def _run_load(args: argparse.Namespace) -> int:
    normalized_path = args.input / "normalized.jsonl"
    if not normalized_path.is_file():
        _logger.error("%s not found; run gentrex normalize first", normalized_path)
        return 1
    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        _logger.error("%s is not set (see .env.example)", _DATABASE_URL_ENV)
        return 2

    settings = config.load_settings(args.settings)["load"]
    release = pathlib.Path(settings["hpo_release"])
    if not release.is_file():
        _logger.error(
            "%s not found; download it as docs/user-guide/normalize.md shows", release
        )
        return 1
    try:
        engine = load_run.make_engine(database_url)
        with engine.connect():
            pass
    except ValueError as exc:
        _logger.error("%s: %s (see docs/user-guide/load.md)", _DATABASE_URL_ENV, exc)
        return 1
    except sa_exc.OperationalError as exc:
        _logger.error("can't connect to the database: %s", exc.orig)
        return 1
    try:
        load_run.prepare_tables(engine)
    except load_run.TableVersionError as exc:
        _logger.error("%s", exc)
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


def _run_export_phenopackets(args: argparse.Namespace) -> int:
    normalized_path = args.input / "normalized.jsonl"
    if not normalized_path.is_file():
        _logger.error("%s not found; run gentrex normalize first", normalized_path)
        return 1
    run_yaml = args.input / "run.yaml"
    run_record = (
        yaml.safe_load(run_yaml.read_text(encoding="utf-8"))
        if run_yaml.is_file()
        else {}
    )
    settings = (run_record or {}).get("settings") or {}
    if "mondo_version" not in settings:
        _logger.error(
            "%s doesn't record the MONDO release, because it is from before"
            " gentrex normalize found diseases; run gentrex normalize again",
            run_yaml,
        )
        return 1
    pseudonyms = None
    if args.pseudonymize:
        key = os.environ.get(_PSEUDONYM_KEY_ENV)
        if not key:
            _logger.error("%s is not set (see .env.example)", _PSEUDONYM_KEY_ENV)
            return 2
        pseudonyms = pseudonyms_lib.Pseudonyms(key)

    versions = {"hpo": settings["hpo_version"], "mondo": settings["mondo_version"]}
    with runs.new_run("export/phenopackets", args.input, versions) as run_dir:
        failed = export_run.run(
            normalized_path, run_dir / "phenopackets", versions, pseudonyms
        )
        if pseudonyms:
            pseudonyms.write(run_dir / "pseudonyms.csv")
        if failed:
            _logger.error("failed files: %s", ", ".join(failed))
            return 1
    return 0


def _run_export_fhir(args: argparse.Namespace) -> int:
    normalized_path = args.input / "normalized.jsonl"
    if not normalized_path.is_file():
        _logger.error("%s not found; run gentrex normalize first", normalized_path)
        return 1

    with runs.new_run("export/fhir", args.input, {}) as run_dir:
        failed = export_run.run_fhir(normalized_path, run_dir / "bundles")
        if failed:
            _logger.error("failed files: %s", ", ".join(failed))
            return 1
    return 0


def _run_export_omop(args: argparse.Namespace) -> int:
    extended = args.format == "omop-extended"
    normalized_path = args.input / "normalized.jsonl"
    if not normalized_path.is_file():
        _logger.error("%s not found; run gentrex normalize first", normalized_path)
        return 1
    database_url = os.environ.get(_OMOP_DATABASE_URL_ENV)
    if not database_url:
        _logger.error("%s is not set (see .env.example)", _OMOP_DATABASE_URL_ENV)
        return 2

    settings = config.load_settings(args.settings)["export"]["omop"]
    schemas = omop.Schemas(
        cdm=settings["cdm_schema"],
        vocabulary=settings["vocabulary_schema"] or settings["cdm_schema"],
        gentrex=settings["gentrex_schema"],
        extension=settings["extension_schema"] if extended else None,
    )
    own = {"gentrex_schema": schemas.gentrex}
    if extended:
        own["extension_schema"] = schemas.extension
    for name, schema in own.items():
        if schema == schemas.cdm:
            _logger.error(
                "export.omop.%s must differ from cdm_schema, so that the CDM schema"
                " holds only CDM tables",
                name,
            )
            return 1
    try:
        engine = load_run.make_engine(database_url)
        if engine.url.get_backend_name() != "postgresql":
            raise ValueError(
                "the OMOP export writes only to PostgreSQL, because OHDSI's tools"
                " store dates in SQLite as numbers"
            )
        with engine.connect():
            pass
    except ValueError as exc:
        _logger.error(
            "%s: %s (see docs/user-guide/export-omop.md)", _OMOP_DATABASE_URL_ENV, exc
        )
        return 1
    except sa_exc.OperationalError as exc:
        _logger.error("can't connect to the database: %s", exc.orig)
        return 1
    person_map = None
    if settings["person_map"]:
        try:
            person_map = omop.read_person_map(pathlib.Path(settings["person_map"]))
        except (OSError, ValueError) as exc:
            _logger.error("%s", exc)
            return 1
    try:
        omop.prepare(engine, schemas, person_map, extended)
    except omop.SetupError as exc:
        _logger.error("%s", exc)
        return 1
    except sa_exc.DBAPIError as exc:
        _logger.error("can't create Gentrex's tables: %s", exc.orig)
        return 1

    with runs.new_run(f"export/{args.format}", args.input, settings):
        failed = omop.run(normalized_path, engine, schemas, person_map, extended)
        if failed:
            _logger.error("failed files: %s", ", ".join(failed))
            return 1
    return 0


def _add_settings(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--settings",
        type=pathlib.Path,
        help="YAML file with the settings that differ from Gentrex's defaults.",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gentrex", description=__doc__)
    parser.add_argument(
        "--version",
        action="version",
        version=f"gentrex {importlib.metadata.version('gentrex')}",
    )
    # In the order you run them, so that --help lists them that way.
    commands = parser.add_subparsers(required=True, title="commands")

    transcribe = commands.add_parser("transcribe", help="Transcribe PDF pages.")
    transcribe.add_argument(
        "--input-dir", type=pathlib.Path, default=pathlib.Path("data/raw")
    )
    ocr_or_retry = transcribe.add_mutually_exclusive_group()
    ocr_or_retry.add_argument(
        "--no-ocr",
        action="store_true",
        help="Skip OCR; scanned pages are written with empty text.",
    )
    ocr_or_retry.add_argument(
        "--retry",
        type=pathlib.Path,
        help="Earlier run folder of gentrex transcribe whose good pages to reuse.",
    )
    _add_settings(transcribe)
    transcribe.set_defaults(func=_run_transcribe)

    select = commands.add_parser("select", help="Select the pages to keep.")
    select.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("transcribe"),
        help="Run folder of gentrex transcribe to read.",
    )
    select.add_argument(
        "--retry",
        type=pathlib.Path,
        help="Earlier run folder of gentrex select whose good decisions to reuse.",
    )
    _add_settings(select)
    select.set_defaults(func=_run_select)

    extract = commands.add_parser("extract", help="Extract report data.")
    extract.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("select"),
        help="Run folder of gentrex select to read.",
    )
    extract.add_argument(
        "--retry",
        type=pathlib.Path,
        help="Earlier run folder of gentrex extract whose good records to reuse.",
    )
    _add_settings(extract)
    extract.set_defaults(func=_run_extract)

    normalize = commands.add_parser("normalize", help="Normalize report data.")
    normalize.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("extract"),
        help="Run folder of gentrex extract to read.",
    )
    normalize.add_argument(
        "--no-hpo",
        action="store_true",
        help="Leave the clinical features without HPO terms.",
    )
    _add_settings(normalize)
    normalize.set_defaults(func=_run_normalize)

    load = commands.add_parser("load", help="Load report data into a database.")
    load.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("normalize"),
        help="Run folder of gentrex normalize to read.",
    )
    _add_settings(load)
    load.set_defaults(func=_run_load)

    export = commands.add_parser(
        "export", help="Export report data in a standard format."
    )
    formats = export.add_subparsers(required=True, title="formats", dest="format")
    phenopackets = formats.add_parser(
        "phenopackets", help="Export report data as Phenopackets."
    )
    phenopackets.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("normalize"),
        help="Run folder of gentrex normalize to read.",
    )
    phenopackets.add_argument(
        "--pseudonymize",
        action="store_true",
        help="Replace patient keys and file names with pseudonyms, for sharing.",
    )
    phenopackets.set_defaults(func=_run_export_phenopackets)
    to_omop = formats.add_parser(
        "omop", help="Export report data into an OMOP CDM database."
    )
    to_omop.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("normalize"),
        help="Run folder of gentrex normalize to read.",
    )
    _add_settings(to_omop)
    to_omop.set_defaults(func=_run_export_omop)
    extended = formats.add_parser(
        "omop-extended",
        help="Export report data into an OMOP CDM database, with extension tables.",
    )
    extended.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("normalize"),
        help="Run folder of gentrex normalize to read.",
    )
    _add_settings(extended)
    extended.set_defaults(func=_run_export_omop)
    to_fhir = formats.add_parser(
        "fhir", help="Export report data as FHIR Genomics Reporting Bundles."
    )
    to_fhir.add_argument(
        "--input",
        type=pathlib.Path,
        default=runs.latest("normalize"),
        help="Run folder of gentrex normalize to read.",
    )
    to_fhir.set_defaults(func=_run_export_fhir)
    return parser


def main() -> None:
    """Runs the command given on the command line."""
    logging.basicConfig(format=runs.LOG_FORMAT)
    # Progress from Gentrex only: libraries log a line for every request.
    logging.getLogger("gentrex").setLevel(logging.INFO)
    args = _build_parser().parse_args()
    try:
        sys.exit(args.func(args))
    except config.SettingsError as exc:
        _logger.error("%s", exc)
        sys.exit(1)
