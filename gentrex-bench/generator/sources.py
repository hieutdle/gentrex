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
# A deletion or duplication of whole exons, whose ends ClinVar gives as ranges,
# as c.(?_5299)_(5572_?)del.
_EXON_CHANGE = re.compile(r"^c\.\(.*(?:del|dup)$")
# A copy-number change as ClinVar names it, with its copy number after the x,
# as GRCh38/hg38 17p11.2(chr17:16852187-20399047)x3.
_COPY_NUMBER = re.compile(r"^GRCh3[78]/hg(?:19|38) \S+\(chr\w+:\d+-\d+\)x(\d)$")
# A band or range of bands of one chromosome, as 17p11.2 or 4q22.1-22.2.
_BANDS = re.compile(r"[0-9X]+[pq][\d.]+(?:-[pq]?[\d.]+)?")
_CLASSES = {
    "Pathogenic": "pathogenic",
    "Likely pathogenic": "likely_pathogenic",
    "Uncertain significance": "uncertain_significance",
}
# Review statuses whose classification has assertion criteria and no conflict.
_REVIEWED = (
    "criteria provided, single submitter",
    "criteria provided, multiple submitters, no conflicts",
    "reviewed by expert panel",
    "practice guideline",
)
_INHERITANCE = {
    "HP:0000006": "autosomal_dominant",
    "HP:0000007": "autosomal_recessive",
    "HP:0001417": "x_linked",
    "HP:0001419": "x_linked_recessive",
    "HP:0001423": "x_linked_dominant",
    "HP:0001427": "mitochondrial",
}
# HPO's frequency terms, as the middle of the range each one stands for.
_FREQUENCIES = {
    "HP:0040280": 1.0,
    "HP:0040281": 0.9,
    "HP:0040282": 0.55,
    "HP:0040283": 0.17,
    "HP:0040284": 0.02,
}
_HPO_CLASS = re.compile(r"^http://purl\.obolibrary\.org/obo/HP_(\d+)$")
_MONDO_CLASS = re.compile(r"^http://purl\.obolibrary\.org/obo/MONDO_(\d+)$")


@dataclasses.dataclass(frozen=True)
class Disease:
    """A disease that HPO annotates, by its OMIM or Orphanet entry.

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
        transcript: The RefSeq transcript, or NC_012920.1 for mtDNA.
        hgvs_c: The c. change, or None for mtDNA.
        hgvs_p: The p. change in three-letter code, or None if ClinVar has none.
        hgvs_m: The m. change of an mtDNA variant.
        classification: pathogenic, likely_pathogenic or uncertain_significance.
        disease: The condition.
        chromosome: The chromosome on GRCh38, as 17 or MT.
        start: The first position on GRCh38.
        stop: The last position on GRCh38.
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
    chromosome: str = ""
    start: int = 0
    stop: int = 0


@dataclasses.dataclass(frozen=True)
class CopyNumberChange:
    """A ClinVar copy-number gain or loss of a region, as an array finds it.

    Attributes:
        variation_id: ClinVar's VariationID.
        chromosome: The chromosome, as 17 or X.
        cytoband: The band or bands, as 17p11.2 or 4q22.1-22.2.
        positions: The first and last position on each build, by GRCh37 and
            GRCh38.
        copy_number: The copies in the patient, from the x of ClinVar's name.
        classification: pathogenic, likely_pathogenic or uncertain_significance.
        genes: How many genes the region holds, as ClinVar counts them.
        disease: The condition, or None if ClinVar names none that MONDO and
            HPO both know.
    """

    variation_id: str
    chromosome: str
    cytoband: str
    positions: dict[str, tuple[int, int]]
    copy_number: int
    classification: str
    genes: int
    disease: Disease | None


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
        copy_number_changes: Usable ClinVar copy-number changes of regions.
        syndromes: The diseases of karyotypes, uniparental disomies, FMR1
            repeats and SMN1 copy numbers, by MONDO ID.
    """

    variants: dict[str, list[Variant]]
    terms: dict[str, Term]
    previous_symbols: dict[str, list[str]]
    copy_number_changes: list[CopyNumberChange] = dataclasses.field(
        default_factory=list
    )
    syndromes: dict[str, Disease] = dataclasses.field(default_factory=dict)


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
    """Returns the mode of inheritance and the features of each annotated disease.

    The diseases are keyed by their OMIM or Orphanet ID, as OMIM:611307 or
    ORPHA:145.

    Only diseases with exactly one mode of inheritance and at least two
    features are kept. Features that HPO marks with NOT, or that aren't current
    terms, are left out. The features come most frequent first, and features
    without a frequency count as occurring in half of the patients.
    """
    modes: dict[str, set[str]] = collections.defaultdict(set)
    features: dict[str, dict[str, float]] = collections.defaultdict(dict)
    with path.open(encoding="utf-8") as fh:
        rows = csv.DictReader(
            (line for line in fh if not line.startswith("#")), delimiter="\t"
        )
        for row in rows:
            disease = row["database_id"]
            if not disease.startswith(("OMIM:", "ORPHA:")):
                continue
            if row["qualifier"] == "NOT":
                continue
            if row["aspect"] == "I" and row["hpo_id"] in _INHERITANCE:
                modes[disease].add(_INHERITANCE[row["hpo_id"]])
            elif row["aspect"] == "P" and row["hpo_id"] in terms:
                features[disease].setdefault(
                    row["hpo_id"], _frequency(row["frequency"])
                )
    return {
        disease: (
            next(iter(found)),
            tuple(sorted(features[disease], key=lambda t: -features[disease][t])),
        )
        for disease, found in modes.items()
        if len(found) == 1 and len(features[disease]) >= 2
    }


def _frequency(value: str) -> float:
    """Returns an HPO frequency, written as a term, n/m or a percentage, as a share."""
    if value in _FREQUENCIES:
        return _FREQUENCIES[value]
    if match := re.fullmatch(r"(\d+)/(\d+)", value):
        return int(match[1]) / int(match[2]) if int(match[2]) else 0.5
    if match := re.fullmatch(r"([\d.]+)%", value):
        return float(match[1]) / 100
    return 0.5


def _diseases(
    phenotype_ids: str,
    mondo: dict[str, str],
    annotations: dict[str, tuple[str, tuple[str, ...]]],
) -> list[Disease]:
    """Returns the conditions of a ClinVar row that MONDO and HPO both know."""
    found = []
    # Conditions are separated by "|", and some of them by ";" within that.
    for condition in re.split(r"[|;]", phenotype_ids):
        ids = dict(part.split(":", 1) for part in condition.split(",") if ":" in part)
        mondo_id = ids.get("MONDO", "")
        keys = [f"OMIM:{ids.get('OMIM')}", f"ORPHA:{ids.get('Orphanet')}"]
        key = next((k for k in keys if k in annotations), None)
        if mondo_id in mondo and key:
            inheritance, phenotypes = annotations[key]
            found.append(Disease(mondo_id, mondo[mondo_id], inheritance, phenotypes))
    return found


def _gene_count(symbols: str) -> int:
    """Returns how many genes ClinVar's GeneSymbol of a region names.

    It reads "subset of 102 genes: PRRT2" and "covers 22 genes, none of
    which ..." by their number, and a list such as "ATOH1;GRID2" by its length.
    """
    if match := re.search(r"(\d+) genes", symbols):
        return int(match[1])
    return len([s for s in symbols.split(";") if s.strip() not in ("", "-")])


def _copy_number_changes(
    rows: dict[str, dict[str, dict[str, str]]],
    mondo: dict[str, str],
    annotations: dict[str, tuple[str, tuple[str, ...]]],
) -> list[CopyNumberChange]:
    """Returns the copy-number changes whose rows name them on both builds."""
    changes = []
    for variation_id, by_build in rows.items():
        if set(by_build) != {"GRCh37", "GRCh38"}:
            continue
        row = by_build["GRCh38"]
        # Both rows share the name, which gives the copy number. The
        # positions and the band come from each build's own columns.
        name = _COPY_NUMBER.match(row["Name"])
        band = row["Cytogenetic"]
        if not name or not _BANDS.fullmatch(band):
            continue
        positions = {b: (int(r["Start"]), int(r["Stop"])) for b, r in by_build.items()}
        diseases = _diseases(row["PhenotypeIDS"], mondo, annotations)
        changes.append(
            CopyNumberChange(
                variation_id=variation_id,
                chromosome=row["Chromosome"],
                cytoband=band,
                positions=positions,
                copy_number=int(name[1]),
                classification=_CLASSES[row["ClinicalSignificance"]],
                genes=_gene_count(row["GeneSymbol"]),
                disease=diseases[0] if diseases else None,
            )
        )
    return sorted(changes, key=lambda c: int(c.variation_id))


def load_clinvar(
    path: pathlib.Path,
    genes: set[str],
    mondo: dict[str, str],
    annotations: dict[str, tuple[str, tuple[str, ...]]],
) -> tuple[dict[str, list[Variant]], list[CopyNumberChange]]:
    """Returns the usable ClinVar variants of the given genes, and the usable
    copy-number changes of regions.

    A variant or change is usable when ClinVar's classification is
    pathogenic, likely pathogenic or of uncertain significance, with
    assertion criteria and no conflicts.

    A variant must also be on GRCh38, its name must have a RefSeq transcript
    and a c. change (or an m. change for mtDNA), and one of its conditions
    must have a MONDO ID and an OMIM or Orphanet entry with HPO features and
    one mode of inheritance. Of a variant's conditions, the one that ClinVar
    names most often for the gene is kept, and a variant whose condition less
    than a tenth of the gene's variants have is left out. A c. change of
    whole exons, whose ends are ranges such as c.(?_5299)_(5572_?)del, is
    kept, and other changes with unknown positions or repeats are left out.

    A copy-number change must be a germline gain or loss of 50 kb to 15 Mb
    on an autosome or X, named with its positions and copy number on both
    GRCh37 and GRCh38. Its condition is kept if MONDO and HPO know it.
    """
    csv.field_size_limit(sys.maxsize)
    found: list[tuple[list[Disease], Variant]] = []
    regions: dict[str, dict[str, dict[str, str]]] = collections.defaultdict(dict)
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            classification = _CLASSES.get(row["ClinicalSignificance"])
            if not classification or row["ReviewStatus"] not in _REVIEWED:
                continue
            if row["Type"] in ("copy number gain", "copy number loss"):
                start, stop = int(row["Start"]), int(row["Stop"])
                if (
                    row["Chromosome"] != "Y"
                    and 50_000 <= stop - start <= 15_000_000
                    and "somatic" not in row["Origin"]
                ):
                    regions[row["VariationID"]][row["Assembly"]] = row
                continue
            if row["GeneSymbol"] not in genes or row["Assembly"] != "GRCh38":
                continue
            coding, mito = _CODING.match(row["Name"]), _MITO.match(row["Name"])
            if not coding and not mito:
                continue
            if coding and ("[" in coding[3] or "?" in coding[3]):
                if not _EXON_CHANGE.match(coding[3]):
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
                        transcript=coding[1] if coding else "NC_012920.1",
                        hgvs_c=coding[3] if coding else None,
                        hgvs_p=coding[4] if coding else None,
                        hgvs_m=mito[2] if mito else None,
                        classification=classification,
                        disease=diseases[0],
                        chromosome=row["Chromosome"],
                        start=int(row["Start"]),
                        stop=int(row["Stop"]),
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
    # A condition of less than a tenth of a gene's variants is often outside
    # the clinical area that tests the gene, as multiple self-healing squamous
    # epithelioma is for TGFBR1, so those variants are left out.
    usual = {}
    for gene, found_variants in variants.items():
        shares = collections.Counter(v.disease.mondo_id for v in found_variants)
        usual[gene] = [
            v
            for v in found_variants
            if shares[v.disease.mondo_id] * 10 >= len(found_variants)
        ]
    return usual, _copy_number_changes(regions, mondo, annotations)


def load_syndromes(
    mondo_path: pathlib.Path,
    hpoa_path: pathlib.Path,
    terms: dict[str, Term],
    mondo_ids: set[str],
) -> dict[str, Disease]:
    """Returns diseases by MONDO ID, with the features HPO gives their entries.

    Unlike the diseases of ClinVar variants, these may have no mode of
    inheritance, as most chromosomal syndromes have none, and then their
    inheritance is "". A disease whose OMIM and Orphanet entries HPO doesn't
    annotate has no features.
    """
    graph = json.loads(mondo_path.read_text(encoding="utf-8"))["graphs"][0]
    labels: dict[str, str] = {}
    keys: dict[str, str] = {}
    for node in graph["nodes"]:
        match = _MONDO_CLASS.fullmatch(node["id"])
        if not match or f"MONDO:{match[1]}" not in mondo_ids:
            continue
        mondo_id = f"MONDO:{match[1]}"
        labels[mondo_id] = node["lbl"]
        for xref in node.get("meta", {}).get("xrefs", []):
            key = xref["val"].replace("Orphanet:", "ORPHA:")
            if key.startswith(("OMIM:", "ORPHA:")):
                keys[key] = mondo_id
    modes: dict[str, set[str]] = collections.defaultdict(set)
    features: dict[str, dict[str, float]] = collections.defaultdict(dict)
    with hpoa_path.open(encoding="utf-8") as fh:
        rows = csv.DictReader(
            (line for line in fh if not line.startswith("#")), delimiter="\t"
        )
        for row in rows:
            mondo_id = keys.get(row["database_id"])
            if mondo_id is None or row["qualifier"] == "NOT":
                continue
            if row["aspect"] == "I" and row["hpo_id"] in _INHERITANCE:
                modes[mondo_id].add(_INHERITANCE[row["hpo_id"]])
            elif row["aspect"] == "P" and row["hpo_id"] in terms:
                features[mondo_id].setdefault(
                    row["hpo_id"], _frequency(row["frequency"])
                )
    return {
        mondo_id: Disease(
            mondo_id,
            label,
            next(iter(modes[mondo_id])) if len(modes[mondo_id]) == 1 else "",
            tuple(sorted(features[mondo_id], key=lambda t: -features[mondo_id][t])),
        )
        for mondo_id, label in labels.items()
    }


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
