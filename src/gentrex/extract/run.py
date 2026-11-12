"""Orchestration: kept pages to a JSONL file of ReportExtractions."""

import itertools
import json
import logging
import pathlib
import time
from concurrent import futures

from gentrex import records
from gentrex import runs
from gentrex.extract import check
from gentrex.extract import extractor as extractor_lib

_logger = logging.getLogger(__name__)


def _extract(
    pages: list[records.PageRecord], extractor: extractor_lib.ReportExtractor
) -> records.ReportExtraction:
    """Extracts one report from its pages, in one request.

    Pages with an error from `gentrex transcribe` are left out and named in
    the record's error. A report without page text gets no request. The
    record names the copied values that aren't in the text of the pages sent.
    """
    sent = [page for page in pages if page.text]
    errors = [
        f"page {page.page}: transcribe: {page.error}" for page in pages if page.error
    ]
    data = not_in_pages = None
    if sent:
        result = extractor.extract_or_error(sent)
        if isinstance(result, Exception):
            errors.append(f"{type(result).__name__}: {result}")
        else:
            data = result
            not_in_pages = check.not_in_pages(
                data, extractor.config.schema, [page.text for page in sent]
            )
    return records.ReportExtraction(
        pages[0].file,
        [page.page for page in sent],
        data,
        error="; ".join(errors) or None,
        not_in_pages=not_in_pages,
    )


def _reports(pages: list[records.PageRecord]) -> list[list[records.PageRecord]]:
    """Returns the pages of each report, which the file holds together."""
    return [
        list(report)
        for _, report in itertools.groupby(pages, key=lambda page: page.file)
    ]


def _reusable(
    earlier: runs.Earlier, reports: list[list[records.PageRecord]]
) -> dict[str, records.ReportExtraction]:
    """Returns the earlier run's records to reuse, by file.

    A record is reused if it has no error and its report has the same pages
    as when the earlier run read it.
    """
    pages = runs.read_earlier(earlier.input_path / "pages.jsonl", records.PageRecord)
    before = {report[0].file: report for report in _reports(pages)}
    now = {report[0].file: report for report in reports}
    extractions = runs.read_earlier(
        earlier.run_dir / "extractions.jsonl", records.ReportExtraction
    )
    return {
        extraction.file: extraction
        for extraction in extractions
        if not extraction.error
        and extraction.file in now
        and before.get(extraction.file) == now[extraction.file]
    }


def run(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    extractor: extractor_lib.ReportExtractor,
    earlier: runs.Earlier | None = None,
) -> list[str]:
    """Extracts one record per report from a file of pages that `gentrex select` kept.

    Up to the config's `concurrency` reports are extracted at once. Records
    are written in input order; an existing file is replaced.

    Args:
        input_path: JSONL file of PageRecords, from `gentrex select`, with each
            report's pages together and in page order.
        output_path: JSONL file of ReportExtractions to write, one per report.
        extractor: Sends the requests.
        earlier: An earlier run whose good records are reused instead of
            extracted again, for --retry.

    Returns:
        Names of the files whose record has an error (a page left out or a
        failed request), in input order. Their records are still written.

    Raises:
        openai.OpenAIError: The endpoint is misconfigured (llm.FATAL_ERRORS).
    """
    start = time.perf_counter()
    with input_path.open(encoding="utf-8") as fh:
        pages = [records.PageRecord(**json.loads(line)) for line in fh]
    reports = _reports(pages)
    reuse = _reusable(earlier, reports) if earlier else {}
    if earlier:
        _logger.info(
            "reusing %d of %d reports from %s",
            len(reuse),
            len(reports),
            earlier.run_dir,
        )
    todo = [report for report in reports if report[0].file not in reuse]
    failed: list[str] = []
    flagged = 0
    pool = futures.ThreadPoolExecutor(extractor.config.concurrency)
    try:
        # An answer may hold half of a surrogate pair; it is kept as a JSON escape.
        with output_path.open("w", encoding="utf-8", errors="backslashreplace") as fh:
            extracted = pool.map(lambda report: _extract(report, extractor), todo)
            for report in reports:
                extraction = reuse.get(report[0].file)
                if extraction is None:
                    extraction = next(extracted)
                    _logger.info("extracted %s", extraction.file)
                fh.write(extraction.to_json() + "\n")
                if extraction.error:
                    failed.append(extraction.file)
                flagged += len(extraction.not_in_pages or [])
    finally:
        # On an error or Ctrl-C, reports still waiting are not sent.
        pool.shutdown(cancel_futures=True)
    seconds = time.perf_counter() - start
    _logger.info(
        "wrote %d reports (%d failed) in %.0f s: %.1f reports per minute",
        len(reports),
        len(failed),
        seconds,
        len(todo) / seconds * 60,
    )
    if flagged:
        _logger.info(
            "%d copied values are not in the text of their pages (not_in_pages)",
            flagged,
        )
    return failed
