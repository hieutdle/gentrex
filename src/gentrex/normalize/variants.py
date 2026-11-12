"""The HGVS syntax of a variant's changes, and the variant's ClinVar ID."""

import collections
import gzip
import hashlib
import pathlib
import re

import mutalyzer_hgvs_parser
from mutalyzer_hgvs_parser import exceptions

_COLUMNS = ("Name", "VariationID")
# The start of a ClinVar name, as NM_007294.4(BRCA1):c.5266dup (p.Gln1756fs).
_NAME = re.compile(r"(N[MR]_\d+)\.\d+\(([^)]+)\):(c\.\S+)")
# The parser wants a reference sequence before a change.
_REFERENCE = "NM_0"


def hgvs_status(change: str | None, kind: str) -> str:
    """Returns whether a printed change follows the HGVS syntax.

    The change may have a reference sequence before it, as in
    NM_007294.4:c.5266dupC. The syntax is that of the Mutalyzer HGVS parser,
    which also takes older spellings such as c.5266dupC and p.R412W.

    Args:
        change: The change as printed.
        kind: c for a coding DNA change, p for a protein change.

    Returns:
        valid, invalid or missing.
    """
    text = (change or "").strip()
    if not text:
        return "missing"
    try:
        description = mutalyzer_hgvs_parser.to_model(
            text if ":" in text else f"{_REFERENCE}:{text}"
        )
    except (
        exceptions.UnexpectedCharacter,
        exceptions.UnexpectedEnd,
        exceptions.NestedDescriptions,
    ):
        return "invalid"
    return "valid" if description.get("coordinate_system") == kind else "invalid"


def _key(change: str) -> str:
    """Returns a c. change as ClinVar names it, without case.

    The reference sequence before it and the bases after del or dup are
    dropped, so NM_007294.4:c.5266dupC equals c.5266dup.
    """
    text = "".join(change.split()).casefold().rpartition(":")[2]
    return re.sub(r"(del|dup)[acgt]+(?=$|ins)", r"\1", text)


def _accession(reference: str | None) -> str:
    """Returns a transcript without its version, as NM_007294 for NM_007294.4."""
    return (reference or "").strip().partition(".")[0].partition("(")[0].upper()


class ClinvarIndex:
    """The c. changes of ClinVar's variant_summary file, by gene.

    Attributes:
        sha256: Checksum of the file.
    """

    def __init__(self, path: pathlib.Path) -> None:
        """Checks the file's columns. read() then reads its variants.

        Raises:
            FileNotFoundError: There is no file at `path`.
            ValueError: The file isn't gzip-compressed or lacks a column.
        """
        self._path = path
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                header = fh.readline().rstrip("\n").lstrip("#").split("\t")
        except (gzip.BadGzipFile, UnicodeDecodeError) as exc:
            raise ValueError(f"{path} is not a gzip-compressed text file") from exc
        missing = set(_COLUMNS) - set(header)
        if missing:
            raise ValueError(f"{path} lacks columns: {', '.join(sorted(missing))}")
        self._name, self._id = (header.index(column) for column in _COLUMNS)
        with path.open("rb") as fh:
            self.sha256 = hashlib.file_digest(fh, "sha256").hexdigest()
        self._variants: dict[tuple[str, str], set[tuple[str, str]]] = {}

    def read(self, genes: set[str]) -> None:
        """Reads the variants of the given genes, by their approved symbols."""
        variants = collections.defaultdict(set)
        with gzip.open(self._path, "rt", encoding="utf-8") as fh:
            next(fh)
            for line in fh:
                row = line.rstrip("\n").split("\t")
                name = _NAME.match(row[self._name])
                if name and name[2] in genes:
                    variants[name[2], _key(name[3])].add((name[1], row[self._id]))
        self._variants = dict(variants)

    def normalize(
        self, gene: str | None, transcript: str | None, change: str | None
    ) -> dict[str, str | None]:
        """Returns the ClinVar variant with a gene's c. change, and how it matched.

        Args:
            gene: The gene's approved symbol.
            transcript: The variant's transcript, if the report gives one.
            change: The c. change as printed, with or without a transcript
                before it.

        Returns:
            `clinvar_variation_id`: ClinVar's VariationID, or None.
            `clinvar_status`: found, other_transcript (ClinVar names the
            change only on another transcript, where it can be another
            variant), ambiguous (several ClinVar variants have the change),
            unmapped or missing (no gene or no c. change).
        """
        change = (change or "").strip()
        if not gene or not change:
            return _result(None, "missing")
        matches = self._variants.get((gene, _key(change)), set())
        if not matches:
            return _result(None, "unmapped")
        accession = _accession(change.rpartition(":")[0] or transcript)
        if accession:
            matches = {match for match in matches if match[0] == accession}
            if not matches:
                return _result(None, "other_transcript")
        ids = {variation_id for _, variation_id in matches}
        if len(ids) > 1:
            return _result(None, "ambiguous")
        return _result(ids.pop(), "found")


def _result(variation_id: str | None, status: str) -> dict[str, str | None]:
    return {"clinvar_variation_id": variation_id, "clinvar_status": status}
