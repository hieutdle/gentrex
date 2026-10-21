"""Gene symbols to approved HGNC symbols and IDs."""

import collections
import csv
import dataclasses
import hashlib
import pathlib

_COLUMNS = {"hgnc_id", "symbol", "alias_symbol", "prev_symbol"}


@dataclasses.dataclass(frozen=True)
class _Gene:
    hgnc_id: str
    symbol: str


class HgncIndex:
    """Approved, alias and previous symbols from the HGNC complete set.

    Attributes:
        sha256: Checksum of the file the index was read from.
    """

    def __init__(
        self,
        approved: dict[str, _Gene],
        aliases: dict[str, set[_Gene]],
        previous: dict[str, set[_Gene]],
        sha256: str,
    ) -> None:
        self._approved = approved
        self._aliases = aliases
        self._previous = previous
        self.sha256 = sha256

    @classmethod
    def from_tsv(cls, path: pathlib.Path) -> "HgncIndex":
        """Reads the tab-separated HGNC complete set.

        Raises:
            FileNotFoundError: There is no file at `path`.
            ValueError: The file lacks a column the index needs.
        """
        approved: dict[str, _Gene] = {}
        aliases: dict[str, set[_Gene]] = collections.defaultdict(set)
        previous: dict[str, set[_Gene]] = collections.defaultdict(set)
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            missing = _COLUMNS - set(reader.fieldnames or ())
            if missing:
                raise ValueError(f"{path} lacks columns: {', '.join(sorted(missing))}")
            for row in reader:
                gene = _Gene(row["hgnc_id"].strip(), row["symbol"].strip())
                approved[gene.symbol.upper()] = gene
                for alias in row["alias_symbol"].split("|"):
                    if alias.strip():
                        aliases[alias.strip().upper()].add(gene)
                for old in row["prev_symbol"].split("|"):
                    if old.strip():
                        previous[old.strip().upper()].add(gene)
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        return cls(approved, dict(aliases), dict(previous), sha256)

    def normalize(self, raw_symbol: str | None) -> dict[str, str | None]:
        """Returns the approved symbol and HGNC ID, and how the symbol matched.

        `gene_status` is approved, alias, previous, alias_or_previous,
        ambiguous (an alias or previous symbol of several genes), unmapped or
        missing. Only one gene per symbol is ever returned.
        """
        key = (raw_symbol or "").strip().upper()
        if not key:
            return _result(None, "missing")
        if key in self._approved:
            return _result(self._approved[key], "approved")
        matches = self._aliases.get(key, set()) | self._previous.get(key, set())
        if len(matches) != 1:
            return _result(None, "ambiguous" if matches else "unmapped")
        if key in self._aliases and key in self._previous:
            status = "alias_or_previous"
        else:
            status = "alias" if key in self._aliases else "previous"
        return _result(next(iter(matches)), status)


def _result(gene: _Gene | None, status: str) -> dict[str, str | None]:
    return {
        "gene_symbol": gene.symbol if gene else None,
        "hgnc_id": gene.hgnc_id if gene else None,
        "gene_status": status,
    }
