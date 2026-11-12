"""Orchestration: NormalizedReports to rows of the database tables."""

import dataclasses
import datetime
import json
import logging
import pathlib
import re
import time
from typing import Any

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy import exc as sa_exc

from gentrex import records
from gentrex.load import hpo
from gentrex.load import tables

# The databases that `gentrex load` is tested on, with the driver that Gentrex
# picks for a URL that names none, such as postgresql://. Every driver but
# SQLite's comes from the extra of the database's name in pyproject.toml.
DRIVERS = {"sqlite": "pysqlite", "postgresql": "psycopg", "mysql": "pymysql"}

_HALF_SURROGATE = re.compile("[\ud800-\udfff]")

# Fields of `data` that `gentrex normalize` leaves as printed.
_REPORT_FIELDS = (
    "mrn",
    "submitter_patient_id",
    "lab_accession_number",
    "sex",
    "test_name",
    "test_type",
    "overall_result_raw",
    "karyotype",
    "clinical_indication",
    "lab_name",
    "genome_build",
)
# Fields of `data` that `gentrex normalize` finds a standard value for. The
# standard value goes to the column of the field's name, and the printed one
# to <name>_raw.
_DATE_FIELDS = (
    "date_of_birth",
    "collection_date",
    "received_date",
    "test_started_date",
    "report_date",
)
_STANDARDIZED_FIELDS = ("specimen_type", *_DATE_FIELDS)
_RESULT_FIELDS = ("overall_result", "overall_result_basis", "overall_result_conflict")
# Fields of each variant in `data`, besides gene_symbol.
_VARIANT_FIELDS = (
    "page",
    "transcript",
    "hgvs_c",
    "hgvs_p",
    "dna_change_raw",
    "chromosomal_position",
    "copy_number",
    "classification",
    "classification_raw",
    "zygosity",
    "zygosity_raw",
    "parental_origin",
    "parental_origin_raw",
    "associated_phenotype",
    "mode_of_inheritance",
    "mode_of_inheritance_raw",
    "is_secondary_finding",
    "variant_type_raw",
)

_logger = logging.getLogger(__name__)


class TableVersionError(Exception):
    """The database holds the tables of another version of `gentrex load`."""


def make_engine(url: str) -> sa.Engine:
    """Returns an engine for `url`, a database URL as SQLAlchemy reads them.

    A server's URL has the form database://user:password@host:port/name. A
    SQLite file's is sqlite:///path, and its folder is created if needed.

    Raises:
        ValueError: The URL is malformed, names a database that `gentrex load`
            doesn't support, or needs a driver that isn't installed.
    """
    try:
        parsed = sa.engine.make_url(url)
    except sa_exc.ArgumentError as exc:
        raise ValueError(f"not a database URL: {exc}") from exc
    backend = parsed.get_backend_name()
    if backend not in DRIVERS:
        raise ValueError(
            f"{backend} is not a supported database ({', '.join(DRIVERS)})"
        )
    if "+" not in parsed.drivername:
        parsed = parsed.set(drivername=f"{backend}+{DRIVERS[backend]}")
    if backend == "sqlite" and parsed.database:
        pathlib.Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    try:
        engine = sa.create_engine(parsed)
    except ModuleNotFoundError as exc:
        raise ValueError(
            f"{exc}; its driver comes with uv run --extra {backend}"
        ) from exc
    if backend == "sqlite":
        # SQLite ignores ON DELETE CASCADE unless each connection asks for it.
        event.listen(
            engine,
            "connect",
            lambda dbapi_conn, _: dbapi_conn.execute("PRAGMA foreign_keys = ON"),
        )
    return engine


def patient_key(file: str, data: dict[str, Any]) -> str:
    """Returns the key that links the reports of one patient.

    The key is the report's MRN, else its submitter patient ID, else its file
    name, after a prefix that says which, as in "mrn:SYN-MRN-0001".
    """
    for field, prefix in (("mrn", "mrn"), ("submitter_patient_id", "submitter")):
        if value := (data.get(field) or "").strip():
            return f"{prefix}:{value}"
    return f"file:{file}"


def read_report(line: str) -> records.NormalizedReport:
    """Parses one line of normalized.jsonl.

    Databases and Phenopackets can't hold half of a surrogate pair, which data
    from `gentrex extract` may hold, so it becomes U+FFFD, the replacement
    character.
    """
    text = json.dumps(json.loads(line), ensure_ascii=False)
    return records.NormalizedReport(**json.loads(_HALF_SURROGATE.sub("�", text)))


def _date(value: str | None) -> datetime.date | None:
    return datetime.date.fromisoformat(value) if value else None


def _rows(
    report: records.NormalizedReport, source: str
) -> list[tuple[sa.Table, list[dict[str, Any]]]]:
    """Returns the rows of one report, by table, in the order to insert them."""
    data = report.data or {}
    normalized = report.normalized or {}
    variants = data.get("variants") or []
    genes = normalized.get("variants") or [{}] * len(variants)
    features = data.get("patient_phenotypes") or []
    matches = normalized.get("patient_phenotypes") or [{}] * len(features)
    report_row = {
        "file": report.file,
        "patient_key": patient_key(report.file, data),
        "pages": report.pages,
        "error": report.error,
        **{field: data.get(field) for field in _REPORT_FIELDS},
        "specimen_type": normalized.get("specimen_type"),
        **{field: _date(normalized.get(field)) for field in _DATE_FIELDS},
        **{f"{field}_raw": data.get(field) for field in _STANDARDIZED_FIELDS},
        **{field: normalized.get(field) for field in _RESULT_FIELDS},
        "record": dataclasses.asdict(report),
        "normalize_run": source,
        "loaded_at": datetime.datetime.now(datetime.UTC),
    }
    variant_rows = [
        {
            "file": report.file,
            "variant_number": number,
            "gene_symbol": gene.get("gene_symbol"),
            "gene_symbol_raw": variant.get("gene_symbol"),
            "hgnc_id": gene.get("hgnc_id"),
            "gene_status": gene.get("gene_status"),
            "disease_id": gene.get("disease_id"),
            "disease_label": gene.get("disease_label"),
            "disease_status": gene.get("disease_status"),
            **{field: variant.get(field) for field in _VARIANT_FIELDS},
        }
        for number, (variant, gene) in enumerate(zip(variants, genes, strict=True), 1)
    ]
    phenotype_rows = []
    candidate_rows = []
    for number, (feature, match) in enumerate(zip(features, matches, strict=True), 1):
        phenotype_rows.append(
            {
                "file": report.file,
                "phenotype_number": number,
                "text": feature.get("text"),
                "present": feature.get("present"),
                "hpo_id": match.get("hpo_id"),
                "hpo_label": match.get("label"),
                "models_agree": match.get("models_agree"),
            }
        )
        candidate_rows += [
            {
                "file": report.file,
                "phenotype_number": number,
                "rank": rank,
                "hpo_id": candidate["hpo_id"],
                "hpo_label": candidate["label"],
                "models": candidate["models"],
            }
            for rank, candidate in enumerate(match.get("candidates") or [], 1)
        ]
    return [
        (tables.reports, [report_row]),
        (tables.variants, variant_rows),
        (tables.patient_phenotypes, phenotype_rows),
        (tables.phenotype_candidates, candidate_rows),
    ]


def _insert(conn: sa.Connection, table: sa.Table, rows: list[dict[str, Any]]) -> None:
    if rows:
        conn.execute(table.insert(), rows)


def _load_tree(conn: sa.Connection, tree: hpo.HpoTree) -> bool:
    """Replaces the HPO terms and ancestors, unless they are from `tree`'s release.

    Returns:
        Whether the terms were loaded.
    """
    loaded = conn.execute(sa.select(tables.hpo_release.c.sha256)).scalars().all()
    if loaded == [tree.sha256]:
        return False
    for table in (tables.hpo_release, tables.hpo_ancestors, tables.hpo_terms):
        conn.execute(table.delete())
    _insert(
        conn,
        tables.hpo_terms,
        [{"hpo_id": term, "hpo_label": label} for term, label in tree.labels.items()],
    )
    _insert(
        conn,
        tables.hpo_ancestors,
        [
            {"hpo_id": term, "ancestor_id": ancestor}
            for term, ancestors in tree.ancestors.items()
            for ancestor in ancestors
        ],
    )
    conn.execute(
        tables.hpo_release.insert(),
        {"sha256": tree.sha256, "loaded_at": datetime.datetime.now(datetime.UTC)},
    )
    return True


def _load_report(
    conn: sa.Connection, report: records.NormalizedReport, source: str
) -> None:
    """Replaces the rows of the report's file."""
    rows = _rows(report, source)
    conn.execute(tables.reports.delete().where(tables.reports.c.file == report.file))
    for table, table_rows in rows:
        _insert(conn, table, table_rows)


def prepare_tables(engine: sa.Engine) -> None:
    """Creates the tables of a new database, or checks their version in an old one.

    A database from before schema_version existed counts as version 1.

    Raises:
        TableVersionError: The database holds the tables of another version.
    """
    with engine.begin() as conn:
        existed = sa.inspect(conn).has_table(tables.reports.name)
        tables.metadata.create_all(conn)
        stored = conn.execute(sa.select(tables.schema_version.c.version)).scalar()
        if stored is None and not existed:
            conn.execute(
                tables.schema_version.insert(), {"version": tables.SCHEMA_VERSION}
            )
            return
    found = stored or 1
    if found != tables.SCHEMA_VERSION:
        raise TableVersionError(
            f"the database holds version {found} of the Gentrex tables, but this"
            f" Gentrex writes version {tables.SCHEMA_VERSION}; delete the database"
            " and load the records again, as docs/user-guide/load.md shows"
        )


def run(input_path: pathlib.Path, engine: sa.Engine, tree: hpo.HpoTree) -> list[str]:
    """Loads every report of a run of `gentrex normalize`, in input order.

    Creates the tables of a new database, and loads the HPO terms unless
    the database holds them from the same release already. Each report
    replaces the rows of its file in one transaction, so that a report that
    fails to load keeps the rows of an earlier run. Reports of other files
    stay.

    Args:
        input_path: JSONL file of NormalizedReports, from `gentrex normalize`.
        engine: The database, from make_engine.
        tree: The HPO terms to load.

    Returns:
        Names of the files that have no data, failed to load or have an error
        from `gentrex extract` or `gentrex normalize`, in input order. Reports
        with an error and data are still loaded.

    Raises:
        TableVersionError: The database holds the tables of another version.
    """
    start = time.perf_counter()
    with input_path.open(encoding="utf-8") as fh:
        reports = [read_report(line) for line in fh]
    source = str(input_path.parent.resolve())
    _logger.info("loading into %s", engine.url.render_as_string(hide_password=True))
    prepare_tables(engine)
    with engine.begin() as conn:
        if _load_tree(conn, tree):
            _logger.info(
                "loaded %d HPO terms with %d ancestor rows",
                len(tree.labels),
                sum(len(ancestors) for ancestors in tree.ancestors.values()),
            )
        else:
            _logger.info("kept the HPO terms, which are from the same release")
    failed: list[str] = []
    loaded = 0
    for report in reports:
        if report.data is None:
            _logger.warning(
                "skipped %s, which has no data: %s", report.file, report.error
            )
            failed.append(report.file)
            continue
        try:
            with engine.begin() as conn:
                _load_report(conn, report, source)
        except Exception as exc:  # One report's failure must not cost the others.
            _logger.error("failed %s: %s: %s", report.file, type(exc).__name__, exc)
            failed.append(report.file)
            continue
        _logger.info("loaded %s", report.file)
        loaded += 1
        if report.error:
            failed.append(report.file)
    matched = {
        match["hpo_id"]
        for report in reports
        for match in (report.normalized or {}).get("patient_phenotypes") or []
    }
    if missing := sorted(matched - tree.labels.keys()):
        _logger.warning(
            "matched HPO terms missing from the HPO release, so hpo_ancestors has"
            " no rows for them: %s",
            ", ".join(missing),
        )
    _logger.info(
        "loaded %d of %d reports in %.0f s",
        loaded,
        len(reports),
        time.perf_counter() - start,
    )
    return failed
