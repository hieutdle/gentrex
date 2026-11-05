"""Orchestration: NormalizedReports to Phenopackets and FHIR Bundles."""

import datetime
import json
import logging
import pathlib
import re
import time
from typing import Any

from gentrex import records
from gentrex.export import fhir
from gentrex.export import phenopacket
from gentrex.export import pseudonyms as pseudonyms_lib
from gentrex.load import run as load_run

_logger = logging.getLogger(__name__)


def _file_name(stem: str, taken: set[str]) -> str:
    """Returns a file name made from `stem`, such as mrn_SYN-MRN-0001.json."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
    name, number = f"{stem}.json", 2
    while name in taken:
        name, number = f"{stem}-{number}.json", number + 1
    taken.add(name)
    return name


def _write(path: pathlib.Path, document: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _read(
    input_path: pathlib.Path,
) -> tuple[int, list[str], dict[str, list[records.NormalizedReport]]]:
    """Reads the reports of a run of `gentrex normalize`, by patient.

    The reports of one patient are those with the same patient_key as in
    `gentrex load`. A report without data has nothing to export.

    Returns:
        The number of reports, the names of the files that have no data or
        have an error, in input order, and the reports with data by patient
        key. Reports with an error and data are still exported.
    """
    with input_path.open(encoding="utf-8") as fh:
        reports = [load_run.read_report(line) for line in fh]
    failed: list[str] = []
    by_patient: dict[str, list[records.NormalizedReport]] = {}
    for report in reports:
        if report.data is None:
            _logger.warning(
                "skipped %s, which has no data: %s", report.file, report.error
            )
            failed.append(report.file)
            continue
        if report.error:
            failed.append(report.file)
        key = load_run.patient_key(report.file, report.data)
        by_patient.setdefault(key, []).append(report)
    return len(reports), failed, by_patient


def run(
    input_path: pathlib.Path,
    output_dir: pathlib.Path,
    versions: dict[str, str | None],
    pseudonyms: pseudonyms_lib.Pseudonyms | None = None,
) -> list[str]:
    """Writes one Phenopacket per patient of a run of `gentrex normalize`.

    Args:
        input_path: JSONL file of NormalizedReports, from `gentrex normalize`.
        output_dir: Folder to create for the Phenopackets, one JSON file per
            patient.
        versions: The HPO and MONDO releases that `gentrex normalize` used,
            under "hpo" and "mondo".
        pseudonyms: Pseudonyms that replace patient keys and file names, in
            the Phenopackets and their file names, for --pseudonymize.

    Returns:
        Names of the files that have no data or have an error from
        `gentrex extract` or `gentrex normalize`, in input order. Reports with
        an error and data are still exported.
    """
    start = time.perf_counter()
    count, failed, by_patient = _read(input_path)
    output_dir.mkdir()
    created = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    taken: set[str] = set()
    for key, patient_reports in by_patient.items():
        packet = phenopacket.build(key, patient_reports, versions, created, pseudonyms)
        name = _file_name(packet["id"], taken)
        _write(output_dir / name, packet)
        _logger.info(
            "wrote %s from %s", name, ", ".join(r.file for r in patient_reports)
        )
    _logger.info(
        "wrote %d Phenopackets from %d of %d reports in %.0f s",
        len(by_patient),
        sum(len(patient_reports) for patient_reports in by_patient.values()),
        count,
        time.perf_counter() - start,
    )
    return failed


def run_fhir(input_path: pathlib.Path, output_dir: pathlib.Path) -> list[str]:
    """Writes one FHIR Bundle per report of a run of `gentrex normalize`.

    Args:
        input_path: JSONL file of NormalizedReports, from `gentrex normalize`.
        output_dir: Folder to create for the Bundles, one JSON file per
            report, named after the PDF.

    Returns:
        Names of the files that have no data or have an error from
        `gentrex extract` or `gentrex normalize`, in input order. Reports with
        an error and data are still exported.
    """
    start = time.perf_counter()
    count, failed, by_patient = _read(input_path)
    output_dir.mkdir()
    taken: set[str] = set()
    written = 0
    for key, patient_reports in by_patient.items():
        patient = fhir.patient(key, patient_reports)
        for report in patient_reports:
            name = _file_name(pathlib.Path(report.file).stem, taken)
            _write(output_dir / name, fhir.bundle(report, patient))
            _logger.info("wrote %s from %s", name, report.file)
            written += 1
    _logger.info(
        "wrote %d of %d reports as Bundles in %.0f s",
        written,
        count,
        time.perf_counter() - start,
    )
    return failed
