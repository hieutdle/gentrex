"""Orchestration: records of `gentrex extract` to a JSONL file of NormalizedReports."""

import json
import logging
import pathlib
import time
from typing import Any

from gentrex import records
from gentrex.normalize import diseases
from gentrex.normalize import genes as genes_lib
from gentrex.normalize import phenotypes
from gentrex.normalize import rules

_logger = logging.getLogger(__name__)


def _normalize(
    data: dict[str, Any],
    hgnc: genes_lib.HgncIndex,
    mondo: diseases.MondoIndex,
    hpo: phenotypes.HpoIndex | None,
) -> dict[str, Any]:
    """Returns the normalized values of one record's data."""
    variants = data.get("variants") or []
    normalized: dict[str, Any] = {
        "date_of_birth": rules.parse_date(data.get("date_of_birth")),
        "specimen_type": rules.specimen_category(data.get("specimen_type")),
        "collection_date": rules.parse_date(data.get("collection_date")),
        "received_date": rules.parse_date(data.get("received_date")),
        "test_started_date": rules.parse_date(data.get("test_started_date")),
        "report_date": rules.parse_date(data.get("report_date")),
        **rules.overall_result(data.get("overall_result_raw"), variants),
        "patient_phenotypes": None,
        "variants": [
            {
                **hgnc.normalize(variant.get("gene_symbol")),
                **mondo.normalize(variant.get("associated_phenotype")),
            }
            for variant in variants
        ],
    }
    if hpo is not None:
        normalized["patient_phenotypes"] = [
            hpo.map(phenotype["text"])
            for phenotype in data.get("patient_phenotypes") or []
        ]
    return normalized


def _normalize_report(
    extraction: records.ReportExtraction,
    hgnc: genes_lib.HgncIndex,
    mondo: diseases.MondoIndex,
    hpo: phenotypes.HpoIndex | None,
) -> records.NormalizedReport:
    """Normalizes one ReportExtraction; a record without data passes through."""
    errors = [extraction.error] if extraction.error else []
    normalized = None
    if extraction.data is not None:
        try:
            normalized = _normalize(extraction.data, hgnc, mondo, hpo)
        except Exception as exc:  # One report's failure must not cost the others.
            errors.append(f"normalize: {type(exc).__name__}: {exc}")
    return records.NormalizedReport(
        extraction.file,
        extraction.pages,
        extraction.data,
        normalized,
        error="; ".join(errors) or None,
    )


def run(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    hgnc: genes_lib.HgncIndex,
    mondo: diseases.MondoIndex,
    hpo: phenotypes.HpoIndex | None,
) -> list[str]:
    """Normalizes every record of a run of `gentrex extract`, in input order.

    Args:
        input_path: JSONL file of ReportExtractions, from `gentrex extract`.
        output_path: JSONL file of NormalizedReports to write; an existing
            file is replaced.
        hgnc: Gene symbols to approved HGNC symbols.
        mondo: Disease names to MONDO diseases.
        hpo: Phenotypes to HPO terms, or None to leave them unmapped.

    Returns:
        Names of the files whose record has an error, from `gentrex extract`
        or from normalizing, in input order. Their records are still written.
    """
    start = time.perf_counter()
    with input_path.open(encoding="utf-8") as fh:
        extractions = [records.ReportExtraction(**json.loads(line)) for line in fh]
    failed: list[str] = []
    # Data from `gentrex extract` may hold half of a surrogate pair; it is kept as
    # a JSON escape.
    with output_path.open("w", encoding="utf-8", errors="backslashreplace") as fh:
        for extraction in extractions:
            report = _normalize_report(extraction, hgnc, mondo, hpo)
            _logger.info("normalized %s", report.file)
            fh.write(report.to_json() + "\n")
            if report.error:
                failed.append(report.file)
    _logger.info(
        "wrote %d reports (%d with an error) in %.0f s",
        len(extractions),
        len(failed),
        time.perf_counter() - start,
    )
    return failed
