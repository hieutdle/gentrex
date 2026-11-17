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
_NAME = re.compile(r"(N[MR]_\d+)\.\d+\(([^)]+)\):(c\.\S+)(?: \((p\.[^)]+)\))?")
# The parser wants a reference sequence before a change.
_REFERENCE = "NM_0"
_AMINO_ACIDS = {
    "Ala": "A",
    "Arg": "R",
    "Asn": "N",
    "Asp": "D",
    "Cys": "C",
    "Gln": "Q",
    "Glu": "E",
    "Gly": "G",
    "His": "H",
    "Ile": "I",
    "Leu": "L",
    "Lys": "K",
    "Met": "M",
    "Phe": "F",
    "Pro": "P",
    "Sec": "U",
    "Ser": "S",
    "Thr": "T",
    "Trp": "W",
    "Tyr": "Y",
    "Val": "V",
    "Ter": "*",
}
_THREE_LETTERS = re.compile("|".join(_AMINO_ACIDS))


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


def _protein_key(change: str) -> str:
    """Returns a p. change in one spelling, for comparing two of them.

    The reference sequence, the parentheses and the difference between the
    one-letter and the three-letter code are dropped, so p.(Arg412Trp)
    equals p.R412W. A frameshift keeps its first amino acid and position
    only, as ClinVar names it, so p.Gln1756Profs*74 equals p.Gln1756fs.
    """
    text = "".join(change.split()).rpartition(":")[2].removeprefix("p.")
    text = text.replace("(", "").replace(")", "")
    text = _THREE_LETTERS.sub(lambda match: _AMINO_ACIDS[match[0]], text)
    text = re.sub(r"^([A-Z*]\d+)[A-Z*]?fs.*", r"\1fs", text)
    # X is the older spelling of a stop codon.
    return re.sub(r"(?<=\d)X$", "*", text)


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
        self._variants: dict[tuple[str, str], set[tuple[str, str, str | None]]] = {}

    def read(self, genes: set[str]) -> None:
        """Reads the variants of the given genes, by their approved symbols."""
        variants = collections.defaultdict(set)
        with gzip.open(self._path, "rt", encoding="utf-8") as fh:
            next(fh)
            for line in fh:
                row = line.rstrip("\n").split("\t")
                name = _NAME.match(row[self._name])
                if name and name[2] in genes:
                    variants[name[2], _key(name[3])].add(
                        (name[1], row[self._id], name[4])
                    )
        self._variants = dict(variants)

    def normalize(
        self,
        gene: str | None,
        transcript: str | None,
        change: str | None,
        protein: str | None = None,
    ) -> dict[str, str | None]:
        """Returns the ClinVar variant with a gene's c. change, and how it matched.

        Args:
            gene: The gene's approved symbol.
            transcript: The variant's transcript, if the report gives one.
            change: The c. change as printed, with or without a transcript
                before it.
            protein: The p. change as printed, if the report gives one.

        Returns:
            `clinvar_variation_id`: ClinVar's VariationID, or None.
            `clinvar_status`: found, other_transcript (ClinVar names the
            change only on another transcript, where it can be another
            variant), ambiguous (several ClinVar variants have the change),
            unmapped or missing (no gene or no c. change).
            `clinvar_hgvs_p`: The p. change in ClinVar's name of the variant,
            or None.
            `clinvar_hgvs_p_status`: same, different or missing (the report
            or ClinVar gives no p. change, or the variant wasn't found).
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
        ids = {variation_id for _, variation_id, _ in matches}
        if len(ids) > 1:
            return _result(None, "ambiguous")
        named = sorted(named for _, _, named in matches if named)
        return _result(ids.pop(), "found", named[0] if named else None, protein)


def _result(
    variation_id: str | None,
    status: str,
    named: str | None = None,
    protein: str | None = None,
) -> dict[str, str | None]:
    """Returns the ClinVar values of a variant.

    Args:
        variation_id: ClinVar's VariationID.
        status: How the lookup went.
        named: The p. change in ClinVar's name of the variant.
        protein: The p. change that the report prints.
    """
    compared = "missing"
    if named and (protein or "").strip():
        same = _protein_key(named) == _protein_key(protein or "")
        compared = "same" if same else "different"
    return {
        "clinvar_variation_id": variation_id,
        "clinvar_status": status,
        "clinvar_hgvs_p": named,
        "clinvar_hgvs_p_status": compared,
    }
