"""Stage 6 orchestration: NormalizedReports to one Phenopacket per patient."""

import datetime
import json
import logging
import pathlib
import re
import time

from gentrex import records
from gentrex.export import phenopacket
from gentrex.load import run as load_run

_logger = logging.getLogger(__name__)


def _file_name(patient_key: str, taken: set[str]) -> str:
    """Returns a file name for the patient, such as mrn_SYN-MRN-0001.json."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", patient_key)
    name, number = f"{stem}.json", 2
    while name in taken:
        name, number = f"{stem}-{number}.json", number + 1
    taken.add(name)
    return name


def run(
    input_path: pathlib.Path,
    output_dir: pathlib.Path,
    versions: dict[str, str | None],
) -> list[str]:
    """Writes one Phenopacket per patient of a stage 4 run.

    The reports of one patient, those with the same patient_key as in stage 5,
    make one Phenopacket. A report without data has nothing to export.

    Args:
        input_path: JSONL file of NormalizedReports, from stage 4.
        output_dir: Folder to create for the Phenopackets, one JSON file per
            patient.
        versions: The HPO and MONDO releases that stage 4 used, under "hpo"
            and "mondo".

    Returns:
        Names of the files that have no data or have an error from stage 3 or
        4, in input order. Reports with an error and data are still exported.
    """
    start = time.perf_counter()
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
    output_dir.mkdir()
    created = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    taken: set[str] = set()
    for key, patient_reports in by_patient.items():
        packet = phenopacket.build(key, patient_reports, versions, created)
        name = _file_name(key, taken)
        (output_dir / name).write_text(
            json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _logger.info(
            "wrote %s from %s", name, ", ".join(r.file for r in patient_reports)
        )
    _logger.info(
        "wrote %d Phenopackets from %d of %d reports in %.0f s",
        len(by_patient),
        sum(len(patient_reports) for patient_reports in by_patient.values()),
        len(reports),
        time.perf_counter() - start,
    )
    return failed
