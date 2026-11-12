"""Embedded-text extraction and per-page routing with pdfplumber."""

import pathlib

import pdfplumber
from pdfplumber import page as page_lib

from gentrex import records

# A page with some text still goes to OCR when that text is only a sliver of
# the page. A page image may carry just a document code or a caption, and a PDF
# that draws its text as curves (outlines) may keep only a few fields, such as
# names and dates, as text.
_MIN_IMAGE_COVERAGE = 0.5
_MAX_IMAGE_PAGE_CHARS = 300
_MIN_CURVES = 1000
_MAX_CURVE_PAGE_CHARS = 600


def _image_coverage(page: page_lib.Page) -> float:
    """Returns the share of the page that its images cover, each clipped to it."""
    x0, top, x1, bottom = page.bbox
    covered = sum(
        max(min(image["x1"], x1) - max(image["x0"], x0), 0)
        * max(min(image["bottom"], bottom) - max(image["top"], top), 0)
        for image in page.images
    )
    return covered / (page.width * page.height)


def classify_source(
    text: str, native_min_chars: int, image_coverage: float, curves: int
) -> records.PageSource:
    """Routes a page by how much embedded text it has, ignoring whitespace.

    Args:
        text: The page's embedded text.
        native_min_chars: A page with fewer characters is scanned.
        image_coverage: The share of the page that images cover. Overlapping
            images can make it more than 1.
        curves: The number of curves on the page.

    Returns:
        "scanned" if the page has fewer than `native_min_chars` characters, or
        few characters on a page of images or curves; otherwise "native".
    """
    char_count = len("".join(text.split()))
    if char_count < native_min_chars:
        return "scanned"
    if image_coverage >= _MIN_IMAGE_COVERAGE and char_count < _MAX_IMAGE_PAGE_CHARS:
        return "scanned"
    if curves >= _MIN_CURVES and char_count < _MAX_CURVE_PAGE_CHARS:
        return "scanned"
    return "native"


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
            source = classify_source(
                text, native_min_chars, _image_coverage(page), len(page.curves)
            )
            pages.append(
                records.PageRecord(
                    file=pdf_path.name,
                    page=number,
                    source=source,
                    text=text if source == "native" else "",
                )
            )
    return pages
