"""Sample the cases: the whole truth of each report, before any text is written.

Each case holds the record that a perfect `gentrex extract` writes, what a
perfect `gentrex normalize` adds, the distractors that the report prints but
that must not be extracted, and the card that tells the writing model what the
report is about. The same seed and references give the same cases.
"""

import collections
import dataclasses
import datetime
import random
import re
from typing import Any

import labs
import sources

from gentrex import config

_VERSION = "gentrex-synthetic-1"

# The share of each kind of test in percent. Each split gets these shares,
# rounded to whole cases, and _Sampler.plans spreads the cases of each kind
# over the templates that report it.
_KIND_WEIGHTS = {
    "panel": 20,
    "exome": 17,
    "single_gene": 9,
    "carrier": 16,
    "mito": 4,
    "targeted": 7,
    "array": 12,
    "karyotype": 5,
    "repeat": 5,
    "sma": 3,
    "methylation": 2,
}
# Kinds whose findings aren't ClinVar variants of a gene's sequence.
_SPECIAL_KINDS = ("array", "karyotype", "repeat", "sma", "methylation")
_PATHOGENIC = frozenset({"pathogenic", "likely_pathogenic"})
_SCENARIOS = {
    "panel": ["positive", "positive", "negative", "vus_only", "mixed"],
    "exome": [
        "positive",
        "positive",
        "negative",
        "vus_only",
        "mixed",
        "secondary_finding",
    ],
    "single_gene": ["positive", "negative", "vus_only"],
    "carrier": ["carrier", "carrier", "negative"],
    "mito": ["positive", "negative"],
    "targeted": ["positive", "negative"],
    "array": ["positive", "positive", "vus_only", "negative"],
    "karyotype": ["positive", "positive", "carrier", "negative"],
    "repeat": ["carrier", "positive", "negative"],
    "sma": ["carrier", "positive", "negative"],
    "methylation": ["positive", "positive", "negative"],
}
# Variant types as Sequence Ontology terms, for templates that print those.
_SO_TERMS = {
    "Missense": "missense_variant",
    "Nonsense": "stop_gained",
    "Frameshift": "frameshift_variant",
    "Synonymous": "synonymous_variant",
    "In-frame deletion": "inframe_deletion",
    "In-frame duplication": "inframe_insertion",
    "Deletion-insertion": "protein_altering_variant",
    "Splice site": "splice_site_variant",
    "Intronic": "intron_variant",
    "Exon deletion": "exon_loss_variant",
    "Exon duplication": "duplication",
}
_PEDIATRIC = (
    "Epilepsy",
    "Noonan Spectrum",
    "Neurodevelopmental",
    "Neuromuscular",
    "Hearing Loss",
)
_RESULT_CATEGORY = {
    "positive": "positive",
    "mixed": "positive",
    "negative": "negative",
    "secondary_finding": "negative",
    "vus_only": "uncertain",
    "carrier": "carrier",
    "upd": "positive",
    "indeterminate": "inconclusive",
}
_ORIGIN = {
    "de_novo": "De novo",
    "maternal": "Maternally inherited",
    "paternal": "Paternally inherited",
    "both_parents": "Inherited from both parents",
}
_RELATIVES = (
    "mother",
    "father",
    "maternal aunt",
    "paternal uncle",
    "older brother",
    "maternal grandmother",
    "paternal cousin",
)
_AMINO = {
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
    "Ser": "S",
    "Thr": "T",
    "Trp": "W",
    "Tyr": "Y",
    "Val": "V",
    "Ter": "*",
    "Sec": "U",
}

# Tags that the templates realize in the layout: cover pages before the
# report (late_page_evidence), a variant table split over two pages, and the
# features on a page of their own at the end.
LAYOUT_TAGS = (
    "table_split_across_pages",
    "late_page_evidence",
    "provided_phenotype_page",
)
# Tags that the writing model realizes in its text, with its instruction.
PROSE_TAGS = {
    "repeated_variant": "In the interpretation and the variant details, name "
    "each variant with its gene and its change, exactly as in the card.",
}
TAGS = (
    *LAYOUT_TAGS,
    *PROSE_TAGS,
    "gene_list_distractor",
    "boilerplate_variant_notation",
    "family_history_distractor",
    "similar_identifiers",
    "trio_columns",
    "multiple_variants",
    "negated_or_uncertain_phenotypes",
    "explicitly_unavailable",
    "missing_optional_fields",
    "multiple_patient_ids",
    "legacy_gene_symbol",
    "nonstandard_hgvs",
    "unusual_date_format",
    "ambiguous_specimen",
)


@dataclasses.dataclass(frozen=True)
class _Karyotype:
    """A karyotype that a chromosome analysis reports.

    Attributes:
        karyotype: The karyotype in ISCN.
        sex: The patient's sex.
        mondo_id: The syndrome it causes, or None.
        meaning: What it shows, in words for the writing model.
        indications: Reasons for testing.
        age: The patient's age range in years.
    """

    karyotype: str
    sex: str
    mondo_id: str | None
    meaning: str
    indications: tuple[str, ...]
    age: tuple[int, int]


_PREGNANCY_LOSS = ("Recurrent pregnancy loss", "Infertility")
_KARYOTYPES = {
    "negative": (
        _Karyotype(
            "46,XX",
            "Female",
            None,
            "a normal female karyotype",
            (*_PREGNANCY_LOSS, "Primary amenorrhea"),
            (24, 40),
        ),
        _Karyotype(
            "46,XY",
            "Male",
            None,
            "a normal male karyotype",
            (*_PREGNANCY_LOSS, "Developmental delay"),
            (24, 40),
        ),
    ),
    "positive": (
        _Karyotype(
            "47,XX,+21",
            "Female",
            "MONDO:0008608",
            "trisomy 21",
            ("Hypotonia and dysmorphic features", "Suspected trisomy"),
            (0, 1),
        ),
        _Karyotype(
            "47,XY,+21",
            "Male",
            "MONDO:0008608",
            "trisomy 21",
            ("Hypotonia and dysmorphic features", "Suspected trisomy"),
            (0, 1),
        ),
        _Karyotype(
            "47,XX,+18",
            "Female",
            "MONDO:0018071",
            "trisomy 18",
            ("Multiple congenital anomalies", "Suspected trisomy"),
            (0, 0),
        ),
        _Karyotype(
            "47,XY,+13",
            "Male",
            "MONDO:0018068",
            "trisomy 13",
            ("Multiple congenital anomalies", "Suspected trisomy"),
            (0, 0),
        ),
        _Karyotype(
            "45,X",
            "Female",
            "MONDO:0019499",
            "monosomy X",
            ("Short stature", "Primary amenorrhea"),
            (9, 16),
        ),
        _Karyotype(
            "45,X[14]/46,XX[6]",
            "Female",
            "MONDO:0019499",
            "mosaic monosomy X, in 14 of 20 cells",
            ("Short stature", "Primary amenorrhea"),
            (9, 16),
        ),
        _Karyotype(
            "47,XXY",
            "Male",
            "MONDO:0006823",
            "an extra X chromosome",
            ("Infertility", "Hypogonadism"),
            (18, 35),
        ),
        _Karyotype(
            "47,XXX",
            "Female",
            "MONDO:0018066",
            "an extra X chromosome",
            ("Developmental delay", "Learning difficulties"),
            (4, 12),
        ),
        _Karyotype(
            "47,XYY",
            "Male",
            "MONDO:0019339",
            "an extra Y chromosome",
            ("Developmental delay", "Tall stature"),
            (4, 12),
        ),
    ),
    "carrier": (
        _Karyotype(
            "45,XX,der(13;14)(q10;q10)",
            "Female",
            None,
            "a balanced Robertsonian translocation of chromosomes 13 and 14",
            _PREGNANCY_LOSS,
            (24, 40),
        ),
        _Karyotype(
            "45,XY,der(13;14)(q10;q10)",
            "Male",
            None,
            "a balanced Robertsonian translocation of chromosomes 13 and 14",
            _PREGNANCY_LOSS,
            (24, 40),
        ),
        _Karyotype(
            "46,XX,t(11;22)(q23;q11.2)",
            "Female",
            None,
            "a balanced reciprocal translocation of chromosomes 11 and 22",
            _PREGNANCY_LOSS,
            (24, 40),
        ),
        _Karyotype(
            "46,XY,t(11;22)(q23;q11.2)",
            "Male",
            None,
            "a balanced reciprocal translocation of chromosomes 11 and 22",
            _PREGNANCY_LOSS,
            (24, 40),
        ),
    ),
}


@dataclasses.dataclass(frozen=True)
class _Disomy:
    """A whole-chromosome uniparental disomy that causes a syndrome.

    Attributes:
        chromosome: The chromosome.
        bands: Its bands from end to end, as ISCN names them.
        length: Its length on GRCh38.
        parent: maternal or paternal.
        mondo_id: The syndrome.
        indications: Reasons for testing.
        age: The patient's age range in years.
    """

    chromosome: str
    bands: str
    length: int
    parent: str
    mondo_id: str
    indications: tuple[str, ...]
    age: tuple[int, int]


_DISOMIES = (
    _Disomy(
        "7",
        "7p22.3q36.3",
        159345973,
        "maternal",
        "MONDO:0008394",
        ("Failure to thrive, short stature", "Growth restriction"),
        (1, 8),
    ),
    _Disomy(
        "15",
        "15q11.2q26.3",
        101991189,
        "maternal",
        "MONDO:0008300",
        ("Hypotonia and feeding difficulties", "Hypotonia"),
        (0, 5),
    ),
    _Disomy(
        "15",
        "15q11.2q26.3",
        101991189,
        "paternal",
        "MONDO:0007113",
        ("Seizures and developmental delay", "Absent speech"),
        (1, 6),
    ),
    _Disomy(
        "6",
        "6p25.3q27",
        170805979,
        "paternal",
        "MONDO:0011073",
        ("Neonatal diabetes", "Neonatal hyperglycemia"),
        (0, 0),
    ),
)
# Gene, HGNC ID, transcript and condition of the repeat and SMA tests.
_FMR1 = ("FMR1", "HGNC:3775", "NM_002024.6", "MONDO:0010383")
_SMN1 = ("SMN1", "HGNC:11117", "NM_000344.4", "MONDO:0001516")
# Spinal muscular atrophy type 1, whose features an affected infant has.
_SMA_TYPE_1 = "MONDO:0009669"


@dataclasses.dataclass(frozen=True)
class _Expansion:
    """A dominant repeat expansion that a test of one repeat finds.

    Attributes:
        gene: The gene.
        hgnc_id: Its HGNC ID.
        transcript: The transcript the report names.
        mondo_id: The condition.
        unit: The repeated sequence, as CAG.
        normal: The range of normal repeat sizes.
        expanded: The range of expanded sizes, or None if the test doesn't
            size an expanded allele.
        printed: The classification of an expanded allele, as printed.
        test: The name of the test.
        indications: Reasons for testing.
        age: The patient's age range in years.
    """

    gene: str
    hgnc_id: str
    transcript: str
    mondo_id: str
    unit: str
    normal: tuple[int, int]
    expanded: tuple[int, int] | None
    printed: str
    test: str
    indications: tuple[str, ...]
    age: tuple[int, int]


_EXPANSIONS = {
    "HTT": _Expansion(
        "HTT",
        "HGNC:4851",
        "NM_002111.8",
        "MONDO:0007739",
        "CAG",
        (15, 26),
        (40, 55),
        "Full Penetrance Allele",
        "Huntington Disease: HTT CAG Repeat Analysis",
        ("Family history of Huntington disease", "Chorea and cognitive decline"),
        (25, 55),
    ),
    "C9orf72": _Expansion(
        "C9orf72",
        "HGNC:28337",
        "NM_018325.3",
        "MONDO:0007105",
        "GGGGCC",
        (2, 10),
        None,
        "Expanded Allele",
        "C9orf72 Hexanucleotide Repeat Expansion Analysis",
        ("Amyotrophic lateral sclerosis", "Frontotemporal dementia"),
        (40, 70),
    ),
}
# Syndromes that methylation-specific MLPA of 15q11.2q13 finds, with the
# parent whose methylation pattern is the only one left.
_METHYLATION = (
    (
        "Prader-Willi Syndrome",
        "MONDO:0008300",
        "maternal",
        ("Hypotonia and feeding difficulties", "Obesity and developmental delay"),
    ),
    (
        "Angelman Syndrome",
        "MONDO:0007113",
        "paternal",
        ("Seizures and developmental delay", "Absent speech and ataxia"),
    ),
)
# The diseases that sources.load_syndromes loads.
SYNDROMES = (
    {k.mondo_id for ks in _KARYOTYPES.values() for k in ks if k.mondo_id}
    | {d.mondo_id for d in _DISOMIES}
    | {_FMR1[3], _SMN1[3], _SMA_TYPE_1}
    | {e.mondo_id for e in _EXPANSIONS.values()}
    | {mondo_id for _, mondo_id, _, _ in _METHYLATION}
)
# Features of children sent for a microarray, for a copy-number change
# without a condition that HPO annotates.
_ARRAY_FEATURES = (
    "HP:0001263",
    "HP:0000717",
    "HP:0001249",
    "HP:0001250",
    "HP:0001252",
    "HP:0004322",
    "HP:0000252",
    "HP:0001627",
)
_ARRAY_INDICATIONS = (
    "Developmental delay",
    "Autism spectrum disorder",
    "Multiple congenital anomalies",
    "Intellectual disability",
    "Developmental delay and seizures",
)
# Genes whose X-linked condition affects heterozygous females and spares
# hemizygous males.
_FEMALE_LIMITED = {"PCDH19"}
# Words of features that only the other sex can have, by the patient's sex.
_OTHER_SEX_WORDS = {
    "Female": (
        "cryptorchi",
        "testi",
        "testes",
        "scrot",
        "penis",
        "penile",
        "hypospadias",
    ),
    "Male": ("amenorrhea", "ovar", "uter", "vagin", "menstru", "breast"),
}


@dataclasses.dataclass
class _Plan:
    """The choices that the tags depend on."""

    lab: labs.Lab
    kind: str
    scenario: str
    area: labs.Area | None


@dataclasses.dataclass
class _Found:
    """The findings of a case, and what they decide about the rest of it.

    Attributes:
        tags: The challenge tags.
        items: The record's variants.
        normalized: What `gentrex normalize` adds to each variant.
        sex: The patient's sex.
        age: The patient's age in years.
        disease: The condition that the test is about, or None.
        phenotypes: HPO IDs that the patient's features come from.
        test_name: The name of the test.
        test_type: The record's test_type.
        indication: The reason for testing.
        karyotype: The karyotype, or None.
        genome_build: The build that the report names, or None.
        focus: The gene, transcript and condition that a test of one gene
            names, also when the result is negative.
        distractors: Distractors that come with the findings.
        card: The variants as the writing model gets them.
        fields: Names that the headline result may use.
        details: What the template prints besides the truth.
        genes: The genes of the panel.
        transcripts: The transcript of each gene that a gene list prints.
        meaning: What the result means, for the writing model, if the kind
            and scenario don't tell it.
    """

    tags: set[str]
    items: list[dict[str, Any]]
    normalized: list[dict[str, Any]]
    sex: str
    age: int
    disease: sources.Disease | None
    phenotypes: tuple[str, ...]
    test_name: str
    test_type: str
    indication: str
    karyotype: str | None = None
    genome_build: str | None = None
    focus: dict[str, str] | None = None
    distractors: list[dict[str, str]] = dataclasses.field(default_factory=list)
    card: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    fields: dict[str, str] = dataclasses.field(default_factory=dict)
    details: dict[str, Any] = dataclasses.field(default_factory=dict)
    genes: list[str] = dataclasses.field(default_factory=list)
    transcripts: dict[str, str | None] = dataclasses.field(default_factory=dict)
    meaning: str | None = None


def _one_letter(protein: str) -> str:
    """Returns a three-letter protein change in one-letter code, as p.R412W."""
    for three, one in _AMINO.items():
        protein = protein.replace(three, one)
    return protein.replace("(", "").replace(")", "")


def _protein(protein: str | None, style: str, nonstandard: bool) -> str | None:
    """Returns a protein change as a template prints it.

    The nonstandard_hgvs tag prints the one-letter code, in parentheses if the
    template already uses the one-letter code.
    """
    if not protein:
        return protein
    if style == "one_letter" and nonstandard:
        return f"p.({_one_letter(protein)[2:]})"
    if style == "one_letter" or nonstandard:
        return _one_letter(protein)
    if style == "parentheses":
        return f"p.({protein[2:]})"
    return protein


def _short_change(variant: sources.Variant) -> str:
    """Returns how a test name refers to a variant, as R534Q or c.1601G>A."""
    if variant.hgvs_p:
        return _one_letter(variant.hgvs_p)[2:]
    return variant.hgvs_c or variant.hgvs_m or ""


def _fields(variants: list[dict[str, Any]]) -> dict[str, str]:
    """Returns the names a headline result can use, from its first primary variant."""
    primary = [v for v in variants if not v["is_secondary_finding"]]
    if not primary:
        return {}
    v = primary[0]
    change = v["hgvs_c"] or v["dna_change_raw"] or ""
    return {
        "gene": v["gene_symbol"] or "",
        "hgvs": f"{change}, {v['hgvs_p']}" if v["hgvs_p"] else change,
        "zygosity": v["zygosity"] or "",
        "Zygosity": (v["zygosity"] or "").capitalize(),
        "classification": labs.SENTENCE_CLASSES.get(v["classification"], ""),
        "printed_class": v["classification_raw"] or "",
    }


def _scenarios(lab: labs.Lab, kind: str) -> list[str]:
    """Returns the scenarios of a kind of test that a template reports.

    A scenario that appears twice is drawn twice as often.
    """
    scenarios = _SCENARIOS[kind]
    if kind == "exome" and lab.disomy:
        scenarios = [*scenarios, "upd", "upd", "upd"]
    if kind in ("panel", "single_gene") and lab.indeterminate:
        scenarios = [*scenarios, "indeterminate"]
    if kind == "repeat" and "FMR1" not in lab.repeat_genes:
        scenarios = ["positive", "positive", "negative"]
    return scenarios


def _iscn_band(band: str) -> str:
    """Returns ClinVar's band or range of bands as ISCN writes it.

    ClinVar's 4q22.1-22.2 is 4q22.1q22.2 in ISCN, and 21p11.2-q22.3 is
    21p11.2q22.3.
    """
    match = re.fullmatch(r"(\d+|X)([pq])([\d.]+)(?:-([pq]?)([\d.]+))?", band)
    if not match or not match[5]:
        return band
    chromosome, arm, first, second_arm, second = match.groups()
    return f"{chromosome}{arm}{first}{second_arm or arm}{second}"


def _size(length: int) -> str:
    """Returns a length in bases as a report prints it, as 536 kb or 3.54 Mb."""
    if length >= 1_000_000:
        return f"{length / 1_000_000:.2f} Mb"
    return f"{round(length / 1000)} kb"


def _variant_word(variant: sources.Variant) -> str | None:
    """Returns the kind of a variant from its HGVS, as a lab would name it."""
    c, p = variant.hgvs_c or "", variant.hgvs_p or ""
    if variant.hgvs_m:
        return None
    if p.endswith("fs"):
        return "Frameshift"
    if p.endswith("Ter") or p.endswith("*"):
        return "Nonsense"
    if p.endswith("="):
        return "Synonymous"
    if "delins" in c:
        return "Deletion-insertion"
    if "del" in c and p:
        return "In-frame deletion"
    if "dup" in c and p:
        return "In-frame duplication"
    if not p and ("+1" in c or "+2" in c or "-1" in c or "-2" in c):
        return "Splice site"
    if c.startswith("c.("):
        return "Exon deletion" if c.endswith("del") else "Exon duplication"
    if not p:
        return "Intronic"
    return "Missense"


def _variant_type(variant: sources.Variant, style: str | None) -> str | None:
    """Returns the kind of a variant in words or as a Sequence Ontology term."""
    if style is None:
        return None
    word = _variant_word(variant)
    return _SO_TERMS.get(word, word) if style == "so" and word else word


def _x_linked_sex(variant: sources.Variant) -> str | None:
    """Returns the sex of a patient affected by an X-linked variant, or None.

    X-linked recessive conditions affect hemizygous males. X-linked dominant
    conditions, such as Rett syndrome, mostly affect heterozygous females, and
    a few X-linked conditions spare males altogether.
    """
    mode = variant.disease.inheritance
    if not mode.startswith("x_linked"):
        return None
    if mode == "x_linked_dominant" or variant.gene in _FEMALE_LIMITED:
        return "Female"
    return "Male"


def _zygosity(inheritance: str, sex: str, diagnostic: bool) -> str:
    if inheritance == "mitochondrial":
        return "heteroplasmic"
    if inheritance.startswith("x_linked") and sex == "Male":
        return "hemizygous"
    if inheritance == "autosomal_recessive" and diagnostic:
        return "homozygous"
    return "heterozygous"


class _Sampler:
    """Samples one case after another from one random stream."""

    def __init__(self, refs: sources.References, seed: str) -> None:
        self._refs = refs
        self._rng = random.Random(seed)
        self._tag_counts: collections.Counter[str] = collections.Counter()
        schema = config.load_schema()["properties"]
        self._fields = list(schema)
        self._variant_fields = list(schema["variants"]["items"]["properties"])
        self._array_features = tuple(t for t in _ARRAY_FEATURES if t in refs.terms)

    def start_split(self) -> None:
        """Starts the counts of tags anew, for the next split."""
        self._tag_counts.clear()

    def plans(self, split: str, count: int) -> list[tuple[str, labs.Lab]]:
        """Returns the kind of test and the template of `count` cases.

        The kinds have the shares of _KIND_WEIGHTS, rounded to whole cases by
        the largest remainder. Each case goes to the template of its kind that
        has the fewest cases so far. The kinds that the fewest templates
        report come first, so that a template that reports several kinds
        fills up last. Cases then move from fuller to emptier templates,
        each to a template of its kind, until the counts are as even as they
        can be. The cases come in random order.
        """
        rng = self._rng
        total = sum(_KIND_WEIGHTS.values())
        exact = {kind: count * weight / total for kind, weight in _KIND_WEIGHTS.items()}
        quotas = {kind: int(share) for kind, share in exact.items()}
        by_remainder = sorted(exact, key=lambda kind: quotas[kind] - exact[kind])
        for kind in by_remainder[: count - sum(quotas.values())]:
            quotas[kind] += 1
        eligible = {
            kind: [
                lab
                for lab in labs.LABS
                if kind in lab.kinds and (split == "test" or not lab.held_out)
            ]
            for kind in quotas
        }
        load: collections.Counter[str] = collections.Counter()
        cases: collections.Counter[tuple[str, str]] = collections.Counter()
        for kind in sorted(quotas, key=lambda k: (len(eligible[k]), quotas[k])):
            for _ in range(quotas[kind]):
                lab = min(eligible[kind], key=lambda lab: (load[lab.key], rng.random()))
                load[lab.key] += 1
                cases[kind, lab.key] += 1

        def chain(start: str, goal: str) -> list[tuple[str, str, str]]:
            """Returns moves of one case each, as (kind, from, to), that lead
            from one template to another, or no moves if none do."""
            came: dict[str, tuple[str, str] | None] = {start: None}
            queue = collections.deque([start])
            while queue and goal not in came:
                a = queue.popleft()
                for kind in quotas:
                    for b in eligible[kind] if cases[kind, a] else []:
                        if b.key not in came:
                            came[b.key] = (kind, a)
                            queue.append(b.key)
            moves = []
            while step := came.get(goal):
                moves.append((step[0], step[1], goal))
                goal = step[1]
            return moves

        # Pass cases from fuller to emptier templates until the counts are
        # as even as they can be. A case moves to a template of its kind, so
        # it may take a chain of moves through templates in between: chart
        # gets a targeted case from lis-printout, which gets a single-gene
        # case from teal-banner.
        keys = sorted({lab.key for group in eligible.values() for lab in group})
        moved = True
        while moved:
            moved = False
            for a in keys:
                for b in keys:
                    if load[a] > load[b] + 1 and (moves := chain(a, b)):
                        for kind, giver, taker in moves:
                            cases[kind, giver] -= 1
                            cases[kind, taker] += 1
                        load[a] -= 1
                        load[b] += 1
                        moved = True
        plans = [
            (kind, lab)
            for kind in quotas
            for lab in eligible[kind]
            for _ in range(cases[kind, lab.key])
        ]
        rng.shuffle(plans)
        return plans

    def _pick_variant(
        self,
        genes: list[str],
        classes: set[str] | frozenset[str],
        modes: set[str] | None = None,
        exclude: set[str] = frozenset(),  # pyright: ignore[reportArgumentType]
    ) -> sources.Variant | None:
        rng = self._rng
        candidates = [
            v
            for gene in genes
            if gene not in exclude
            for v in self._refs.variants.get(gene, [])
            if v.classification in classes
            and (modes is None or v.disease.inheritance in modes)
            and (v.hgvs_m is None) == (not gene.startswith("MT-"))
        ]
        if not candidates:
            return None
        gene = rng.choice(sorted({v.gene for v in candidates}))
        return rng.choice([v for v in candidates if v.gene == gene])

    def _literature_variant(self, variant: sources.Variant) -> sources.Variant | None:
        """Returns another pathogenic ClinVar variant of the same gene, or None."""
        others = [
            v
            for v in self._refs.variants.get(variant.gene, [])
            if v.classification == "pathogenic"
            and (v.hgvs_c, v.hgvs_m) != (variant.hgvs_c, variant.hgvs_m)
        ]
        return self._rng.choice(others) if others else None

    def _plan(self, kind: str, lab: labs.Lab) -> _Plan:
        rng = self._rng
        scenario = rng.choice(_scenarios(lab, kind))
        area = None
        if kind == "exome" and scenario != "upd":
            area = rng.choice([a for a in labs.AREAS if a.name in _PEDIATRIC])
        elif kind in ("panel", "single_gene", "targeted"):
            area = rng.choice(labs.AREAS)
        return _Plan(lab, kind, scenario, area)

    def _tags(self, plan: _Plan, has_variants: bool, has_features: bool) -> set[str]:
        rng = self._rng
        allowed = set(TAGS)
        if plan.kind != "panel":
            allowed.discard("gene_list_distractor")
        if plan.kind != "exome" or not plan.lab.trio or plan.scenario == "upd":
            allowed.discard("trio_columns")
        if plan.scenario not in ("positive", "vus_only"):
            allowed.discard("multiple_variants")
        if plan.scenario not in ("positive", "vus_only", "mixed", "indeterminate"):
            allowed.discard("table_split_across_pages")
        if plan.kind in ("targeted", "single_gene"):
            # The second variant of multiple_variants is in another gene.
            allowed -= {"multiple_variants", "table_split_across_pages"}
        if plan.kind in _SPECIAL_KINDS or plan.scenario == "upd":
            # One finding, which has no HGVS to name in the text or to print
            # in another style.
            allowed -= {
                "multiple_variants",
                "table_split_across_pages",
                "repeated_variant",
                "legacy_gene_symbol",
                "nonstandard_hgvs",
            }
        if plan.kind in ("array", "karyotype"):
            allowed.discard("boilerplate_variant_notation")
        if plan.kind == "karyotype":
            allowed.discard("ambiguous_specimen")
        if not has_variants:
            allowed -= {
                "table_split_across_pages",
                "repeated_variant",
                "legacy_gene_symbol",
                "nonstandard_hgvs",
            }
        if not has_features:
            allowed -= {"negated_or_uncertain_phenotypes", "provided_phenotype_page"}
        if "submitter_patient_id" not in plan.lab.ids(random.Random(0)):
            allowed.discard("multiple_patient_ids")
        if "provided_phenotype_page" in allowed and "late_page_evidence" in allowed:
            allowed.discard(
                rng.choice(["provided_phenotype_page", "late_page_evidence"])
            )
        count = rng.choice([1, 2, 2, 3])
        # Sorted first, because a set's order changes from process to process.
        ranked = sorted(
            sorted(allowed), key=lambda t: (self._tag_counts[t], rng.random())
        )
        chosen = ranked[:count]
        if "table_split_across_pages" in chosen and "multiple_variants" in allowed:
            chosen.append("multiple_variants")
        self._tag_counts.update(chosen)
        return set(chosen)

    def _variants(
        self, plan: _Plan, tags: set[str]
    ) -> list[tuple[sources.Variant, bool]]:
        """Returns the variants of the case, each with whether it is secondary."""
        vus = {"uncertain_significance"}
        genes: list[str]
        if plan.kind == "mito":
            genes = list(labs.MITO_GENES)
        elif plan.kind == "carrier":
            genes = list(plan.lab.carrier_genes or labs.CARRIER_GENES)
        else:
            assert plan.area is not None
            genes = list(plan.area.genes)
            if plan.kind == "single_gene":
                genes = [
                    self._rng.choice([g for g in genes if g in self._refs.variants])
                ]
        picks: list[tuple[sources.Variant | None, bool]] = []
        if plan.kind == "targeted":
            if plan.scenario == "positive":
                picks.append((self._pick_variant(genes, _PATHOGENIC), False))
        elif plan.scenario == "positive":
            first = self._pick_variant(genes, _PATHOGENIC)
            picks.append((first, False))
            # Without a pathogenic variant, a second one would make a positive
            # case of a variant of uncertain significance alone.
            if first and "multiple_variants" in tags:
                picks.append(
                    (self._pick_variant(genes, vus, exclude={first.gene}), False)
                )
        elif plan.scenario == "mixed":
            first = self._pick_variant(genes, _PATHOGENIC)
            used = {first.gene} if first else set()
            picks += [
                (first, False),
                (self._pick_variant(genes, vus, exclude=used), False),
            ]
        elif plan.scenario == "vus_only":
            picks.append((self._pick_variant(genes, vus), False))
            if "multiple_variants" in tags:
                used = {p.gene for p, _ in picks if p}
                picks.append((self._pick_variant(genes, vus, exclude=used), False))
        elif plan.scenario == "carrier":
            picks.append(
                (self._pick_variant(genes, _PATHOGENIC, {"autosomal_recessive"}), False)
            )
        elif plan.scenario == "indeterminate":
            # A pathogenic variant and a VUS in the same recessive gene, in
            # unknown phase.
            recessive = {"autosomal_recessive"}
            first = self._pick_variant(genes, _PATHOGENIC, recessive)
            if first is not None:
                second = self._pick_variant([first.gene], vus, recessive)
                picks += [(first, False), (second, False)] if second else []
        elif plan.scenario == "secondary_finding":
            picks.append(
                (
                    self._pick_variant(
                        list(labs.SECONDARY_GENES), _PATHOGENIC, {"autosomal_dominant"}
                    ),
                    True,
                )
            )
        return [(v, secondary) for v, secondary in picks if v is not None]

    def _features(
        self, phenotypes: tuple[str, ...], sex: str, negated: bool
    ) -> list[tuple[str, str, bool | None]]:
        """Returns (HPO ID, printed text, present) for each of the patient's features.

        Args:
            phenotypes: The features of the patient's condition, most frequent
                first.
            sex: The patient's sex, which leaves out the other sex's features.
            negated: Whether the last feature is absent or uncertain.

        Returns:
            The features, none of whose text contains another's.
        """
        rng = self._rng
        words = _OTHER_SEX_WORDS[sex]
        fitting = [
            t
            for t in phenotypes
            if not any(w in self._refs.terms[t].label.casefold() for w in words)
        ]
        # The most frequent features, in random order, so that a patient has
        # the typical features of the disease rather than its rare ones.
        ids = fitting[:8]
        rng.shuffle(ids)
        wanted = rng.randint(2, 5)
        features: list[tuple[str, str, bool | None]] = []
        for hpo_id in ids:
            term = self._refs.terms[hpo_id]
            names = [term.label, *[s for s in term.synonyms if len(s) < 40]]
            text = rng.choice(names[:4])
            texts = [t.casefold() for _, t, _ in features]
            if any(text.casefold() in t or t in text.casefold() for t in texts):
                continue
            features.append((hpo_id, text, True))
            if len(features) == wanted:
                break
        if negated and len(features) >= 2:
            hpo_id, text, _ = features[-1]
            if text[:1].isupper() and text[1:2].islower():
                text = text[0].lower() + text[1:]
            features[-1] = (hpo_id, text, rng.choice([False, None]))
        return features

    def _dates(self, plan: _Plan, age: int, lab_prints_started: bool) -> dict[str, Any]:
        rng = self._rng
        report = datetime.date(2019, 1, 1) + datetime.timedelta(rng.randint(0, 2800))
        turnaround = (
            rng.randint(42, 120) if plan.kind == "exome" else rng.randint(14, 70)
        )
        received = report - datetime.timedelta(turnaround)
        collected = received - datetime.timedelta(rng.randint(1, 10))
        started = received + datetime.timedelta(rng.randint(0, 5))
        birth = collected - datetime.timedelta(365 * age + rng.randint(30, 360))
        dates = {
            "date_of_birth": birth,
            "collection_date": collected,
            "received_date": received,
            "report_date": report,
        }
        if lab_prints_started:
            dates["test_started_date"] = started
        return dates

    def case(self, number: int, split: str, kind: str, lab: labs.Lab) -> dict[str, Any]:
        """Returns one case of a kind of test and a template: its truth,
        distractors and card."""
        plan = self._plan(kind, lab)
        if plan.kind in _SPECIAL_KINDS or plan.scenario == "upd":
            build = {
                "array": self._array,
                "karyotype": self._karyotype,
                "repeat": self._repeat,
                "sma": self._sma,
                "methylation": self._methylation,
            }.get(plan.kind, self._disomy)
            found = build(plan)
        else:
            found = self._sequenced(plan)
        if found is None:
            return self.case(number, split, kind, lab)
        return self._assemble(number, split, plan, found)

    def _item(self, **values: Any) -> dict[str, Any]:
        """Returns a variant of the record, with every field of the schema."""
        item: dict[str, Any] = dict.fromkeys(self._variant_fields)
        item.update({"is_secondary_finding": False, **values})
        return item

    def _sequenced(self, plan: _Plan) -> _Found | None:
        """Returns the findings of a test that sequences genes, or None to retry."""
        rng = self._rng
        lab, area = plan.lab, plan.area
        provisional = self._variants(plan, {"multiple_variants"})
        tested = None
        if plan.kind == "targeted":
            assert area is not None
            tested = (
                provisional[0][0]
                if provisional
                else self._pick_variant(list(area.genes), _PATHOGENIC)
            )
            if tested is None:
                return None
        # The gene that a single-gene, carrier or targeted test names, also
        # when the result is negative.
        focus = None
        if plan.kind in ("single_gene", "carrier", "targeted"):
            focus = provisional[0][0] if provisional else tested
        if focus is None and plan.kind in ("single_gene", "carrier"):
            focus = self._pick_variant(
                list(
                    (plan.lab.carrier_genes or labs.CARRIER_GENES)
                    if plan.kind == "carrier"
                    else area.genes  # pyright: ignore[reportOptionalMemberAccess]
                ),
                _PATHOGENIC,
                {"autosomal_recessive"} if plan.kind == "carrier" else None,
            )
        primary = [v for v, secondary in provisional if not secondary]
        disease = primary[0].disease if primary else None
        if focus is not None:
            disease = focus.disease
        if disease is None and area is not None:
            fallback = self._pick_variant(list(area.genes), {"pathogenic"})
            disease = fallback.disease if fallback else None
        if plan.kind == "mito" and disease is None:
            fallback = self._pick_variant(list(labs.MITO_GENES), {"pathogenic"})
            disease = fallback.disease if fallback else None
        has_features = plan.kind != "carrier" and disease is not None
        tags = self._tags(plan, bool(provisional), has_features)
        found = provisional
        if "multiple_variants" not in tags and plan.scenario in (
            "positive",
            "vus_only",
        ):
            found = provisional[:1]
        if plan.scenario != "negative" and not found:
            return None
        if len(found) < 2:
            tags -= {"table_split_across_pages", "multiple_variants"}

        sexes = [_x_linked_sex(v) for v, secondary in found if not secondary]
        sex = next((s for s in sexes if s), None) or rng.choice(["Female", "Male"])
        if area is not None:
            age = rng.randint(*area.age)
        elif plan.kind == "carrier":
            age = rng.randint(20, 40)
        else:
            age = rng.randint(4, 40)
        trio = "trio_columns" in tags
        if trio:
            age = min(age, 12)

        if plan.kind == "exome":
            test_name = lab.exome_name[1 if trio else 0]
            test_type = "genome" if lab.genome else "exome"
        elif plan.kind == "targeted":
            assert tested is not None
            test_name = f"{tested.gene} {_short_change(tested)} Variant Analysis"
            test_type = "targeted_variant"
        elif plan.kind == "panel":
            assert area is not None
            test_name = lab.panel_name(area.name)
            test_type = "panel"
        elif plan.kind == "single_gene":
            gene = focus.gene if focus else rng.choice(area.genes)  # pyright: ignore[reportOptionalMemberAccess]
            test_name = f"{gene} Gene Sequencing and Deletion/Duplication Analysis"
            test_type = "single_gene"
        elif plan.kind == "carrier":
            test_name = lab.carrier_name
            test_type = "panel"
        else:
            test_name = "Mitochondrial Genome Sequencing"
            test_type = "other"
        if area is not None:
            indication = rng.choice(area.indication)
        elif plan.kind == "carrier" and lab.carrier_genes and disease:
            indication = f"Partner is a carrier of {disease.label}"
        elif plan.kind == "carrier":
            indication = "Reproductive carrier screening"
        else:
            indication = "Suspected mitochondrial disorder"

        items, normalized = [], []
        for variant, secondary in found:
            zygosity = _zygosity(
                variant.disease.inheritance,
                sex,
                diagnostic=not secondary
                and plan.scenario not in ("carrier", "indeterminate")
                and variant.classification != "uncertain_significance",
            )
            printed_gene = variant.gene
            previous = self._refs.previous_symbols.get(variant.gene, [])
            if "legacy_gene_symbol" in tags and previous:
                printed_gene = rng.choice(previous)
            protein = _protein(
                variant.hgvs_p, lab.protein_style, "nonstandard_hgvs" in tags
            )
            zygosity_raw = lab.zygosity[zygosity]
            if zygosity == "heteroplasmic":
                zygosity_raw = f"{zygosity_raw} ({rng.randint(15, 85)}%)"
            origin = None
            if trio:
                if (
                    variant.classification != "uncertain_significance"
                    and zygosity == "heterozygous"
                ):
                    origin = "de_novo"
                elif zygosity == "hemizygous":
                    origin = "maternal"
                elif zygosity == "homozygous":
                    origin = "both_parents"
                else:
                    origin = rng.choice(["maternal", "paternal"])
            items.append(
                self._item(
                    gene_symbol=printed_gene,
                    transcript=variant.transcript,
                    hgvs_c=variant.hgvs_c,
                    hgvs_p=protein,
                    dna_change_raw=variant.hgvs_m,
                    classification_raw=lab.classification[variant.classification],
                    classification=variant.classification,
                    zygosity_raw=zygosity_raw,
                    zygosity=zygosity,
                    parental_origin_raw=_ORIGIN[origin] if origin else None,
                    parental_origin=origin,
                    associated_phenotype=variant.disease.label,
                    mode_of_inheritance_raw=lab.inheritance[
                        variant.disease.inheritance
                    ],
                    mode_of_inheritance=variant.disease.inheritance,
                    is_secondary_finding=secondary,
                    variant_type_raw=_variant_type(variant, lab.variant_type_style),
                    chromosomal_position=(
                        lab.position.format(
                            chromosome=variant.chromosome,
                            start=variant.start,
                            stop=variant.stop,
                        )
                        if lab.position and variant.chromosome
                        else None
                    ),
                )
            )
            normalized.append(
                {
                    "gene_symbol": variant.gene,
                    "hgnc_id": variant.hgnc_id,
                    "disease_id": variant.disease.mondo_id,
                    "clinvar_variation_id": variant.variation_id,
                }
            )
        # A tag stays only if it changed the report, so that results split by
        # tag count only the reports that have the challenge.
        current = [n["gene_symbol"] for n in normalized]
        if [v["gene_symbol"] for v in items] == current:
            tags.discard("legacy_gene_symbol")
        if not any(v["hgvs_p"] for v in items):
            tags.discard("nonstandard_hgvs")

        printed = {
            v.gene: item["gene_symbol"]
            for (v, _), item in zip(found, items, strict=True)
        }
        genes = [printed.get(g, g) for g in area.genes] if area else []
        if plan.kind == "single_gene" and focus is not None:
            genes = [printed.get(focus.gene, focus.gene)]
            test_name = test_name.replace(focus.gene, genes[0], 1)
        # The transcript of each gene that a gene list prints: ClinVar's most
        # common one, or the variant's.
        transcripts = {
            printed.get(g, g): collections.Counter(
                v.transcript for v in self._refs.variants[g]
            ).most_common(1)[0][0]
            for g in (area.genes if area else ())
            if self._refs.variants.get(g)
        }
        transcripts |= {v["gene_symbol"]: v["transcript"] for v in items}
        distractors: list[dict[str, str]] = []
        if "gene_list_distractor" in tags:
            distractors += [
                {"kind": "gene_list", "text": g}
                for g in genes
                if g not in printed.values()
            ]
        if lab.literature_variant and found:
            first = found[0][0]
            cited = self._literature_variant(first)
            if cited is not None:
                distractors.append(
                    {
                        "kind": "literature_variant",
                        "text": cited.hgvs_c or cited.hgvs_m or "",
                        "gene": printed[first.gene],
                    }
                )
        if lab.results_to_note:
            distractors += [
                {"kind": "result_to_note", "text": text}
                for text in (
                    f"FMR1: {rng.randint(20, 32)}, {rng.randint(29, 40)} CGG repeats",
                    f"SMN1: {rng.choice([2, 3])} copies",
                )
            ]
        if lab.clinvar_ids:
            distractors += [
                {"kind": "clinvar_id", "text": v.variation_id} for v, _ in found
            ]
        details: dict[str, Any] = {}
        if plan.kind == "carrier" and lab.carrier_genes and focus is not None:
            # The reason for testing is the partner's variant, which the
            # report prints with the partner's date of birth.
            partner = self._literature_variant(focus) or focus
            born = datetime.date(2019, 1, 1) - datetime.timedelta(
                rng.randint(365 * 22, 365 * 40)
            )
            details["partner"] = {
                "name": rng.choice(
                    labs.FIRST_NAMES["Male" if sex == "Female" else "Female"]
                ),
                "born": born.strftime("%d/%m/%Y"),
                "change": partner.hgvs_c or "",
            }
            distractors += [
                {"kind": "partner_date_of_birth", "text": details["partner"]["born"]},
                {"kind": "partner_variant", "text": details["partner"]["change"]},
            ]
        if tested is not None and not found:
            distractors.append(
                {
                    "kind": "tested_variant",
                    "text": tested.hgvs_c or "",
                    "gene": tested.gene,
                }
            )
        return _Found(
            tags=tags,
            items=items,
            normalized=normalized,
            sex=sex,
            age=age,
            disease=disease,
            phenotypes=disease.phenotypes if has_features and disease else (),
            test_name=test_name,
            test_type=test_type,
            indication=indication,
            genome_build=lab.build,
            focus={
                "gene": printed.get(focus.gene, focus.gene),
                "transcript": focus.transcript or "",
                "condition": focus.disease.label,
            }
            if focus
            else None,
            distractors=distractors,
            card=[_card_variant(v) for v in items],
            fields=_fields(items) | {"condition": disease.label if disease else ""},
            details=details,
            genes=genes,
            transcripts=transcripts,
        )

    def _array(self, plan: _Plan) -> _Found | None:
        """Returns the findings of a chromosomal microarray, from ClinVar."""
        rng, lab = self._rng, plan.lab
        assert lab.array is not None
        sex = rng.choice(["Female", "Male"])
        found = _Found(
            tags=set(),
            items=[],
            normalized=[],
            sex=sex,
            age=rng.randint(1, 12),
            disease=None,
            phenotypes=self._array_features,
            test_name=lab.array.name,
            test_type="microarray",
            indication=rng.choice(_ARRAY_INDICATIONS),
            genome_build=lab.array.build,
        )
        if plan.scenario == "negative":
            notation = lab.array.normal[sex]
            found.distractors.append(
                {"kind": "normal_array_notation", "text": notation}
            )
            found.details = {"normal": notation}
        else:
            classes = (
                _PATHOGENIC
                if plan.scenario == "positive"
                else {"uncertain_significance"}
            )
            pool = [
                c
                for c in self._refs.copy_number_changes
                if c.classification in classes
                and (c.chromosome != "X" or c.copy_number in (0, 1, 2, 3))
                and (c.chromosome == "X" or c.copy_number in (0, 1, 3))
            ]
            if not pool:
                return None
            change = rng.choice(pool)
            if change.chromosome == "X":
                found.sex = "Male" if change.copy_number in (0, 2) else "Female"
            baseline = 1 if change.chromosome == "X" and found.sex == "Male" else 2
            gain = change.copy_number > baseline
            if baseline == 1:
                zygosity = "hemizygous"
            else:
                zygosity = "homozygous" if change.copy_number == 0 else "heterozygous"
            start, stop = change.positions[lab.array.build]
            band = _iscn_band(change.cytoband)
            disease = change.disease
            found.disease = disease
            if disease and disease.phenotypes:
                found.phenotypes = disease.phenotypes
            found.items.append(
                self._item(
                    dna_change_raw=lab.array.notation.format(
                        band=band,
                        start=start,
                        stop=stop,
                        copy_number=change.copy_number,
                    ),
                    chromosomal_position=lab.position.format(
                        chromosome=change.chromosome, start=start, stop=stop
                    )
                    if lab.position
                    else None,
                    copy_number=change.copy_number,
                    classification_raw=lab.classification[change.classification],
                    classification=change.classification,
                    associated_phenotype=disease.label if disease else None,
                    variant_type_raw=lab.array.change_words[gain]
                    if lab.array.change_words
                    else None,
                    zygosity_raw=lab.zygosity[zygosity] if lab.array.zygosity else None,
                    zygosity=zygosity if lab.array.zygosity else None,
                )
            )
            found.normalized.append(
                {
                    "gene_symbol": None,
                    "hgnc_id": None,
                    "disease_id": disease.mondo_id if disease else None,
                    "clinvar_variation_id": change.variation_id,
                }
            )
            size = _size(stop - start + 1)
            words = "gain (duplication)" if gain else "loss (deletion)"
            card = {
                "change": f"a copy-number {words} of {size} at {band}, a region "
                f"with {change.genes} genes",
                "classification": labs.SENTENCE_CLASSES[change.classification],
                "condition": disease.label if disease else None,
                "finding": "primary",
            }
            found.card = [{k: v for k, v in card.items() if v}]
            found.details = {
                "band": band,
                "size": size,
                "genes": change.genes,
                "gain": gain,
            }
            length = stop - start + 1
            approximate = (
                f"~{length / 1_000_000:.1f} Mb"
                if length >= 1_000_000
                else f"~{round(length / 1000)} kb"
            )
            change_word = "Duplication" if gain else "Deletion"
            found.fields = _fields(found.items) | {
                "size": approximate,
                "SIZE": size.upper(),
                "change": change_word,
                "CHANGE": change_word.upper(),
                "BAND": band.upper(),
            }
        found.fields |= {
            "sex": found.sex.lower(),
            "Sex": found.sex,
            "SEX": found.sex.upper(),
        }
        found.tags = self._tags(plan, bool(found.items), bool(found.phenotypes))
        return found

    def _karyotype(self, plan: _Plan) -> _Found:
        """Returns the findings of a chromosome analysis."""
        rng = self._rng
        entry = rng.choice(_KARYOTYPES[plan.scenario])
        disease = self._refs.syndromes.get(entry.mondo_id or "")
        phenotypes = disease.phenotypes if disease else ()
        mosaic = [int(n) for n in re.findall(r"\[(\d+)\]", entry.karyotype)]
        return _Found(
            tags=self._tags(plan, False, bool(phenotypes)),
            items=[],
            normalized=[],
            sex=entry.sex,
            age=rng.randint(*entry.age),
            disease=disease,
            phenotypes=phenotypes,
            test_name=plan.lab.karyotype_name,
            test_type="karyotype",
            indication=rng.choice(entry.indications),
            karyotype=entry.karyotype,
            fields={"sex": entry.sex.lower(), "finding": entry.meaning},
            details={"cells": sum(mosaic) or 20, "finding": entry.meaning},
        )

    def _repeat(self, plan: _Plan) -> _Found:
        """Returns the findings of a repeat analysis of a gene the lab tests."""
        gene = self._rng.choice(plan.lab.repeat_genes)
        if gene == "FMR1":
            return self._fragile_x(plan)
        return self._expansion(plan, _EXPANSIONS[gene])

    def _expansion(self, plan: _Plan, expansion: _Expansion) -> _Found:
        """Returns the findings of a test for a dominant repeat expansion."""
        rng, lab = self._rng, plan.lab
        disease = self._refs.syndromes[expansion.mondo_id]
        unit = expansion.unit
        normal = sorted(rng.randint(*expansion.normal) for _ in range(2))
        found = _Found(
            tags=set(),
            items=[],
            normalized=[],
            sex=rng.choice(["Female", "Male"]),
            age=rng.randint(*expansion.age),
            disease=disease,
            phenotypes=disease.phenotypes if plan.scenario == "positive" else (),
            test_name=expansion.test,
            test_type="single_gene",
            indication=rng.choice(expansion.indications),
            focus={
                "gene": expansion.gene,
                "transcript": expansion.transcript,
                "condition": disease.label,
            },
        )
        if plan.scenario == "negative":
            sizes = f"{normal[0]} and {normal[1]} {unit} repeats"
            found.distractors.append({"kind": "normal_repeat_size", "text": sizes})
            found.details = {"repeats": sizes, "unit": unit}
            found.fields = {"summary": "Negative"}
            found.meaning = (
                f"Both {expansion.gene} alleles have {unit} repeat sizes in the "
                "normal range."
            )
        else:
            if expansion.expanded:
                size = rng.randint(*expansion.expanded)
                sizes = f"{normal[0]} and {size} {unit} repeats"
                summary = (
                    f"Heterozygous for {size} {unit} Repeats ({expansion.printed})"
                )
            else:
                sizes = f"{normal[0]} and >30 {unit} repeats"
                summary = "Positive"
            found.items.append(
                self._item(
                    gene_symbol=expansion.gene,
                    transcript=expansion.transcript,
                    dna_change_raw=sizes,
                    zygosity_raw=lab.zygosity["heterozygous"],
                    zygosity="heterozygous",
                    classification_raw=expansion.printed,
                    classification="pathogenic",
                    associated_phenotype=disease.label,
                    mode_of_inheritance_raw=lab.inheritance[disease.inheritance],
                    mode_of_inheritance=disease.inheritance,
                )
            )
            found.normalized.append(
                {
                    "gene_symbol": expansion.gene,
                    "hgnc_id": expansion.hgnc_id,
                    "disease_id": expansion.mondo_id,
                    "clinvar_variation_id": None,
                }
            )
            found.card = [
                {
                    "gene": expansion.gene,
                    "change": f"one normal allele and one expanded {unit} repeat "
                    "allele of the size that causes disease",
                    "zygosity": "heterozygous",
                    "classification": "pathogenic",
                    "condition": disease.label,
                    "inheritance": _inheritance_words(disease.inheritance),
                    "finding": "primary",
                }
            ]
            found.details = {"unit": unit}
            found.fields = {"summary": summary}
            found.meaning = (
                f"The patient has one normal {expansion.gene} allele and one "
                f"expanded allele of the size that causes {disease.label}."
            )
        found.tags = self._tags(plan, bool(found.items), bool(found.phenotypes))
        return found

    def _methylation(self, plan: _Plan) -> _Found:
        """Returns the findings of methylation-specific MLPA of 15q11.2q13.

        A positive result names the syndrome and has no variant, because the
        test doesn't tell a uniparental disomy from an imprinting defect.
        """
        rng = self._rng
        syndrome, mondo_id, parent, indications = rng.choice(_METHYLATION)
        disease = self._refs.syndromes[mondo_id]
        positive = plan.scenario == "positive"
        found = _Found(
            tags=set(),
            items=[],
            normalized=[],
            sex=rng.choice(["Female", "Male"]),
            age=rng.randint(0, 6),
            disease=disease,
            phenotypes=disease.phenotypes,
            test_name="Prader-Willi/Angelman Syndrome Analysis via MS-MLPA",
            test_type="other",
            indication=rng.choice(indications),
            fields={"syndrome": syndrome},
            details={"parent": parent if positive else None, "syndrome": syndrome},
        )
        found.tags = self._tags(plan, False, bool(found.phenotypes))
        return found

    def _fragile_x(self, plan: _Plan) -> _Found:
        """Returns the findings of an FMR1 repeat analysis for fragile X syndrome."""
        rng, lab = self._rng, plan.lab
        gene, hgnc_id, transcript, mondo_id = _FMR1
        disease = self._refs.syndromes[mondo_id]
        screening = plan.scenario == "carrier" or (
            plan.scenario == "negative" and rng.random() < 0.5
        )
        if screening:
            sex, age = "Female", rng.randint(22, 38)
            test_name = "Fragile X Carrier Screening"
            indication = rng.choice(
                [
                    "Reproductive carrier screening",
                    "Family history of fragile X syndrome",
                ]
            )
        else:
            sex = (
                "Male"
                if plan.scenario == "positive"
                else rng.choice(["Female", "Male"])
            )
            age = rng.randint(3, 12)
            test_name = "Fragile X Syndrome, Diagnostic"
            indication = rng.choice(
                [
                    "Developmental delay",
                    "Intellectual disability",
                    "Autism spectrum disorder",
                ]
            )
        normal = sorted(rng.randint(20, 40) for _ in range(2 if sex == "Female" else 1))
        found = _Found(
            tags=set(),
            items=[],
            normalized=[],
            sex=sex,
            age=age,
            disease=disease,
            phenotypes=disease.phenotypes if plan.scenario == "positive" else (),
            test_name=test_name,
            test_type="single_gene",
            indication=indication,
            focus={"gene": gene, "transcript": transcript, "condition": disease.label},
        )
        if plan.scenario == "negative":
            sizes = " and ".join(map(str, normal)) + " CGG repeats"
            found.distractors.append({"kind": "normal_repeat_size", "text": sizes})
            found.details = {"repeats": sizes}
        else:
            if plan.scenario == "carrier":
                sizes = f"{normal[0]} and {rng.randint(55, 140)} CGG repeats"
                printed, classification = "Premutation allele", "other"
                words = "a premutation-size CGG repeat expansion"
            else:
                sizes, printed, classification = (
                    ">200 CGG repeats",
                    "Full mutation allele",
                    "pathogenic",
                )
                words = "a full-mutation CGG repeat expansion"
            found.items.append(
                self._item(
                    gene_symbol=gene,
                    transcript=transcript,
                    dna_change_raw=sizes,
                    classification_raw=printed,
                    classification=classification,
                    associated_phenotype=disease.label,
                    mode_of_inheritance_raw=lab.inheritance[disease.inheritance],
                    mode_of_inheritance=disease.inheritance,
                )
            )
            found.normalized.append(
                {
                    "gene_symbol": gene,
                    "hgnc_id": hgnc_id,
                    "disease_id": mondo_id,
                    "clinvar_variation_id": None,
                }
            )
            found.card = [
                {
                    "gene": gene,
                    "change": words,
                    "classification": printed.lower(),
                    "condition": disease.label,
                    "inheritance": _inheritance_words(disease.inheritance),
                    "finding": "primary",
                }
            ]
            found.details = {"agg": rng.randint(0, 2)}
        found.fields = _fields(found.items)
        found.tags = self._tags(plan, bool(found.items), bool(found.phenotypes))
        return found

    def _sma(self, plan: _Plan) -> _Found:
        """Returns the findings of an SMN1 and SMN2 copy-number test."""
        rng, lab = self._rng, plan.lab
        gene, hgnc_id, transcript, mondo_id = _SMN1
        disease = self._refs.syndromes[mondo_id]
        type_1 = self._refs.syndromes[_SMA_TYPE_1]
        copies = {"carrier": 1, "positive": 0}.get(plan.scenario, 2)
        affected = plan.scenario == "positive"
        smn2 = rng.randint(2, 4) if affected else rng.randint(1, 3)
        found = _Found(
            tags=set(),
            items=[],
            normalized=[],
            sex=rng.choice(["Female", "Male"]),
            age=0 if affected else rng.randint(22, 38),
            disease=disease,
            phenotypes=type_1.phenotypes if affected else (),
            test_name="Spinal Muscular Atrophy (SMA), Diagnostic"
            if affected
            else "Spinal Muscular Atrophy (SMA) Carrier Screening",
            test_type="single_gene",
            indication=rng.choice(
                ["Hypotonia and muscle weakness", "Delayed motor milestones"]
            )
            if affected
            else "Reproductive carrier screening",
            focus={"gene": gene, "transcript": transcript, "condition": disease.label},
            distractors=[
                {"kind": "smn2_copy_number", "text": f"SMN2 copy number: {smn2}"}
            ],
            details={"smn1": copies, "smn2": smn2},
        )
        if copies == 2:
            found.distractors.append(
                {"kind": "smn1_copy_number", "text": "SMN1 copy number: 2"}
            )
        else:
            found.items.append(
                self._item(
                    gene_symbol=gene,
                    transcript=transcript,
                    copy_number=copies,
                    associated_phenotype=disease.label,
                    mode_of_inheritance_raw=lab.inheritance[type_1.inheritance],
                    mode_of_inheritance=type_1.inheritance,
                )
            )
            found.normalized.append(
                {
                    "gene_symbol": gene,
                    "hgnc_id": hgnc_id,
                    "disease_id": mondo_id,
                    "clinvar_variation_id": None,
                }
            )
            words = (
                "a deletion of both copies"
                if affected
                else "a deletion of one of the two copies"
            )
            found.card = [
                {
                    "gene": gene,
                    "change": f"{words} of SMN1",
                    "condition": disease.label,
                    "inheritance": _inheritance_words(type_1.inheritance),
                    "finding": "primary",
                }
            ]
        found.fields = _fields(found.items)
        found.tags = self._tags(plan, bool(found.items), bool(found.phenotypes))
        return found

    def _disomy(self, plan: _Plan) -> _Found:
        """Returns the findings of a genome test that found a uniparental disomy."""
        rng, lab = self._rng, plan.lab
        entry = rng.choice(_DISOMIES)
        disease = self._refs.syndromes[entry.mondo_id]
        items = [
            self._item(
                dna_change_raw=f"{entry.bands} {entry.parent} uniparental disomy",
                chromosomal_position=f"chr{entry.chromosome}:1-{entry.length}",
                parental_origin_raw=entry.parent,
                parental_origin=entry.parent,
                associated_phenotype=disease.label,
            )
        ]
        return _Found(
            tags=self._tags(plan, True, bool(disease.phenotypes)),
            items=items,
            normalized=[
                {
                    "gene_symbol": None,
                    "hgnc_id": None,
                    "disease_id": disease.mondo_id,
                    "clinvar_variation_id": None,
                }
            ],
            sex=rng.choice(["Female", "Male"]),
            age=rng.randint(*entry.age),
            disease=disease,
            phenotypes=disease.phenotypes,
            test_name=lab.exome_name[0],
            test_type="genome" if lab.genome else "exome",
            indication=rng.choice(entry.indications),
            genome_build=lab.build,
            card=[
                {
                    "change": f"{entry.parent} uniparental disomy of chromosome "
                    f"{entry.chromosome}",
                    "condition": disease.label,
                    "finding": "primary",
                }
            ],
            fields=_fields(items),
            details={"genes": rng.randint(600, 1400), "size": _size(entry.length)},
        )

    def _assemble(
        self, number: int, split: str, plan: _Plan, found: _Found
    ) -> dict[str, Any]:
        """Returns the case: the record around the findings, and the card."""
        rng = self._rng
        lab, tags = plan.lab, found.tags
        case_id = f"SYN-{number:04d}"
        record: dict[str, Any] = dict.fromkeys(self._fields)
        record.update(lab.ids(rng))
        if "multiple_patient_ids" in tags:
            record["submitter_patient_id"] += (
                f", {lab.ids(rng)['submitter_patient_id']}"
            )
        dates = self._dates(plan, found.age, lab.prints_started)
        date_format = lab.date_format
        if "unusual_date_format" in tags:
            date_format = rng.choice(list(labs.UNUSUAL_DATE_FORMATS))
        for field, value in dates.items():
            record[field] = labs.date_formats()[date_format](value)
        record["sex"] = found.sex
        for field in lab.missing:
            record[field] = None
        specimens = labs.SPECIMENS
        if "ambiguous_specimen" in tags:
            specimens = labs.AMBIGUOUS_SPECIMENS
        elif plan.kind == "karyotype":
            specimens = labs.KARYOTYPE_SPECIMENS
        specimen, specimen_category = rng.choice(specimens)
        record.update(
            specimen_type=specimen,
            test_name=found.test_name,
            test_type=found.test_type,
            clinical_indication=found.indication,
            lab_name=lab.name,
            karyotype=found.karyotype,
            genome_build=found.genome_build,
            variants=found.items,
        )
        features = self._features(
            found.phenotypes, found.sex, "negated_or_uncertain_phenotypes" in tags
        )
        record["patient_phenotypes"] = [
            {"text": text, "present": present} for _, text, present in features
        ]
        record["overall_result_raw"] = lab.wording(plan.kind, plan.scenario).format_map(
            collections.defaultdict(str, found.fields)
        )

        distractors = list(found.distractors)
        if "boilerplate_variant_notation" in tags:
            ref, alt = rng.sample("ACGT", 2)
            distractors.append(
                {
                    "kind": "boilerplate_hgvs",
                    "text": f"c.{rng.randint(100, 3000)}{ref}>{alt}",
                }
            )
        if "family_history_distractor" in tags:
            mine = {hpo_id for hpo_id, _, _ in features}
            pool = [t for t in found.phenotypes if t not in mine]
            if pool:
                distractors.append(
                    {
                        "kind": "relative_feature",
                        "text": self._refs.terms[rng.choice(pool)].label,
                        "relative": rng.choice(_RELATIVES),
                    }
                )
            else:
                tags.discard("family_history_distractor")
        if "similar_identifiers" in tags:
            accession = record["lab_accession_number"]
            for label in rng.sample(_OTHER_ID_LABELS, 2):
                similar = accession
                while similar == accession:
                    similar = "".join(
                        rng.choice("0123456789") if c.isdigit() else c
                        for c in accession
                    )
                distractors.append(
                    {"kind": "identifier", "text": similar, "label": label}
                )
        unavailable = None
        if "explicitly_unavailable" in tags:
            present = [
                f
                for f in ("mrn", "submitter_patient_id", "collection_date")
                if record[f] is not None
            ]
            unavailable = rng.choice(present)
            record[unavailable] = None
        omitted = []
        if "missing_optional_fields" in tags:
            optional = [
                f
                for f in (
                    "test_started_date",
                    "received_date",
                    "submitter_patient_id",
                    "specimen_type",
                )
                if record[f] is not None
            ]
            omitted = rng.sample(optional, min(len(optional), rng.randint(1, 2)))
            for field in omitted:
                record[field] = None

        normalized = {
            field: (dates[field].isoformat() if record[field] is not None else None)
            if field in dates
            else None
            for field in (
                "date_of_birth",
                "collection_date",
                "received_date",
                "test_started_date",
                "report_date",
            )
        }
        normalized.update(
            specimen_type=specimen_category if record["specimen_type"] else None,
            overall_result=_RESULT_CATEGORY[plan.scenario],
            variants=found.normalized,
            patient_phenotypes=[{"hpo_id": hpo_id} for hpo_id, _, _ in features],
        )

        sex = found.sex
        patient = {
            "first_name": rng.choice(labs.FIRST_NAMES[sex]),
            "last_name": rng.choice(labs.LAST_NAMES),
            "age_years": found.age,
            "sex": sex,
        }
        meaning = (
            found.meaning
            or _KIND_MEANING.get((plan.kind, plan.scenario))
            or _MEANING[plan.scenario]
        )
        card = {
            "laboratory": lab.name,
            "test": record["test_name"],
            "test_kind": _KIND_WORDS[plan.kind],
            "reason_for_testing": record["clinical_indication"],
            "patient": {"age_years": found.age, "sex": sex},
            "result": meaning.format_map(collections.defaultdict(str, found.fields)),
            "condition": found.disease.label if found.disease else None,
            "variants": found.card,
            "instructions": [PROSE_TAGS[t] for t in sorted(tags) if t in PROSE_TAGS],
        }
        return {
            "case_id": case_id,
            "split": split,
            "generator": _VERSION,
            "lab": lab.key,
            "based_on": list(lab.based_on),
            "kind": plan.kind,
            "scenario": plan.scenario,
            "tags": sorted(tags),
            "patient": patient,
            "dates": {field: value.isoformat() for field, value in dates.items()},
            "date_format": date_format,
            "area": plan.area.name if plan.area else None,
            "genes": found.genes,
            "transcripts": found.transcripts,
            "focus": found.focus,
            "details": found.details,
            "record": record,
            "normalized": normalized,
            "distractors": distractors,
            "unavailable": unavailable,
            "omitted": omitted,
            "card": card,
        }


# Labels of other IDs, for the similar_identifiers tag. No template prints
# them otherwise.
_OTHER_ID_LABELS = ("Requisition #", "Kit ID", "Client Ref #", "Batch #")
_KIND_WORDS = {
    "panel": "multigene panel",
    "exome": "exome or genome sequencing",
    "single_gene": "single-gene sequencing and deletion/duplication analysis",
    "carrier": "carrier screen",
    "mito": "mitochondrial genome sequencing",
    "targeted": "targeted analysis of one known variant",
    "array": "chromosomal microarray",
    "karyotype": "chromosome analysis (karyotype)",
    "repeat": "repeat expansion analysis of one gene",
    "sma": "SMN1 and SMN2 copy-number analysis for spinal muscular atrophy",
    "methylation": "methylation-specific MLPA of 15q11.2q13 for Prader-Willi and "
    "Angelman syndromes",
}
_MEANING = {
    "positive": "A pathogenic or likely pathogenic variant explains the patient's "
    "features.",
    "mixed": "A pathogenic or likely pathogenic variant was found, and a variant of "
    "uncertain significance.",
    "negative": "No reportable variant was found.",
    "vus_only": "Only variants of uncertain significance were found.",
    "carrier": "The patient carries one pathogenic or likely pathogenic variant "
    "for a recessive condition and is not affected.",
    "secondary_finding": "The primary result is negative. A pathogenic or likely "
    "pathogenic variant was found in a gene of the ACMG secondary-findings list "
    "and is reported as a secondary finding.",
    "upd": "The patient inherited both copies of one chromosome from the same "
    "parent, and this uniparental disomy explains the patient's features.",
    "indeterminate": "A pathogenic or likely pathogenic variant and a variant of "
    "uncertain significance were found in the same gene of a recessive "
    "condition. It is not known whether they are on different copies of the "
    "gene, so the result is indeterminate.",
}
# What the result means for kinds of test whose results differ from the above.
_KIND_MEANING = {
    ("array", "positive"): "A pathogenic or likely pathogenic copy-number change "
    "explains the patient's features.",
    ("array", "vus_only"): "Only a copy-number change of uncertain significance "
    "was found.",
    ("array", "negative"): "No clinically significant copy-number change was found.",
    ("karyotype", "positive"): "The karyotype is abnormal. It shows {finding}.",
    ("karyotype", "carrier"): "The karyotype shows {finding}. The patient is "
    "healthy, but a balanced rearrangement raises the risk of miscarriage and "
    "of a child with an unbalanced karyotype.",
    ("karyotype", "negative"): "The karyotype is normal. It shows {finding}.",
    ("repeat", "carrier"): "The patient carries an FMR1 premutation allele and "
    "is not affected.",
    ("repeat", "positive"): "The patient has an FMR1 full mutation, which causes "
    "fragile X syndrome.",
    ("repeat", "negative"): "The patient's FMR1 repeat sizes are in the normal range.",
    ("sma", "carrier"): "The patient lacks one of the two usual copies of SMN1 "
    "and is a carrier of spinal muscular atrophy.",
    ("sma", "positive"): "The patient lacks both copies of SMN1 and has spinal "
    "muscular atrophy.",
    ("sma", "negative"): "The patient has the usual two copies of SMN1 and is "
    "not a carrier.",
    ("methylation", "positive"): "Copy number at 15q11.2q13 is normal, and only "
    "one parent's methylation pattern is present, which is consistent with "
    "{syndrome}. The test doesn't tell whether a uniparental disomy or an "
    "imprinting defect causes it.",
    ("methylation", "negative"): "Copy number and methylation at 15q11.2q13 are "
    "normal.",
}


def _inheritance_words(mode: str) -> str:
    """Returns a mode of inheritance in words, as X-linked recessive."""
    return mode.replace("_", " ").replace("x linked", "X-linked")


def _card_variant(variant: dict[str, Any]) -> dict[str, Any]:
    """Returns what the writing model needs to know of a variant."""
    mode = _inheritance_words(variant["mode_of_inheritance"])
    card = {
        "gene": variant["gene_symbol"],
        "change": variant["hgvs_c"] or variant["dna_change_raw"],
        "protein_change": variant["hgvs_p"],
        "zygosity": variant["zygosity"],
        "classification": labs.SENTENCE_CLASSES[variant["classification"]],
        "condition": variant["associated_phenotype"],
        "inheritance": mode,
        "origin": (variant["parental_origin"] or "").replace("_", " "),
        "finding": "secondary" if variant["is_secondary_finding"] else "primary",
    }
    return {key: value for key, value in card.items() if value}


def sample(refs: sources.References, seed: str, dev: int, test: int) -> list[dict]:
    """Returns `dev` dev cases and then `test` test cases, numbered from 1."""
    sampler = _Sampler(refs, seed)
    cases = []
    for split, count in (("dev", dev), ("test", test)):
        sampler.start_split()
        for kind, lab in sampler.plans(split, count):
            cases.append(sampler.case(len(cases) + 1, split, kind, lab))
    return cases
