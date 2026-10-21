"""Stage 5 orchestration: NormalizedReports to rows of the PostgreSQL tables."""

import dataclasses
import json
import logging
import pathlib
import re
import time
from typing import Any

import psycopg
from psycopg import sql
from psycopg.types import json as pg_json

from gentrex import records
from gentrex.load import hpo

_TABLES_SQL = pathlib.Path(__file__).with_name("tables.sql")

_HALF_SURROGATE = re.compile("[\ud800-\udfff]")

# Fields of `data` that stage 4 leaves as printed.
_REPORT_FIELDS = (
    "mrn",
    "submitter_patient_id",
    "lab_accession_number",
    "sex",
    "test_name",
    "test_type",
    "overall_result_raw",
    "clinical_indication",
    "lab_name",
)
# Fields of `data` that stage 4 finds a standard value for. The standard value
# goes to the column of the field's name, and the printed one to <name>_raw.
_STANDARDIZED_FIELDS = (
    "date_of_birth",
    "specimen_type",
    "collection_date",
    "received_date",
    "test_started_date",
    "report_date",
)
_RESULT_FIELDS = ("overall_result", "overall_result_basis", "overall_result_conflict")
# Fields of each variant in `data`, besides gene_symbol.
_VARIANT_FIELDS = (
    "page",
    "transcript",
    "hgvs_c",
    "hgvs_p",
    "dna_change_raw",
    "chromosomal_position",
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


def patient_key(file: str, data: dict[str, Any]) -> str:
    """Returns the key that links the reports of one patient.

    The key is the report's MRN, else its submitter patient ID, else its file
    name, after a prefix that says which, as in "mrn:SYN-MRN-0001".
    """
    for field, prefix in (("mrn", "mrn"), ("submitter_patient_id", "submitter")):
        if value := (data.get(field) or "").strip():
            return f"{prefix}:{value}"
    return f"file:{file}"


def _read(line: str) -> records.NormalizedReport:
    """Parses one line of normalized.jsonl.

    PostgreSQL can't store half of a surrogate pair, which stage 3 data may
    hold, so it becomes U+FFFD, the replacement character.
    """
    text = json.dumps(json.loads(line), ensure_ascii=False)
    return records.NormalizedReport(**json.loads(_HALF_SURROGATE.sub("\ufffd", text)))


def _rows(
    report: records.NormalizedReport, source: str
) -> dict[str, list[dict[str, Any]]]:
    """Returns the rows of one report, by table, in the order to insert them."""
    data = report.data or {}
    normalized = report.normalized or {}
    variants = data.get("variants") or []
    genes = normalized.get("variants") or [{}] * len(variants)
    features = data.get("patient_phenotypes") or []
    matches = normalized.get("patient_phenotypes") or [{}] * len(features)
    rows: dict[str, list[dict[str, Any]]] = {
        "reports": [
            {
                "file": report.file,
                "patient_key": patient_key(report.file, data),
                "pages": report.pages,
                "error": report.error,
                **{field: data.get(field) for field in _REPORT_FIELDS},
                **{field: normalized.get(field) for field in _STANDARDIZED_FIELDS},
                **{f"{field}_raw": data.get(field) for field in _STANDARDIZED_FIELDS},
                **{field: normalized.get(field) for field in _RESULT_FIELDS},
                "record": pg_json.Jsonb(dataclasses.asdict(report)),
                "normalize_run": source,
            }
        ],
        "variants": [
            {
                "file": report.file,
                "variant_number": number,
                "gene_symbol": gene.get("gene_symbol"),
                "gene_symbol_raw": variant.get("gene_symbol"),
                "hgnc_id": gene.get("hgnc_id"),
                "gene_status": gene.get("gene_status"),
                **{field: variant.get(field) for field in _VARIANT_FIELDS},
            }
            for number, (variant, gene) in enumerate(
                zip(variants, genes, strict=True), 1
            )
        ],
        "patient_phenotypes": [],
        "phenotype_candidates": [],
    }
    for number, (feature, match) in enumerate(zip(features, matches, strict=True), 1):
        rows["patient_phenotypes"].append(
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
        rows["phenotype_candidates"] += [
            {
                "file": report.file,
                "phenotype_number": number,
                "rank": rank,
                "hpo_id": candidate["hpo_id"],
                "hpo_label": candidate["label"],
                "models": pg_json.Jsonb(candidate["models"]),
            }
            for rank, candidate in enumerate(match.get("candidates") or [], 1)
        ]
    return rows


def _insert(conn: psycopg.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    """Inserts rows into `table`; the keys of each row name its columns."""
    if not rows:
        return
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, rows[0])),
        sql.SQL(", ").join(map(sql.Placeholder, rows[0])),
    )
    with conn.cursor() as cursor:
        cursor.executemany(query, rows)


def _load_tree(conn: psycopg.Connection, tree: hpo.HpoTree) -> None:
    """Replaces the HPO terms and their ancestors, in one transaction."""
    with conn.transaction(), conn.cursor() as cursor:
        cursor.execute("TRUNCATE hpo_terms, hpo_ancestors")
        with cursor.copy("COPY hpo_terms (hpo_id, hpo_label) FROM STDIN") as copy:
            for term in tree.labels.items():
                copy.write_row(term)
        with cursor.copy("COPY hpo_ancestors (hpo_id, ancestor_id) FROM STDIN") as copy:
            for term, ancestors in tree.ancestors.items():
                for ancestor in ancestors:
                    copy.write_row((term, ancestor))


def _load_report(
    conn: psycopg.Connection, report: records.NormalizedReport, source: str
) -> None:
    """Replaces the rows of the report's file, in one transaction."""
    rows = _rows(report, source)
    with conn.transaction():
        conn.execute("DELETE FROM reports WHERE file = %s", (report.file,))
        for table, table_rows in rows.items():
            _insert(conn, table, table_rows)


def run(
    input_path: pathlib.Path, conn: psycopg.Connection, tree: hpo.HpoTree
) -> list[str]:
    """Loads every report of a stage 4 run into the database, in input order.

    Creates the tables that don't exist yet and replaces the HPO terms. Each
    report replaces the rows of its file in one transaction, so that a report
    that fails to load keeps the rows of an earlier run. Reports of other files
    stay.

    Args:
        input_path: JSONL file of NormalizedReports, from stage 4.
        conn: Connection in autocommit mode, so that each report is committed
            on its own.
        tree: The HPO terms to load.

    Returns:
        Names of the files that have no data, failed to load or have an error
        from stage 3 or 4, in input order. Reports with an error and data are
        still loaded.
    """
    start = time.perf_counter()
    with input_path.open(encoding="utf-8") as fh:
        reports = [_read(line) for line in fh]
    source = str(input_path.parent.resolve())
    _logger.info(
        "loading into database %s on %s:%s",
        conn.info.dbname,
        conn.info.host,
        conn.info.port,
    )
    conn.execute(_TABLES_SQL.read_bytes())
    _load_tree(conn, tree)
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
