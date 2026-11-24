"""Check each printed report against its case, and write its truth file.

A report passes when every page has the synthetic footer, every value of
the truth and every distractor is in its text, the text names the genome build
of the truth and no other, and it names no c., g., m. or p. change, array result or
karyotype besides those of the truth and the distractors. The truth file then
gets the text of each page and the page of each variant. Text matching follows
gentrex transcribe, which reads the PDF's text with pdfplumber.
"""

import copy
import dataclasses
import re
import unicodedata
from typing import Any

import pdfplumber

# A change as printed: c.1521_1523del, c.(?_5299)_(5572_?)del, m.3243A>G,
# g.117559590_117559592del, p.Arg412Trp, p.(R412W) or p.?.
_CHANGE = re.compile(r"(?<![\w.])(?:[cgm]\.[-*(?_]*\d|p\.\(?[A-Z=?*])[^\s,;]*")
_CHANGE_FIELDS = ("hgvs_c", "hgvs_p", "dna_change_raw", "chromosomal_position")
# The start of an array result or a karyotype in ISCN, as arr[GRCh38] or 47,XX.
_ISCN = re.compile(r"arr\[|\b4[4-9],[XY]")
# The words that name each genome build.
_BUILDS = {"GRCh37": ("GRCh37", "hg19"), "GRCh38": ("GRCh38", "hg38")}
_ENUMS = {
    "genome_build",
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


def _parts(value: str) -> list[str]:
    """Splits a value where Chrome may wrap it: at spaces, and after a hyphen or
    slash inside a word. A part that ends a word keeps the space after it."""
    parts = []
    for word in value.split(" "):
        pieces = re.split(r"(?<=[/-])(?=[^/-])", word)
        parts += [*pieces[:-1], pieces[-1] + " "]
    return parts


def _line_by_line(parts: list[str], page: str) -> bool:
    """Whether the parts of a value run across the page's lines in order.

    pdfplumber reads a wrapped table cell line by line across the whole row,
    so a cell's later lines come after text from the neighbouring cells. A
    line can hold two parts with such text between them, because page_lines
    joins the line after a hyphen to it.
    """
    i = 0
    for line in page.split("\n"):
        start = 0
        while i < len(parts):
            for j in range(len(parts), i, -1):
                at = line.find("".join(parts[i:j]).strip(), start)
                if at >= 0:
                    start = at + len("".join(parts[i:j]).strip())
                    i = j
                    break
            else:
                break
        if i == len(parts):
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
    parts = _parts(needle)
    if whole or len(parts) < 2:
        return whole, []
    return [], [n for n, p in enumerate(pages, 1) if _line_by_line(parts, p)]


def _change(variant: dict[str, Any]) -> str:
    """Returns what the report prints for a variant: its change, else its gene.

    An SMN1 copy number has no change, so its gene stands for it.
    """
    return variant["hgvs_c"] or variant["dna_change_raw"] or variant["gene_symbol"]


def unexpected_changes(case: dict[str, Any], pages: list[str]) -> list[str]:
    """Returns the changes and ISCN results in the text that the case doesn't print.

    They come from the writing model, which may print a variant wrongly. A
    change is a c., g., m. or p. change, and an ISCN result an array result or
    a karyotype. The start of a known change passes only where Chrome wraps
    one: at the end of a line, after a hyphen or before a bracket.
    """
    record = case["record"]
    known = {v[f] for v in record["variants"] for f in _CHANGE_FIELDS if v[f]}
    known |= {d["text"] for d in case["distractors"]}
    found = set()
    for line in "\n".join(pages).split("\n"):
        for match in _CHANGE.finditer(line):
            change = match[0]
            while change[-1] in ".:" or (
                change[-1] == ")" and change.count(")") > change.count("(")
            ):
                change = change[:-1]
            wrapped = any(
                k.startswith(match[0])
                and (
                    match.end() == len(line)
                    or match[0][-1] == "-"
                    or k[len(match[0]) :].startswith("(")
                )
                for k in known
            )
            if not wrapped and not any(k.endswith(change) for k in known):
                found.add(change)
    notations = [v["dna_change_raw"] for v in record["variants"]]
    notations += [record["karyotype"], *(d["text"] for d in case["distractors"])]
    for page in pages:
        text = page.replace("\n", " ")
        covered = set()
        for notation in filter(None, notations):
            for match in re.finditer(re.escape(notation), text):
                covered.update(range(match.start(), match.end()))
        found |= {
            text[match.start() :].split(" ")[0].rstrip(".,;:")
            for match in _ISCN.finditer(text)
            if match.start() not in covered
        }
    return sorted(found)


def named_builds(pages: list[str]) -> set[str]:
    """Returns the genome builds that the text names, as GRCh37 for hg19."""
    return {
        build
        for build, words in _BUILDS.items()
        if any(re.search(rf"\b{word}\b", page) for word in words for page in pages)
    }


# The kinds of variant, in the order that tables list them.
VARIANT_KINDS = (
    "sequence",
    "exon_deletion_duplication",
    "mitochondrial",
    "copy_number",
    "gene_copy_number",
    "repeat",
    "uniparental_disomy",
)


def variant_kind(variant: dict[str, Any]) -> str:
    """Returns the kind of a variant of a record, from how the report gives it.

    A c. change of whole exons, whose ends are ranges, is a deletion or
    duplication of exons. A copy number without a DNA change is that of a
    gene, as SMN1's.
    """
    change = variant.get("hgvs_c") or ""
    other = (variant.get("dna_change_raw") or "").casefold()
    if change:
        return "exon_deletion_duplication" if change.startswith("c.(") else "sequence"
    if "m." in other:
        return "mitochondrial"
    if other.startswith("arr"):
        return "copy_number"
    if "repeat" in other:
        return "repeat"
    if "uniparental disomy" in other:
        return "uniparental_disomy"
    return "gene_copy_number"


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
    build = case["record"]["genome_build"]
    if named_builds(pages) != ({build} if build else set()):
        errors.append(f"the text names {sorted(named_builds(pages))}, not {build}")
    errors += [
        f"{change!r} is neither in the truth nor a distractor"
        for change in unexpected_changes(case, pages)
    ]
    if errors:
        return Result(errors, warnings, None)

    record = copy.deepcopy(case["record"])
    for variant in record["variants"]:
        variant["page"] = min(find("variant", _change(variant)))
    return Result(
        errors,
        warnings,
        {
            "case": {
                key: case[key]
                for key in (
                    "case_id",
                    "generator",
                    "lab",
                    "laboratory",
                    "kind",
                    "scenario",
                    "tags",
                    "challenges",
                )
            }
            | {
                "writer": writer,
                "variant_kinds": [variant_kind(v) for v in record["variants"]],
            },
            "record": record,
            "normalized": case["normalized"],
            "pages": [{"page": n, "text": text} for n, text in enumerate(raw, 1)],
            "distractors": case["distractors"],
        },
    )
