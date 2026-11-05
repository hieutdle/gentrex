"""Reference data the cases are sampled from: ClinVar, HPO, MONDO and HGNC."""

import collections
import csv
import dataclasses
import gzip
import json
import pathlib
import re
import sys

_CODING = re.compile(r"^(NM_\d+\.\d+)\(([^)]+)\):(c\.[^ ]+)(?: \((p\.[^)]+)\))?$")
_MITO = re.compile(r"^NC_012920\.1\((MT-[^)]+)\):(m\.[^ ]+)$")
_CLASSES = {
    "Pathogenic": "pathogenic",
    "Likely pathogenic": "likely_pathogenic",
    "Uncertain significance": "uncertain_significance",
}
_INHERITANCE = {
    "HP:0000006": "autosomal_dominant",
    "HP:0000007": "autosomal_recessive",
    "HP:0001417": "x_linked",
    "HP:0001419": "x_linked_recessive",
    "HP:0001423": "x_linked_dominant",
    "HP:0001427": "mitochondrial",
}
_HPO_CLASS = re.compile(r"^http://purl\.obolibrary\.org/obo/HP_(\d+)$")
_MONDO_CLASS = re.compile(r"^http://purl\.obolibrary\.org/obo/MONDO_(\d+)$")


@dataclasses.dataclass(frozen=True)
class Disease:
    """A disease with an OMIM entry that HPO annotates.

    Attributes:
        mondo_id: The MONDO ID that ClinVar gives the condition.
        label: The MONDO label.
        inheritance: The one mode of inheritance that HPO gives the disease.
        phenotypes: HPO IDs of the disease's features, in annotation order.
    """

    mondo_id: str
    label: str
    inheritance: str
    phenotypes: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class Variant:
    """A ClinVar variant with a classification and a usable condition.

    Attributes:
        variation_id: ClinVar's VariationID.
        gene: The approved HGNC symbol.
        hgnc_id: The HGNC ID.
        transcript: The RefSeq transcript, or None for mtDNA.
        hgvs_c: The c. change, or None for mtDNA.
        hgvs_p: The p. change in three-letter code, or None if ClinVar has none.
        hgvs_m: The m. change of an mtDNA variant.
        classification: pathogenic, likely_pathogenic or uncertain_significance.
        disease: The condition.
    """

    variation_id: str
    gene: str
    hgnc_id: str
    transcript: str | None
    hgvs_c: str | None
    hgvs_p: str | None
    hgvs_m: str | None
    classification: str
    disease: Disease


@dataclasses.dataclass(frozen=True)
class Term:
    """A current HPO term."""

    label: str
    synonyms: tuple[str, ...]


@dataclasses.dataclass
class References:
    """Everything the sampler reads.

    Attributes:
        variants: Usable ClinVar variants by gene.
        terms: Current HPO terms by ID.
        previous_symbols: Previous HGNC symbols by approved symbol, each of
            them the previous symbol of only this gene.
    """

    variants: dict[str, list[Variant]]
    terms: dict[str, Term]
    previous_symbols: dict[str, list[str]]


def load_terms(path: pathlib.Path) -> dict[str, Term]:
    """Returns the current HPO terms of an HPO release in obographs JSON."""
    graph = json.loads(path.read_text(encoding="utf-8"))["graphs"][0]
    terms = {}
    for node in graph["nodes"]:
        match = _HPO_CLASS.fullmatch(node["id"])
        meta = node.get("meta", {})
        if node.get("type") != "CLASS" or not match or not node.get("lbl"):
            continue
        if meta.get("deprecated"):
            continue
        synonyms = tuple(
            s["val"] for s in meta.get("synonyms", []) if s["pred"] == "hasExactSynonym"
        )
        terms[f"HP:{match[1]}"] = Term(node["lbl"], synonyms)
    return terms


def load_mondo_labels(path: pathlib.Path) -> dict[str, str]:
    """Returns the labels of the current MONDO diseases whose label is unique."""
    graph = json.loads(path.read_text(encoding="utf-8"))["graphs"][0]
    labels = {}
    for node in graph["nodes"]:
        match = _MONDO_CLASS.fullmatch(node["id"])
        if node.get("type") != "CLASS" or not match or not node.get("lbl"):
            continue
        if not node.get("meta", {}).get("deprecated"):
            labels[f"MONDO:{match[1]}"] = node["lbl"]
    counts = collections.Counter(label.casefold() for label in labels.values())
    return {k: v for k, v in labels.items() if counts[v.casefold()] == 1}


def load_annotations(
    path: pathlib.Path, terms: dict[str, Term]
) -> dict[str, tuple[str, tuple[str, ...]]]:
    """Returns the mode of inheritance and the features of each OMIM disease.

    Only diseases with exactly one mode of inheritance and at least three
    features are kept. Features that HPO marks with NOT, or that aren't current
    terms, are left out.
    """
    modes: dict[str, set[str]] = collections.defaultdict(set)
    features: dict[str, list[str]] = collections.defaultdict(list)
    with path.open(encoding="utf-8") as fh:
        rows = csv.DictReader(
            (line for line in fh if not line.startswith("#")), delimiter="\t"
        )
        for row in rows:
            disease = row["database_id"]
            if not disease.startswith("OMIM:") or row["qualifier"] == "NOT":
                continue
            if row["aspect"] == "I" and row["hpo_id"] in _INHERITANCE:
                modes[disease].add(_INHERITANCE[row["hpo_id"]])
            elif row["aspect"] == "P" and row["hpo_id"] in terms:
                if row["hpo_id"] not in features[disease]:
                    features[disease].append(row["hpo_id"])
    return {
        disease: (next(iter(found)), tuple(features[disease]))
        for disease, found in modes.items()
        if len(found) == 1 and len(features[disease]) >= 3
    }


def _diseases(
    phenotype_ids: str,
    mondo: dict[str, str],
    annotations: dict[str, tuple[str, tuple[str, ...]]],
) -> list[Disease]:
    """Returns the conditions of a ClinVar row that MONDO and HPO both know."""
    found = []
    for condition in phenotype_ids.split("|"):
        ids = dict(part.split(":", 1) for part in condition.split(",") if ":" in part)
        mondo_id = ids.get("MONDO", "")
        omim = f"OMIM:{ids['OMIM']}" if "OMIM" in ids else ""
        if mondo_id in mondo and omim in annotations:
            inheritance, phenotypes = annotations[omim]
            found.append(Disease(mondo_id, mondo[mondo_id], inheritance, phenotypes))
    return found


def load_variants(
    path: pathlib.Path,
    genes: set[str],
    mondo: dict[str, str],
    annotations: dict[str, tuple[str, tuple[str, ...]]],
) -> dict[str, list[Variant]]:
    """Returns the usable ClinVar variants of the given genes, by gene.

    A variant is usable when it is on GRCh38, ClinVar's classification is
    pathogenic, likely pathogenic or of uncertain significance with criteria
    and no conflicts, its name has a RefSeq transcript and a c. change (or an
    m. change for mtDNA), and one of its conditions has a MONDO ID and an
    OMIM entry with HPO features and one mode of inheritance. Of a variant's
    conditions, the one that ClinVar names most often for the gene is kept.
    """
    csv.field_size_limit(sys.maxsize)
    found: list[tuple[list[Disease], Variant]] = []
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["GeneSymbol"] not in genes or row["Assembly"] != "GRCh38":
                continue
            classification = _CLASSES.get(row["ClinicalSignificance"])
            review = row["ReviewStatus"]
            if not classification or "criteria provided" not in review:
                continue
            if "conflicting" in review:
                continue
            coding, mito = _CODING.match(row["Name"]), _MITO.match(row["Name"])
            if not coding and not mito:
                continue
            if coding and ("?" in coding[3] or "[" in coding[3]):
                continue
            diseases = _diseases(row["PhenotypeIDS"], mondo, annotations)
            if not diseases:
                continue
            found.append(
                (
                    diseases,
                    Variant(
                        variation_id=row["VariationID"],
                        gene=row["GeneSymbol"],
                        hgnc_id=row["HGNC_ID"],
                        transcript=coding[1] if coding else None,
                        hgvs_c=coding[3] if coding else None,
                        hgvs_p=coding[4] if coding else None,
                        hgvs_m=mito[2] if mito else None,
                        classification=classification,
                        disease=diseases[0],
                    ),
                )
            )
    counts: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    for diseases, variant in found:
        counts[variant.gene].update(d.mondo_id for d in diseases)
    variants: dict[str, list[Variant]] = collections.defaultdict(list)
    for diseases, variant in found:
        main = max(diseases, key=lambda d: counts[variant.gene][d.mondo_id])
        variants[variant.gene].append(dataclasses.replace(variant, disease=main))
    return dict(variants)


def load_previous_symbols(path: pathlib.Path) -> dict[str, list[str]]:
    """Returns the previous symbols of each approved HGNC symbol.

    A previous symbol that is also an approved symbol, or that several genes
    had, is left out, so that it names one gene only.
    """
    rows = list(csv.DictReader(path.open(encoding="utf-8"), delimiter="\t"))
    approved = {row["symbol"].upper() for row in rows}
    owners: dict[str, set[str]] = collections.defaultdict(set)
    for row in rows:
        for old in filter(None, (s.strip() for s in row["prev_symbol"].split("|"))):
            owners[old.upper()].add(row["symbol"])
    previous: dict[str, list[str]] = collections.defaultdict(list)
    for row in rows:
        for old in filter(None, (s.strip() for s in row["prev_symbol"].split("|"))):
            if old.upper() not in approved and len(owners[old.upper()]) == 1:
                previous[row["symbol"]].append(old)
    return dict(previous)
