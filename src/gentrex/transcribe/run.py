"""Orchestration: PDFs to a JSONL file of PageRecords."""

import collections
import dataclasses
import logging
import pathlib
import time
from concurrent import futures
from typing import TextIO

from gentrex import records
from gentrex import runs
from gentrex.transcribe import native
from gentrex.transcribe import ocr as ocr_lib

_logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _StartedPdf:
    """A PDF whose scanned pages have been sent to OCR.

    Attributes:
        name: PDF file name.
        pages: Every page of the PDF.
        ocr_calls: The pending OCR result of each scanned page, by page number.
        reused: How many scanned pages got their text from an earlier run.
    """

    name: str
    pages: list[records.PageRecord]
    ocr_calls: dict[int, futures.Future[str | Exception]]
    reused: int = 0

    def unfinished(self) -> int:
        """Returns how many OCR calls are still waiting or running."""
        return sum(not call.done() for call in self.ocr_calls.values())

    def finish(self) -> list[records.PageRecord]:
        """Waits for the OCR calls and returns the pages with their outcome."""
        for page in self.pages:
            if page.page in self.ocr_calls:
                result = self.ocr_calls[page.page].result()
                if isinstance(result, str):
                    page.text = result
                else:
                    page.error = f"{type(result).__name__}: {result}"
        return self.pages


def _earlier_texts(
    pages: list[records.PageRecord], earlier: list[records.PageRecord]
) -> dict[int, str]:
    """Returns the earlier OCR text of each scanned page that needs no new call.

    The earlier pages count only if the PDF still has the same pages, each
    scanned or native as before, and the same text on its native pages.
    Scanned pages with an error or without text are sent to OCR again.
    """

    def outline(found: list[records.PageRecord]) -> list[tuple[int, str, str]]:
        return [
            (page.page, page.source, page.text if page.source == "native" else "")
            for page in found
        ]

    if outline(earlier) != outline(pages):
        return {}
    return {
        page.page: page.text
        for page in earlier
        if page.source == "scanned" and page.text and not page.error
    }


def _start_pdf(
    pdf_path: pathlib.Path,
    native_min_chars: int,
    ocr: ocr_lib.OcrEngine | None,
    pool: futures.Executor,
    earlier: list[records.PageRecord],
) -> _StartedPdf:
    """Reads the PDF's pages and sends the scanned ones to OCR, if `ocr` is set.

    Scanned pages whose text an earlier run read, as `earlier` holds, keep
    that text and are not sent.
    """
    pages = native.classify_pages(pdf_path, native_min_chars)
    reused = _earlier_texts(pages, earlier)
    for page in pages:
        page.text = reused.get(page.page, page.text)
    scanned = [
        page.page
        for page in pages
        if page.source == "scanned" and page.page not in reused
    ]
    ocr_calls = {}
    if ocr is not None and scanned:
        ocr_calls = ocr_lib.submit_pages(pdf_path, scanned, ocr, pool)
    return _StartedPdf(pdf_path.name, pages, ocr_calls, len(reused))


def _write_oldest(
    started: collections.deque[_StartedPdf],
    fh: TextIO,
    failed: set[str],
    written: collections.Counter[str],
) -> None:
    """Writes the pages of the PDF started first, waiting for its OCR calls."""
    pdf = started.popleft()
    pages = pdf.finish()
    if any(page.error for page in pages):
        failed.add(pdf.name)
    written.update(page.source for page in pages)
    fh.write("".join(page.to_json() + "\n" for page in pages))
    fh.flush()


def run(
    pdf_paths: list[pathlib.Path],
    output: pathlib.Path,
    native_min_chars: int,
    ocr: ocr_lib.OcrEngine | None,
    earlier: runs.Earlier | None = None,
) -> list[str]:
    """Transcribes the PDFs into `output`.

    OCR requests from several PDFs are in flight at once, up to the OCR
    config's `concurrency`. Each PDF's pages are written together, in the
    order of `pdf_paths`.

    Args:
        pdf_paths: PDFs to transcribe.
        output: JSONL file to write; an existing file is replaced.
        native_min_chars: Routing threshold, see native.classify_source.
        ocr: OCR engine, or None to leave scanned pages empty.
        earlier: An earlier run whose OCR text is reused for scanned pages
            that it read without an error, for --retry.

    Returns:
        Names of the files that could not be read or had a page OCR failed
        on, in the order of `pdf_paths`. Pages of the latter are still
        written, with `error` set.
    """
    start = time.perf_counter()
    output.parent.mkdir(parents=True, exist_ok=True)
    workers = ocr.config.concurrency if ocr else 1
    failed: set[str] = set()
    written: collections.Counter[str] = collections.Counter()
    started: collections.deque[_StartedPdf] = collections.deque()
    earlier_pages: dict[str, list[records.PageRecord]] = collections.defaultdict(list)
    if earlier:
        for page in runs.read_earlier(
            earlier.run_dir / "pages.jsonl", records.PageRecord
        ):
            earlier_pages[page.file].append(page)
    reused = 0
    pool = futures.ThreadPoolExecutor(workers)
    try:
        with output.open("w", encoding="utf-8") as fh:
            for pdf_path in pdf_paths:
                _logger.info("processing %s", pdf_path.name)
                try:
                    pdf = _start_pdf(
                        pdf_path,
                        native_min_chars,
                        ocr,
                        pool,
                        earlier_pages.get(pdf_path.name, []),
                    )
                except Exception:  # One unreadable PDF must not stop the run.
                    _logger.exception("failed on %s", pdf_path.name)
                    failed.add(pdf_path.name)
                    continue
                started.append(pdf)
                reused += pdf.reused
                # Write PDFs that are complete. Then hold back the next PDF
                # while enough pages are out: `workers` in flight and as many
                # rendered ahead, so a free worker never waits for rendering.
                while started and (
                    not started[0].unfinished()
                    or sum(pdf.unfinished() for pdf in started) >= 2 * workers
                ):
                    _write_oldest(started, fh, failed, written)
            while started:
                _write_oldest(started, fh, failed, written)
    finally:
        # On an error or Ctrl-C, pages still waiting are not sent.
        pool.shutdown(cancel_futures=True)
    seconds = time.perf_counter() - start
    if earlier:
        _logger.info(
            "reused the text of %d scanned pages from %s", reused, earlier.run_dir
        )
    _logger.info(
        "wrote %d pages (%d scanned) in %.0f s: %.1f pages per minute",
        written.total(),
        written["scanned"],
        seconds,
        written.total() / seconds * 60,
    )
    return [path.name for path in pdf_paths if path.name in failed]
