"""Disease names to MONDO diseases, by their labels and exact synonyms."""

import collections
import json
import pathlib
import re

from gentrex.normalize import phenotypes

_MONDO_CLASS = re.compile(r"http://purl\.obolibrary\.org/obo/MONDO_(\d+)")
# An abbreviation such as RTS stands for several diseases in practice, so a
# name is never matched to a disease by its abbreviation.
_ABBREVIATION = "http://purl.obolibrary.org/obo/mondo#ABBREVIATION"
_PARENTHESES = re.compile(r"\([^)]*\)")


def _key(name: str) -> str:
    """Returns `name` lowercased, with punctuation and spaces as single spaces."""
    return " ".join(re.sub(r"\W+", " ", name.casefold()).split())


class MondoIndex:
    """The labels and exact synonyms of the current MONDO diseases.

    Attributes:
        version: The MONDO release, such as 2026-11-03, or None if the release
            file doesn't name it.
    """

    def __init__(
        self,
        labels: dict[str, set[str]],
        synonyms: dict[str, set[str]],
        names: dict[str, str],
        version: str | None,
    ) -> None:
        self._labels = labels
        self._synonyms = synonyms
        self._names = names
        self.version = version

    @classmethod
    def from_release(cls, path: pathlib.Path) -> "MondoIndex":
        """Reads a MONDO release in obographs JSON, such as mondo-base.json.

        A current disease is a MONDO class that has a label and is not
        deprecated.
        """
        graph = json.loads(path.read_text(encoding="utf-8"))["graphs"][0]
        labels: dict[str, set[str]] = collections.defaultdict(set)
        synonyms: dict[str, set[str]] = collections.defaultdict(set)
        names: dict[str, str] = {}
        for node in graph["nodes"]:
            match = _MONDO_CLASS.fullmatch(node["id"])
            meta = node.get("meta", {})
            if node.get("type") != "CLASS" or not match or not node.get("lbl"):
                continue
            if meta.get("deprecated"):
                continue
            mondo_id = f"MONDO:{match[1]}"
            names[mondo_id] = node["lbl"]
            labels[_key(node["lbl"])].add(mondo_id)
            for synonym in meta.get("synonyms", []):
                if (
                    synonym["pred"] == "hasExactSynonym"
                    and synonym.get("synonymType") != _ABBREVIATION
                ):
                    synonyms[_key(synonym["val"])].add(mondo_id)
        version = phenotypes.release_version(graph)
        return cls(dict(labels), dict(synonyms), names, version)

    def normalize(self, name: str | None) -> dict[str, str | None]:
        """Returns the MONDO disease that `name` names, and how the name matched.

        A disease matches when `name` is its label or one of its exact
        synonyms, ignoring case and punctuation. The name is tried as printed,
        and then without any text in parentheses, such as "(HBOC)".
        `disease_status` is label, synonym, ambiguous (a name of several
        diseases), unmapped or missing. Only one disease per name is ever
        returned.
        """
        if not (name or "").strip():
            return _result(None, None, "missing")
        for attempt in dict.fromkeys([_key(name), _key(_PARENTHESES.sub(" ", name))]):
            for status, index in (("label", self._labels), ("synonym", self._synonyms)):
                matches = index.get(attempt, set())
                if len(matches) > 1:
                    return _result(None, None, "ambiguous")
                if matches:
                    mondo_id = next(iter(matches))
                    return _result(mondo_id, self._names[mondo_id], status)
        return _result(None, None, "unmapped")


def _result(
    mondo_id: str | None, label: str | None, status: str
) -> dict[str, str | None]:
    return {"disease_id": mondo_id, "disease_label": label, "disease_status": status}
