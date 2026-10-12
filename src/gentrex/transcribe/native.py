"""Embedded-text extraction and per-page routing with pdfplumber."""

import pathlib

import pdfplumber

from gentrex import records


def classify_source(text: str, native_min_chars: int) -> records.PageSource:
    """Routes a page by how much embedded text it has, ignoring whitespace."""
    char_count = len("".join(text.split()))
    return "native" if char_count >= native_min_chars else "scanned"


def classify_pages(
    pdf_path: pathlib.Path, native_min_chars: int
) -> list[records.PageRecord]:
    """Returns one record per page; scanned pages are left without text.

    Routing is per page because a report can mix native and scanned pages.
    """
    pages: list[records.PageRecord] = []
    with pdfplumber.open(pdf_path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            source = classify_source(text, native_min_chars)
            pages.append(
                records.PageRecord(
                    file=pdf_path.name,
                    page=number,
                    source=source,
                    text=text if source == "native" else "",
                )
            )
    return pages
