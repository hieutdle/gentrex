"""Stage 1 orchestration: PDFs to a JSONL file of PageRecords."""

import collections
import dataclasses
import logging
import pathlib
import time
from concurrent import futures
from typing import TextIO

from gentrex import records
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
    """

    name: str
    pages: list[records.PageRecord]
    ocr_calls: dict[int, futures.Future[str | Exception]]

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


def _start_pdf(
    pdf_path: pathlib.Path,
    native_min_chars: int,
    ocr: ocr_lib.OcrEngine | None,
    pool: futures.Executor,
) -> _StartedPdf:
    """Reads the PDF's pages and sends the scanned ones to OCR, if `ocr` is set."""
    pages = native.classify_pages(pdf_path, native_min_chars)
    scanned = [page.page for page in pages if page.source == "scanned"]
    ocr_calls = {}
    if ocr is not None and scanned:
        ocr_calls = ocr_lib.submit_pages(pdf_path, scanned, ocr, pool)
    return _StartedPdf(pdf_path.name, pages, ocr_calls)


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
    pool = futures.ThreadPoolExecutor(workers)
    try:
        with output.open("w", encoding="utf-8") as fh:
            for pdf_path in pdf_paths:
                _logger.info("processing %s", pdf_path.name)
                try:
                    started.append(_start_pdf(pdf_path, native_min_chars, ocr, pool))
                except Exception:  # One unreadable PDF must not stop the run.
                    _logger.exception("failed on %s", pdf_path.name)
                    failed.add(pdf_path.name)
                    continue
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
    _logger.info(
        "wrote %d pages (%d scanned) in %.0f s: %.1f pages per minute",
        written.total(),
        written["scanned"],
        seconds,
        written.total() / seconds * 60,
    )
    return [path.name for path in pdf_paths if path.name in failed]
