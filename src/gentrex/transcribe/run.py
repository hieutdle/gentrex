"""Stage 1 orchestration: PDFs to a JSONL file of PageRecords."""

import logging
import pathlib

from gentrex import records
from gentrex.transcribe import native
from gentrex.transcribe import ocr as ocr_lib

_logger = logging.getLogger(__name__)


def transcribe_pdf(
    pdf_path: pathlib.Path,
    native_min_chars: int,
    ocr: ocr_lib.OcrEngine | None,
) -> list[records.PageRecord]:
    """Returns the PDF's pages; scanned pages stay empty when `ocr` is None."""
    pages = native.classify_pages(pdf_path, native_min_chars)
    scanned = [page for page in pages if page.source == "scanned"]
    if not scanned or ocr is None:
        return pages

    results = ocr_lib.ocr_pages(pdf_path, [page.page for page in scanned], ocr)
    for page in scanned:
        result = results[page.page]
        if isinstance(result, str):
            page.text = result
        else:
            page.error = f"{type(result).__name__}: {result}"
    return pages


def run(
    pdf_paths: list[pathlib.Path],
    output: pathlib.Path,
    native_min_chars: int,
    ocr: ocr_lib.OcrEngine | None,
) -> list[str]:
    """Transcribes the PDFs into `output`, one PDF at a time.

    Args:
        pdf_paths: PDFs to transcribe.
        output: JSONL file to write; an existing file is replaced.
        native_min_chars: Routing threshold, see native.classify_source.
        ocr: OCR engine, or None to leave scanned pages empty.

    Returns:
        Names of the files that could not be read or had a page OCR failed
        on. Pages of the latter are still written, with `error` set.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    failed: list[str] = []
    with output.open("w", encoding="utf-8") as fh:
        for pdf_path in pdf_paths:
            _logger.info("processing %s", pdf_path.name)
            try:
                pages = transcribe_pdf(pdf_path, native_min_chars, ocr)
            except ocr_lib.FATAL_ERRORS:
                raise
            except Exception:  # One unreadable PDF must not stop the run.
                _logger.exception("failed on %s", pdf_path.name)
                failed.append(pdf_path.name)
                continue
            if any(page.error for page in pages):
                failed.append(pdf_path.name)
            fh.write("".join(page.to_json() + "\n" for page in pages))
            fh.flush()
    return failed
