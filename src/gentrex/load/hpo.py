"""The HPO hierarchy: which terms each HPO term is a kind of."""

import collections
import dataclasses
import functools
import hashlib
import json
import pathlib

from gentrex.normalize import phenotypes


@dataclasses.dataclass(frozen=True)
class HpoTree:
    """The current terms of an HPO release, with their ancestors.

    Attributes:
        labels: The label of each term, by HPO ID.
        ancestors: The ancestors of each term, by HPO ID. They are the term
            itself and every term it is a kind of, through any number of is_a
            links.
        sha256: Checksum of the release file the terms were read from.
    """

    labels: dict[str, str]
    ancestors: dict[str, frozenset[str]]
    sha256: str

    @classmethod
    def from_release(cls, release: pathlib.Path) -> "HpoTree":
        """Reads the terms in the HPO index of `gentrex normalize`, and their links.

        Args:
            release: HPO release in obographs JSON, such as hp-base.json.
        """
        data = release.read_bytes()
        graph = json.loads(data)["graphs"][0]
        ids: dict[str, str] = {}
        labels: dict[str, str] = {}
        for hpo_id, node in phenotypes.current_terms(graph):
            ids[node["id"]] = hpo_id
            labels[hpo_id] = node["lbl"]
        parents: dict[str, set[str]] = collections.defaultdict(set)
        for edge in graph["edges"]:
            if edge["pred"] == "is_a" and edge["sub"] in ids and edge["obj"] in ids:
                parents[ids[edge["sub"]]].add(ids[edge["obj"]])

        @functools.cache
        def ancestors(term: str) -> frozenset[str]:
            return frozenset({term}).union(*map(ancestors, parents[term]))

        return cls(
            labels,
            {term: ancestors(term) for term in labels},
            hashlib.sha256(data).hexdigest(),
        )
