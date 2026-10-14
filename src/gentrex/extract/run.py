"""Stage 3 orchestration: kept pages to a JSONL file of ReportExtractions."""

import itertools
import json
import logging
import pathlib
import time
from concurrent import futures

from gentrex import records
from gentrex.extract import extractor as extractor_lib

_logger = logging.getLogger(__name__)


def _extract(
    pages: list[records.PageRecord], extractor: extractor_lib.ReportExtractor
) -> records.ReportExtraction:
    """Extracts one report from its pages, in one request.

    Pages with a stage 1 error are left out and named in the record's error.
    A report without page text gets no request.
    """
    sent = [page for page in pages if page.text]
    errors = [
        f"page {page.page}: stage 1: {page.error}" for page in pages if page.error
    ]
    data = None
    if sent:
        result = extractor.extract_or_error(sent)
        if isinstance(result, Exception):
            errors.append(f"{type(result).__name__}: {result}")
        else:
            data = result
    return records.ReportExtraction(
        pages[0].file,
        [page.page for page in sent],
        data,
        error="; ".join(errors) or None,
    )


def run(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    extractor: extractor_lib.ReportExtractor,
) -> list[str]:
    """Extracts one record per report from a stage 2 file of kept pages.

    Up to the config's `concurrency` reports are extracted at once. Records
    are written in input order; an existing file is replaced.

    Args:
        input_path: JSONL file of PageRecords, from stage 2, with each
            report's pages together and in page order.
        output_path: JSONL file of ReportExtractions to write, one per report.
        extractor: Sends the requests.

    Returns:
        Names of the files whose record has an error (a page left out or a
        failed request), in input order. Their records are still written.

    Raises:
        openai.OpenAIError: The endpoint is misconfigured (llm.FATAL_ERRORS).
    """
    start = time.perf_counter()
    with input_path.open(encoding="utf-8") as fh:
        pages = [records.PageRecord(**json.loads(line)) for line in fh]
    reports = [
        list(report)
        for _, report in itertools.groupby(pages, key=lambda page: page.file)
    ]
    failed: list[str] = []
    pool = futures.ThreadPoolExecutor(extractor.config.concurrency)
    try:
        # An answer may hold half of a surrogate pair; it is kept as a JSON escape.
        with output_path.open("w", encoding="utf-8", errors="backslashreplace") as fh:
            extractions = pool.map(lambda report: _extract(report, extractor), reports)
            for extraction in extractions:
                _logger.info("extracted %s", extraction.file)
                fh.write(extraction.to_json() + "\n")
                if extraction.error:
                    failed.append(extraction.file)
    finally:
        # On an error or Ctrl-C, reports still waiting are not sent.
        pool.shutdown(cancel_futures=True)
    seconds = time.perf_counter() - start
    _logger.info(
        "wrote %d reports (%d failed) in %.0f s: %.1f reports per minute",
        len(reports),
        len(failed),
        seconds,
        len(reports) / seconds * 60,
    )
    return failed
