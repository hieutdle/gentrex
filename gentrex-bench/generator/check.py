"""Check each printed report against its case, and write its truth file.

A report passes when the PDF has the planned number of pages, each with the
synthetic footer, and every value of the truth and every distractor is in its
text. The truth file then gets the text of each page and the page of each
variant. Text matching follows gentrex transcribe, which reads the PDF's text
with pdfplumber.
"""

import copy
import dataclasses
import re
import unicodedata
from typing import Any

import pdfplumber

_ENUMS = {
    "test_type",
    "classification",
    "zygosity",
    "parental_origin",
    "mode_of_inheritance",
}


@dataclasses.dataclass
class Result:
    """The check of one report.

    Attributes:
        errors: Why the report doesn't match its case; empty if it passes.
        warnings: Values found only line by line, as in a wrapped table cell.
        truth: The truth file, or None if there are errors.
    """

    errors: list[str]
    warnings: list[str]
    truth: dict[str, Any] | None


def page_lines(text: str) -> str:
    """Returns page text prepared for matching.

    NFKC with single spaces and one line per text line. A line break after a
    hyphen or slash is dropped, since that is where Chrome wraps words such as
    "Whole-exome" or "and/or".
    """
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"(?<=\S[-/])\n", "", text)
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def _line_by_line(words: list[str], page: str) -> bool:
    """Whether the words run across the page's lines in order.

    pdfplumber reads a wrapped table cell line by line across the whole row,
    so a cell's later lines come after text from the neighbouring cells.
    """
    i = 0
    for line in page.split("\n"):
        for j in range(len(words), i, -1):
            if " ".join(words[i:j]) in line:
                i = j
                break
        if i == len(words):
            return True
    return False


def locate(value: str, pages: list[str]) -> tuple[list[int], list[int]]:
    """Returns the pages that hold the value whole, and those that hold it line by line.

    Pages are 1-based and prepared by page_lines. A whole value must not
    continue a word, so "Male" is not found in "Female".
    """
    needle = " ".join(unicodedata.normalize("NFKC", value).split())
    pattern = re.compile(rf"(?<!\w){re.escape(needle)}(?!\w)")
    whole = [n for n, p in enumerate(pages, 1) if pattern.search(p.replace("\n", " "))]
    if whole or " " not in needle:
        return whole, []
    words = needle.split(" ")
    return [], [n for n, p in enumerate(pages, 1) if _line_by_line(words, p)]


def _printed(record: dict[str, Any]) -> list[tuple[str, str]]:
    """Returns (path, value) of every value of the record that is printed as text."""
    values = [
        (f"/{k}", v)
        for k, v in record.items()
        if isinstance(v, str) and k not in _ENUMS
    ]
    for i, variant in enumerate(record["variants"]):
        values += [
            (f"/variants/{i}/{k}", v)
            for k, v in variant.items()
            if isinstance(v, str) and k not in _ENUMS
        ]
    for i, feature in enumerate(record["patient_phenotypes"]):
        values.append((f"/patient_phenotypes/{i}/text", feature["text"]))
    return values


def check(case: dict[str, Any], pdf_path, writer: dict[str, Any]) -> Result:
    """Checks a printed report against its case.

    Args:
        case: The case from sample.py.
        pdf_path: The native PDF.
        writer: The model, effort and prompt checksum that wrote the report.

    Returns:
        The errors, the warnings and, for a report without errors, its truth.
    """
    with pdfplumber.open(pdf_path) as pdf:
        raw = [(page.extract_text() or "").strip() for page in pdf.pages]
    pages = [page_lines(text) for text in raw]
    errors: list[str] = []
    warnings: list[str] = []
    planned = case["card"]["page_count"]
    if len(pages) != planned:
        errors.append(f"the PDF has {len(pages)} pages, the card asks for {planned}")
    for n, page in enumerate(pages, 1):
        if f"Page {n} of {len(pages)}" not in page or case["case_id"] not in page:
            errors.append(f"page {n} lacks the synthetic footer")

    def find(label: str, value: str) -> list[int]:
        whole, split = locate(value, pages)
        if split and not whole:
            warnings.append(f"{label} {value!r} is only line by line, on page {split}")
        if not whole and not split:
            errors.append(f"{label} {value!r} is not in the PDF text")
        return whole or split

    for path, value in _printed(case["record"]):
        find(path, value)
    for distractor in case["distractors"]:
        find(f"distractor {distractor['kind']}", distractor["text"])
    if case["unavailable"]:
        find("unavailable field", "Not provided")
    if errors:
        return Result(errors, warnings, None)

    record = copy.deepcopy(case["record"])
    for variant in record["variants"]:
        change = variant["hgvs_c"] or variant["dna_change_raw"]
        variant["page"] = min(find("variant", change))
    return Result(
        errors,
        warnings,
        {
            "case": {
                key: case[key]
                for key in (
                    "case_id",
                    "split",
                    "generator",
                    "lab",
                    "kind",
                    "scenario",
                    "tags",
                )
            }
            | {"writer": writer},
            "record": record,
            "normalized": case["normalized"],
            "pages": [{"page": n, "text": text} for n, text in enumerate(raw, 1)],
            "distractors": case["distractors"],
        },
    )
