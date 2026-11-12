"""The report templates of the synthetic reports, and the clinical areas they test.

Each template follows one layout family of the public sample reports in
gentrex-bench/public/catalog.csv. Its page layout is the HTML file
templates/<key>.html, and this module holds the rest: its wording of the
result, classifications and other values, its IDs and date format, and the
tests it reports. `based_on` names the sample reports. The lab names are
invented, and no template copies a lab's name, logo or text. Each name is a
colour that starts with the same letter as the real lab, as Indigo for
Invitae. Templates that follow the same real lab share a fictional name,
because a lab uses different layouts for different tests. Templates with
`held_out` set appear only in the test split.
"""

import dataclasses
import datetime
import random
from collections.abc import Callable
from typing import Any


def _digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789") for _ in range(n))


def _letters(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(n))


def _clock(d: datetime.date) -> str:
    """Returns a time of day that depends only on the date, as 08:54."""
    return f"{7 + d.toordinal() % 10:02d}:{d.toordinal() * 7 % 60:02d}"


DATE_FORMATS: dict[str, Callable[[datetime.date], str]] = {
    "m/d/yyyy": lambda d: f"{d.month}/{d.day}/{d.year}",
    "mm/dd/yyyy": lambda d: d.strftime("%m/%d/%Y"),
    "dd-mon-yyyy": lambda d: d.strftime("%d-%b-%Y").upper(),
    "mon dd, yyyy": lambda d: d.strftime("%b %d, %Y"),
    "month d, yyyy": lambda d: f"{d.strftime('%B')} {d.day}, {d.year}",
    "d month yyyy": lambda d: f"{d.day} {d.strftime('%B')} {d.year}",
    "d mon yyyy": lambda d: f"{d.day} {d.strftime('%b')} {d.year}",
    "yyyy-mm-dd": lambda d: d.isoformat(),
    "dd-mon-yy hh:mm": lambda d: f"{d.strftime('%d-%b-%y')} {_clock(d)}",
}

# Formats for the unusual_date_format tag, which `gentrex normalize` doesn't
# read, so the truth's ISO dates test whether it says so.
UNUSUAL_DATE_FORMATS: dict[str, Callable[[datetime.date], str]] = {
    "yyyy/mm/dd": lambda d: d.strftime("%Y/%m/%d"),
    "d.m.yyyy": lambda d: f"{d.day}.{d.month}.{d.year}",
    "mon d yyyy": lambda d: f"{d.strftime('%b')} {d.day} {d.year}",
}


def date_formats() -> dict[str, Callable[[datetime.date], str]]:
    """Returns every date format by its key, the usual and the unusual ones."""
    return DATE_FORMATS | UNUSUAL_DATE_FORMATS


# The kinds of test that the sampler makes.
KINDS = (
    "panel",
    "exome",
    "single_gene",
    "carrier",
    "mito",
    "targeted",
    "array",
    "karyotype",
    "repeat",
    "sma",
    "methylation",
)


def _results(
    positive: str,
    negative: str,
    uncertain: str,
    carrier: str = "",
    indeterminate: str = "Indeterminate",
) -> dict[str, str]:
    """Returns the headline result of each scenario from four wordings.

    A wording may name the first variant with {gene}, {hgvs}, {zygosity},
    {Zygosity}, {classification} and {printed_class}, the classification as
    the template prints it, and its condition with {condition}. Arrays and
    karyotypes add the size, change and band as {size} (~2.6 Mb), {SIZE}
    (2.62 MB), {change}, {CHANGE} and {BAND}, and the patient's {sex}, {Sex}
    or {SEX}. Repeat tests add {summary}, and methylation tests {syndrome}.
    """
    return {
        "positive": positive,
        "mixed": positive,
        "negative": negative,
        "secondary_finding": negative,
        "vus_only": uncertain,
        "carrier": carrier or positive,
        "upd": positive,
        "indeterminate": indeterminate,
    }


@dataclasses.dataclass(frozen=True)
class ArrayStyle:
    """How a template reports a chromosomal microarray.

    Attributes:
        name: The name of the test.
        build: The genome build of the positions, GRCh37 or GRCh38.
        notation: The ISCN of a finding, with {band}, {start}, {stop} and
            {copy_number}.
        normal: The ISCN of a normal result, by the patient's sex.
        change_words: The words for a loss and a gain, or None if the layout
            prints no type of change.
        zygosity: Whether the layout prints the zygosity of a change.
    """

    name: str
    build: str
    notation: str
    normal: dict[str, str]
    change_words: tuple[str, str] | None = None
    zygosity: bool = False


@dataclasses.dataclass(frozen=True)
class Lab:
    """A report template of a fictional laboratory.

    Attributes:
        key: Short name, used in the case files.
        name: The laboratory name printed on the report.
        based_on: IDs of the public sample reports whose layout it follows.
        kinds: The kinds of test it reports, from KINDS.
        date_format: Key of DATE_FORMATS.
        ids: Makes the IDs that the header prints, by field of the record.
        result: The headline result of each scenario.
        classification: The wording of each classification.
        zygosity: The wording of each zygosity.
        inheritance: The wording of each mode of inheritance.
        panel_name: The name of a panel test, from the clinical area's name.
        exome_name: The names of the proband and trio exome or genome tests.
        carrier_name: The name of a carrier screen.
        genome: Whether its exome kind is a genome test.
        protein_style: How protein changes print: plain (p.Arg412Trp),
            parentheses (p.(Arg412Trp)) or one_letter (p.R412W).
        variant_type_style: Variant types as words (Missense) or as Sequence
            Ontology terms (missense_variant); None if the layout prints no
            type.
        position: Format of a variant's GRCh38 position, with {chromosome},
            {start} and {stop}; None if the layout prints no position.
        prints_started: Whether the layout prints the date testing started.
        missing: Record fields that the layout never prints.
        trio: Whether the layout can show the parents of a trio.
        literature_variant: Whether the report cites a variant from the
            literature, which is a distractor.
        results_to_note: Whether the report lists other results that aren't
            variants, such as FMR1 repeats, which are distractors.
        held_out: Whether the template is kept out of the dev split.
        build: The genome build that the layout names for sequencing tests,
            or None if it names none.
        disomy: Whether the layout can report a uniparental disomy.
        array: How the layout reports a microarray, if it does.
        karyotype_name: The name of a chromosome analysis.
        kind_results: Headline results of kinds of test that word them
            differently from `result`, by kind.
        repeat_genes: The genes whose repeats the layout reports.
        carrier_genes: The genes of its carrier test, if not CARRIER_GENES.
        indeterminate: Whether a panel can have an indeterminate result: a
            pathogenic variant and a variant of uncertain significance in the
            same recessive gene.
        clinvar_ids: Whether the variant table prints ClinVar's variation
            IDs, which are distractors.
    """

    key: str
    name: str
    based_on: tuple[str, ...]
    kinds: tuple[str, ...]
    date_format: str
    ids: Callable[[random.Random], dict[str, str]]
    result: dict[str, str]
    classification: dict[str, str]
    zygosity: dict[str, str]
    inheritance: dict[str, str]
    panel_name: Callable[[str], str] = lambda area: f"{area} Panel"
    exome_name: tuple[str, str] = ("Exome Sequencing", "Exome Sequencing, Trio")
    carrier_name: str = "Carrier Screen"
    genome: bool = False
    protein_style: str = "plain"
    variant_type_style: str | None = None
    position: str | None = None
    prints_started: bool = False
    missing: tuple[str, ...] = ()
    trio: bool = False
    literature_variant: bool = False
    results_to_note: bool = False
    held_out: bool = False
    build: str | None = None
    disomy: bool = False
    array: ArrayStyle | None = None
    karyotype_name: str = "Chromosome Analysis"
    kind_results: dict[str, dict[str, str]] = dataclasses.field(default_factory=dict)
    repeat_genes: tuple[str, ...] = ()
    carrier_genes: tuple[str, ...] | None = None
    indeterminate: bool = False
    clinvar_ids: bool = False

    def wording(self, kind: str, scenario: str) -> str:
        """Returns the headline result of a scenario of a kind of test."""
        return self.kind_results.get(kind, self.result)[scenario]


def _words(cases: str) -> tuple[dict[str, str], dict[str, str]]:
    """Returns the zygosity and inheritance wordings in title, lower or upper case."""
    zygosity = {
        "heterozygous": "Heterozygous",
        "homozygous": "Homozygous",
        "hemizygous": "Hemizygous",
        "heteroplasmic": "Heteroplasmic",
        "homoplasmic": "Homoplasmic",
    }
    inheritance = {
        "autosomal_dominant": "Autosomal dominant",
        "autosomal_recessive": "Autosomal recessive",
        "x_linked": "X-linked",
        "x_linked_dominant": "X-linked dominant",
        "x_linked_recessive": "X-linked recessive",
        "mitochondrial": "Mitochondrial",
    }
    change = {"title": str, "lower": str.lower, "upper": str.upper}[cases]
    return (
        {k: change(v) for k, v in zygosity.items()},
        {k: change(v) if cases != "upper" else v for k, v in inheritance.items()},
    )


_TITLE_ZYGOSITY, _TITLE_INHERITANCE = _words("title")
_LOWER_ZYGOSITY, _LOWER_INHERITANCE = _words("lower")
_ABBREVIATED_ZYGOSITY = {
    "heterozygous": "HET",
    "homozygous": "HOM",
    "hemizygous": "HEM",
    "heteroplasmic": "HETEROPLASMIC",
    "homoplasmic": "HOMOPLASMIC",
}
_ABBREVIATED_INHERITANCE = {
    "autosomal_dominant": "AD",
    "autosomal_recessive": "AR",
    "x_linked": "XL",
    "x_linked_dominant": "XLD",
    "x_linked_recessive": "XLR",
    "mitochondrial": "Mitochondrial",
}
SENTENCE_CLASSES = {
    "pathogenic": "pathogenic",
    "likely_pathogenic": "likely pathogenic",
    "uncertain_significance": "variant of uncertain significance",
    "likely_benign": "likely benign",
    "benign": "benign",
}
_SENTENCE = "The patient is {zygosity} for {gene} {hgvs}, which is {classification}."
_INDETERMINATE = "Indeterminate: two variants in {gene}, in unknown phase."


def _bronze(
    key: str,
    based_on: tuple[str, ...],
    kinds: tuple[str, ...],
    result: dict[str, str],
    **names: Any,
) -> Lab:
    """Returns a template of Bronze, whose layouts share masthead and grid."""
    return Lab(
        key=key,
        name="Bronze Clinical Genomics",
        based_on=based_on,
        kinds=kinds,
        date_format="mon dd, yyyy",
        ids=lambda rng: {"lab_accession_number": _digits(rng, 7)},
        result=result,
        classification={
            "pathogenic": "Pathogenic",
            "likely_pathogenic": "Likely pathogenic",
            "uncertain_significance": "Variant of uncertain significance (VUS)",
            "likely_benign": "Likely benign",
            "benign": "Benign",
        },
        zygosity=_ABBREVIATED_ZYGOSITY,
        inheritance=_ABBREVIATED_INHERITANCE,
        protein_style="parentheses",
        variant_type_style="so",
        position="{chromosome}:{start}",
        prints_started=True,
        missing=("mrn",),
        literature_variant=True,
        build="GRCh38",
        **names,
    )


LABS = [
    Lab(
        key="graybar-panel",
        name="Aqua Genetics",
        based_on=("AMB01", "AMB02", "AMB10", "AMB11", "AMB12", "SR002", "SR003"),
        kinds=("panel", "single_gene"),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "lab_accession_number": f"{_digits(rng, 2)}-{_digits(rng, 6)}",
            "mrn": _digits(rng, 7),
        },
        result=_results(
            positive="POSITIVE: {printed_class} Detected",
            negative="NEGATIVE: No Clinically Significant Variants Detected",
            uncertain="Variant of Unknown Significance Detected",
        ),
        classification={
            "pathogenic": "Pathogenic Mutation",
            "likely_pathogenic": "Variant, Likely Pathogenic",
            "uncertain_significance": "Variant, Unknown Significance",
            "likely_benign": "Variant, Likely Benign",
            "benign": "Benign",
        },
        zygosity=_LOWER_ZYGOSITY,
        inheritance=_LOWER_INHERITANCE,
        panel_name=lambda area: area.split()[0] + "Scan",
        protein_style="one_letter",
        prints_started=True,
        missing=("report_date",),
        build="GRCh38",
    ),
    Lab(
        key="exome-box",
        name="Aqua Genetics",
        based_on=("AMB03", "AMB04", "AMB05", "AMB13"),
        kinds=("exome",),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "lab_accession_number": f"{_digits(rng, 2)}-{_digits(rng, 6)}",
            "mrn": _digits(rng, 8),
        },
        result=_results(
            positive="POSITIVE: Clinically Relevant Variant Detected",
            negative="NEGATIVE: No clinically relevant variants detected",
            uncertain="UNCERTAIN: Variant of Uncertain Clinical Relevance Detected",
        ),
        classification={
            "pathogenic": "Pathogenic Mutation",
            "likely_pathogenic": "Variant, Likely Pathogenic",
            "uncertain_significance": "Variant of Uncertain Significance",
            "likely_benign": "Variant, Likely Benign",
            "benign": "Benign",
        },
        zygosity=_TITLE_ZYGOSITY,
        inheritance=_TITLE_INHERITANCE,
        exome_name=("ExomeScan-Proband", "ExomeScan-Trio"),
        protein_style="one_letter",
        prints_started=True,
        trio=True,
        build="GRCh38",
    ),
    Lab(
        key="genome-card",
        name="Aqua Genetics",
        based_on=("AMB06", "AMB07", "AMB14", "AMB15", "AMB16", "AMB17"),
        kinds=("exome",),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "lab_accession_number": f"{_digits(rng, 2)}-{_digits(rng, 6)}",
            "mrn": _digits(rng, 6),
        },
        result=_results(
            positive="Positive", negative="Negative", uncertain="Uncertain"
        ),
        classification={
            "pathogenic": "Pathogenic",
            "likely_pathogenic": "Likely Pathogenic",
            "uncertain_significance": "Variant of Uncertain Significance",
            "likely_benign": "Likely Benign",
            "benign": "Benign",
        },
        zygosity=_TITLE_ZYGOSITY,
        inheritance=_TITLE_INHERITANCE,
        exome_name=("Genome Sequencing", "Genome Sequencing, Trio"),
        genome=True,
        position="chr{chromosome}:{start}",
        prints_started=True,
        trio=True,
        held_out=True,
        build="GRCh38",
        disomy=True,
    ),
    _bronze(
        key="findings-grid",
        indeterminate=True,
        based_on=(
            "BLU01",
            "BLU02",
            "BLU03",
            "BLU04",
            "SR012",
            "SR013",
            "SR014",
            "SR015",
            "SR017",
        ),
        kinds=("panel", "mito"),
        result=_results(
            positive=_SENTENCE,
            negative="Negative",
            uncertain=_SENTENCE.replace("{classification}", "a {classification}"),
            indeterminate=_INDETERMINATE,
        ),
    ),
    _bronze(
        key="screen-badge",
        based_on=("SR007", "SR008"),
        kinds=("carrier",),
        result=_results(positive="POSITIVE", negative="NEGATIVE", uncertain="NEGATIVE"),
        carrier_name="Comprehensive Carrier Screen",
    ),
    _bronze(
        key="results-statement",
        indeterminate=True,
        based_on=("SR010", "SR016"),
        kinds=("panel",),
        result=_results(
            positive=_SENTENCE,
            negative="Negative for explaining the patient's phenotype.",
            uncertain=_SENTENCE.replace("{classification}", "a {classification}"),
            indeterminate=_INDETERMINATE,
        ),
    ),
    _bronze(
        key="exome-findings",
        based_on=("SR011",),
        kinds=("exome",),
        result=_results(
            positive=_SENTENCE,
            negative="Negative.",
            uncertain=_SENTENCE.replace("{classification}", "a {classification}"),
        ),
        exome_name=("Exome Plus", "Exome Plus, Trio"),
    ),
    Lab(
        key="teal-banner",
        name="Lilac Molecular Laboratory",
        based_on=("LAB01",),
        kinds=("single_gene", "carrier"),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "lab_accession_number": _digits(rng, 8),
            "mrn": _digits(rng, 8),
        },
        result=_results(
            positive="POSITIVE",
            negative="NEGATIVE",
            uncertain="VARIANT OF UNCERTAIN SIGNIFICANCE",
        ),
        classification=SENTENCE_CLASSES,
        zygosity=_TITLE_ZYGOSITY,
        inheritance=_LOWER_INHERITANCE,
        carrier_name="Gene-specific Carrier Screening",
        build="GRCh38",
    ),
    Lab(
        key="enterprise",
        name="Lilac Molecular Laboratory",
        based_on=("LAB03", "LAB04", "LAB05", "LAB08"),
        kinds=("carrier", "single_gene", "repeat", "sma"),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "lab_accession_number": (
                f"{_digits(rng, 3)}-{_digits(rng, 3)}-{_digits(rng, 4)}-"
                f"{_digits(rng, 1)}"
            ),
            "mrn": _digits(rng, 8),
            "submitter_patient_id": _digits(rng, 9),
        },
        result=_results(
            positive="POSITIVE",
            negative="NEGATIVE",
            uncertain="VARIANT OF UNCERTAIN SIGNIFICANCE",
            carrier="POSITIVE: CARRIER",
        ),
        classification=SENTENCE_CLASSES,
        zygosity=_TITLE_ZYGOSITY,
        inheritance=_LOWER_INHERITANCE,
        carrier_name="Full-gene Sequencing Carrier Screen",
        position="CHR{chromosome}:{start}-{stop}",
        build="GRCh38",
        repeat_genes=("FMR1",),
        kind_results={
            "repeat": _results(
                positive="POSITIVE: FULL MUTATION",
                negative="NEGATIVE",
                uncertain="NEGATIVE",
                carrier="POSITIVE: PREMUTATION CARRIER",
            ),
            "sma": _results(
                positive="POSITIVE: AFFECTED",
                negative="NEGATIVE",
                uncertain="NEGATIVE",
                carrier="POSITIVE: CARRIER",
            ),
        },
    ),
    Lab(
        key="carrier-banner",
        name="Lilac Molecular Laboratory",
        based_on=("LAB06",),
        kinds=("carrier",),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "lab_accession_number": f"{_letters(rng, 2)}{_digits(rng, 7)}",
            "mrn": _digits(rng, 8),
        },
        result=_results(
            positive="RESULT: POSITIVE",
            negative="RESULT: NEGATIVE",
            uncertain="RESULT: NEGATIVE",
        ),
        classification={k: v.upper() for k, v in SENTENCE_CLASSES.items()},
        zygosity=_LOWER_ZYGOSITY,
        inheritance=_TITLE_INHERITANCE,
        carrier_name="Expanded Carrier Panel",
        results_to_note=True,
        build="GRCh38",
    ),
    Lab(
        key="dx-banner",
        name="Indigo Genetic Testing",
        based_on=("INV01",),
        kinds=("panel", "single_gene"),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "lab_accession_number": f"{_letters(rng, 2)}{_digits(rng, 7)}",
            "mrn": _digits(rng, 8),
        },
        result=_results(
            positive="RESULT: POSITIVE",
            negative="RESULT: NEGATIVE",
            uncertain="RESULT: UNCERTAIN",
        ),
        classification={
            "pathogenic": "Pathogenic",
            "likely_pathogenic": "Likely Pathogenic",
            "uncertain_significance": "Uncertain Significance",
            "likely_benign": "Likely Benign",
            "benign": "Benign",
        },
        zygosity=_TITLE_ZYGOSITY,
        inheritance=_TITLE_INHERITANCE,
        panel_name=lambda area: f"Comprehensive {area} Panel",
        build="GRCh38",
    ),
    Lab(
        key="snp-array",
        name="Aqua Genetics",
        based_on=("AMB08", "AMB09"),
        kinds=("array",),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "lab_accession_number": f"{_digits(rng, 2)}-{_digits(rng, 6)}",
            "mrn": _digits(rng, 7),
        },
        result=_results(
            positive="POSITIVE: {printed_class} CNV Detected",
            negative="NEGATIVE: No Clinically Significant CNVs Detected",
            uncertain="UNCERTAIN: CNV of Uncertain Significance Detected",
        ),
        classification={
            "pathogenic": "Pathogenic",
            "likely_pathogenic": "Likely Pathogenic",
            "uncertain_significance": "Uncertain Significance",
            "likely_benign": "Likely Benign",
            "benign": "Benign",
        },
        zygosity=_TITLE_ZYGOSITY,
        inheritance=_TITLE_INHERITANCE,
        position="chr{chromosome}:{start}-{stop}",
        prints_started=True,
        array=ArrayStyle(
            name="SNP Microarray",
            build="GRCh38",
            notation="arr[GRCh38] {band}({start}_{stop})x{copy_number}",
            normal={
                "Female": "arr[GRCh38](1-22,X)x2",
                "Male": "arr[GRCh38](1-22)x2,(XY)x1",
            },
            change_words=("LOSS", "GAIN"),
        ),
    ),
    Lab(
        key="carrier-grid",
        name="Indigo Genetic Testing",
        based_on=("SR006",),
        kinds=("carrier",),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "lab_accession_number": f"{_letters(rng, 2)}{_digits(rng, 7)}",
            "mrn": _digits(rng, 8),
        },
        result=_results(positive="POSITIVE", negative="NEGATIVE", uncertain="NEGATIVE"),
        classification={k: v.upper() for k, v in SENTENCE_CLASSES.items()},
        zygosity=_LOWER_ZYGOSITY,
        inheritance=_TITLE_INHERITANCE,
        carrier_name="Comprehensive Carrier Screen",
        results_to_note=True,
        held_out=True,
    ),
    Lab(
        key="chart",
        name="Apricot Reference Laboratories",
        based_on=("ARU01", "ARU02"),
        kinds=("targeted",),
        date_format="m/d/yyyy",
        ids=lambda rng: {
            "lab_accession_number": (
                f"{_digits(rng, 2)}-{rng.randint(1, 365):03d}-{_digits(rng, 6)}"
            ),
            "mrn": _digits(rng, 11),
        },
        result=_results(
            positive="{Zygosity}", negative="Negative", uncertain="See Note"
        ),
        classification=SENTENCE_CLASSES,
        zygosity=_TITLE_ZYGOSITY,
        inheritance=_TITLE_INHERITANCE,
    ),
    Lab(
        key="lis-printout",
        name="Apricot Reference Laboratories",
        based_on=("SR018",),
        kinds=("single_gene", "targeted"),
        date_format="dd-mon-yy hh:mm",
        ids=lambda rng: {
            "lab_accession_number": (
                f"{_digits(rng, 2)}-{rng.randint(1, 365):03d}-{_digits(rng, 6)}"
            ),
        },
        result=_results(positive="See Note", negative="See Note", uncertain="See Note"),
        classification=SENTENCE_CLASSES,
        zygosity=_LOWER_ZYGOSITY,
        inheritance=_LOWER_INHERITANCE,
        missing=("date_of_birth", "mrn", "submitter_patient_id"),
        held_out=True,
    ),
    Lab(
        key="microarray-printout",
        name="Lilac Molecular Laboratory",
        based_on=("LAB07",),
        kinds=("array",),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "lab_accession_number": (
                f"{_digits(rng, 3)}-{_digits(rng, 3)}-{_digits(rng, 4)}-"
                f"{_digits(rng, 1)}"
            ),
            "mrn": f"{_letters(rng, 2)}{_digits(rng, 2)}-{_digits(rng, 5)}",
        },
        result=_results(
            positive="{SIZE} {CHANGE} OF {BAND}",
            negative="NORMAL {SEX} MICROARRAY",
            uncertain="{SIZE} {CHANGE} OF {BAND}",
        ),
        classification={k: v.upper() for k, v in SENTENCE_CLASSES.items()},
        zygosity=_TITLE_ZYGOSITY,
        inheritance=_TITLE_INHERITANCE,
        array=ArrayStyle(
            name="Chromosomal Microarray, Pediatric",
            build="GRCh37",
            notation="arr[hg19]{band}({start:,}-{stop:,})x{copy_number}",
            normal={
                "Female": "arr[hg19](1-22,X)x2",
                "Male": "arr[hg19](1-22)x2,(XY)x1",
            },
        ),
    ),
    Lab(
        key="karyotype",
        name="Lilac Molecular Laboratory",
        based_on=("LAB02",),
        kinds=("karyotype",),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "lab_accession_number": _digits(rng, 8),
            "mrn": f"{_digits(rng, 8)}-{_digits(rng, 1)}",
        },
        result=_results(
            positive="Abnormal {sex} karyotype",
            negative="Normal {sex} karyotype",
            uncertain="Normal {sex} karyotype",
            carrier="Balanced translocation carrier karyotype, {sex}",
        ),
        classification=SENTENCE_CLASSES,
        zygosity=_TITLE_ZYGOSITY,
        inheritance=_TITLE_INHERITANCE,
        karyotype_name="Chromosome Analysis, Blood",
    ),
    Lab(
        key="summary-line",
        name="Plum Genetics",
        based_on=tuple(f"PVG{n:02d}" for n in range(2, 15)),
        kinds=("panel", "single_gene", "array", "repeat", "methylation"),
        date_format="month d, yyyy",
        ids=lambda rng: {
            "lab_accession_number": (
                f"{_digits(rng, 4)}-{_digits(rng, 3)}-{_digits(rng, 3)}"
            ),
            "mrn": f"{_digits(rng, 5)}{_letters(rng, 5)}",
        },
        result=_results(
            positive="Positive", negative="Negative", uncertain="Uncertain"
        ),
        classification={
            "pathogenic": "PATHOGENIC",
            "likely_pathogenic": "LIKELY PATHOGENIC",
            "uncertain_significance": "UNCERTAIN",
            "likely_benign": "LIKELY BENIGN",
            "benign": "BENIGN",
        },
        zygosity=_TITLE_ZYGOSITY,
        inheritance=_ABBREVIATED_INHERITANCE,
        build="GRCh37",
        kind_results={
            "array": _results(
                positive="{Zygosity} for an {size} {change} ({printed_class})",
                negative="NEGATIVE - {Sex} Profile",
                uncertain="{Zygosity} for an {size} {change} ({printed_class})",
            ),
            "repeat": _results(
                positive="{summary}", negative="Negative", uncertain="Negative"
            ),
            "methylation": _results(
                positive="Positive for {syndrome}",
                negative="Negative",
                uncertain="Negative",
            ),
        },
        array=ArrayStyle(
            name="CMA-ISCA via aCGH and SNP Test",
            build="GRCh37",
            notation="arr[GRCh37] {band}({start}_{stop})x{copy_number}",
            normal={"Female": "arr(X,1-22)x2", "Male": "arr(X,Y)x1,(1-22)x2"},
            change_words=("Deletion", "Duplication"),
            zygosity=True,
        ),
        repeat_genes=("HTT", "C9orf72"),
        indeterminate=True,
        clinvar_ids=True,
    ),
    Lab(
        key="summary-sidebar",
        name="Plum Genetics",
        based_on=("PVG01",),
        kinds=("exome",),
        date_format="month d, yyyy",
        ids=lambda rng: {
            "lab_accession_number": (
                f"{_digits(rng, 4)}-{_digits(rng, 3)}-{_digits(rng, 3)}"
            ),
            "mrn": f"{_digits(rng, 5)}{_letters(rng, 5)}",
        },
        result=_results(
            positive="POSITIVE RESULT",
            negative="NEGATIVE RESULT",
            uncertain="UNCERTAIN RESULT",
        ),
        classification={
            "pathogenic": "PATHOGENIC",
            "likely_pathogenic": "LIKELY PATHOGENIC",
            "uncertain_significance": "UNCERTAIN SIGNIFICANCE",
            "likely_benign": "LIKELY BENIGN",
            "benign": "BENIGN",
        },
        zygosity=_TITLE_ZYGOSITY,
        inheritance=_LOWER_INHERITANCE,
        exome_name=(
            "Whole Exome Test, Proband Only",
            "Whole Exome Test, Trio Analysis (Proband and Parents)",
        ),
        trio=True,
        build="GRCh37",
    ),
    Lab(
        key="patient-page",
        name="Navy Genomic Laboratory",
        based_on=("NHS01",),
        kinds=("carrier",),
        date_format="d month yyyy",
        ids=lambda rng: {
            "lab_accession_number": f"FG{_digits(rng, 2)}-{_digits(rng, 5)}",
            "mrn": f"999 {_digits(rng, 3)} {_digits(rng, 4)}",
        },
        result=_results(
            positive="Carrier of {condition}",
            negative="Not a carrier of {condition}",
            uncertain="Not a carrier of {condition}",
        ),
        classification={
            "pathogenic": "Pathogenic",
            "likely_pathogenic": "Likely pathogenic",
            "uncertain_significance": "Uncertain significance",
            "likely_benign": "Likely benign",
            "benign": "Benign",
        },
        zygosity=_TITLE_ZYGOSITY,
        inheritance=_TITLE_INHERITANCE,
        carrier_name="Cystic Fibrosis Carrier Test",
        position="Chr{chromosome}(GRCh38):g.{start}_{stop}",
        build="GRCh38",
        carrier_genes=("CFTR",),
    ),
    Lab(
        key="one-page",
        name="Navy Genomic Laboratory",
        based_on=("NHS01",),
        kinds=("carrier", "single_gene"),
        date_format="d mon yyyy",
        ids=lambda rng: {
            "lab_accession_number": f"NG{_digits(rng, 2)}-{_digits(rng, 4)}",
            "mrn": f"999 {_digits(rng, 3)} {_digits(rng, 4)}",
        },
        result=_results(
            positive=(
                "This patient is {zygosity} for a {classification} mutation in"
                " {gene}, {hgvs}."
            ),
            negative="No mutation was detected in the gene tested.",
            uncertain=(
                "This patient is {zygosity} for a {gene} variant of uncertain"
                " significance, {hgvs}."
            ),
        ),
        kind_results={
            "carrier": _results(
                positive=(
                    "This patient is {zygosity} for a {classification} mutation"
                    " in {gene}, {hgvs}, and is therefore a carrier of {condition}."
                ),
                negative=(
                    "No mutation was detected. This patient's risk of being a"
                    " carrier of {condition} is reduced."
                ),
                uncertain=(
                    "This patient is {zygosity} for a {gene} variant of"
                    " uncertain significance, {hgvs}."
                ),
            )
        },
        classification={
            "pathogenic": "pathogenic",
            "likely_pathogenic": "likely pathogenic",
            "uncertain_significance": "uncertain significance",
            "likely_benign": "likely benign",
            "benign": "benign",
        },
        zygosity={
            "heterozygous": "heterozygote",
            "homozygous": "homozygote",
            "hemizygous": "hemizygote",
            "heteroplasmic": "heteroplasmic",
            "homoplasmic": "homoplasmic",
        },
        inheritance=_TITLE_INHERITANCE,
        carrier_name="Cystic Fibrosis Mutation Screen",
        protein_style="parentheses",
        carrier_genes=("CFTR",),
    ),
]


@dataclasses.dataclass(frozen=True)
class Area:
    """A clinical area, with the genes its panel tests.

    Attributes:
        name: The name, as used in panel names.
        genes: The genes of the panel, in panel order.
        age: The patient's age range in years.
        indication: Reasons for testing.
    """

    name: str
    genes: tuple[str, ...]
    age: tuple[int, int]
    indication: tuple[str, ...]


AREAS = [
    Area(
        "Epilepsy",
        (
            "SCN1A",
            "SCN2A",
            "SCN8A",
            "KCNQ2",
            "STXBP1",
            "CDKL5",
            "PCDH19",
            "SLC2A1",
            "TSC1",
            "TSC2",
            "GRIN2A",
            "CHD2",
            "SYNGAP1",
            "DEPDC5",
            "KCNT1",
        ),
        (0, 14),
        ("Diagnostic evaluation for epilepsy", "Early-onset seizures"),
    ),
    Area(
        "Cardiomyopathy",
        (
            "MYH7",
            "MYBPC3",
            "TNNT2",
            "TNNI3",
            "TPM1",
            "ACTC1",
            "LMNA",
            "DSP",
            "PKP2",
            "FLNC",
            "RBM20",
            "MYL2",
            "MYL3",
        ),
        (18, 65),
        (
            "Diagnostic evaluation for cardiomyopathy",
            "Family history of cardiomyopathy",
        ),
    ),
    Area(
        "Arrhythmia",
        ("KCNQ1", "KCNH2", "SCN5A", "RYR2", "CASQ2", "KCNE1", "KCNJ2", "CALM1"),
        (8, 55),
        (
            "Diagnostic evaluation for an inherited arrhythmia",
            "Syncope and abnormal ECG",
        ),
    ),
    Area(
        "Hereditary Cancer",
        (
            "BRCA1",
            "BRCA2",
            "PALB2",
            "ATM",
            "CHEK2",
            "TP53",
            "PTEN",
            "MLH1",
            "MSH2",
            "MSH6",
            "PMS2",
            "APC",
            "MUTYH",
            "CDH1",
            "STK11",
        ),
        (28, 72),
        ("Personal history of cancer", "Family history of cancer"),
    ),
    Area(
        "Hearing Loss",
        (
            "GJB2",
            "SLC26A4",
            "MYO7A",
            "OTOF",
            "TMC1",
            "CDH23",
            "USH2A",
            "TECTA",
            "MYO15A",
        ),
        (0, 30),
        ("Diagnostic evaluation for hearing loss", "Congenital hearing loss"),
    ),
    Area(
        "Neuromuscular",
        ("DMD", "CAPN3", "DYSF", "SGCA", "FKRP", "ANO5", "COL6A1", "RYR1"),
        (2, 45),
        ("Diagnostic evaluation for muscle weakness", "Elevated creatine kinase"),
    ),
    Area(
        "Noonan Spectrum",
        (
            "PTPN11",
            "SOS1",
            "RAF1",
            "RIT1",
            "KRAS",
            "BRAF",
            "MAP2K1",
            "SHOC2",
            "CBL",
            "NRAS",
            "LZTR1",
        ),
        (0, 12),
        (
            "Diagnostic evaluation for a suspected RASopathy",
            "Short stature and congenital heart disease",
        ),
    ),
    Area(
        "Aortopathy",
        ("FBN1", "TGFBR1", "TGFBR2", "SMAD3", "ACTA2", "COL3A1", "MYH11"),
        (12, 60),
        ("Thoracic aortic aneurysm", "Diagnostic evaluation for Marfan syndrome"),
    ),
    Area(
        "Neurodevelopmental",
        (
            "MECP2",
            "ARID1B",
            "ADNP",
            "DDX3X",
            "KMT2D",
            "CHD8",
            "SHANK3",
            "ANKRD11",
            "FOXP1",
            "SYNGAP1",
        ),
        (1, 12),
        (
            "Global developmental delay",
            "Developmental delay and intellectual disability",
        ),
    ),
]

CARRIER_GENES = (
    "CFTR",
    "HEXA",
    "GBA1",
    "ASPA",
    "FANCC",
    "BLM",
    "PAH",
    "HBB",
    "GJB2",
    "MUTYH",
)
MITO_GENES = ("MT-TL1", "MT-ND4", "MT-ATP6", "MT-ND1", "MT-TK", "MT-ND5")
# Genes of the ACMG secondary-findings list, for secondary findings.
SECONDARY_GENES = (
    "BRCA1",
    "BRCA2",
    "MLH1",
    "MSH2",
    "MYH7",
    "MYBPC3",
    "KCNQ1",
    "KCNH2",
    "FBN1",
    "LDLR",
    "TP53",
    "RYR1",
)

SPECIMENS = [
    ("Whole blood (EDTA)", "whole_blood"),
    ("Peripheral blood, EDTA", "whole_blood"),
    ("Blood", "whole_blood"),
    ("Saliva", "saliva"),
    ("Saliva (Oragene)", "saliva"),
    ("Buccal swab", "buccal_swab"),
    ("Cheek swab", "buccal_swab"),
]
# Specimens of a chromosome analysis, which needs living blood cells.
KARYOTYPE_SPECIMENS = [
    ("Peripheral blood, sodium heparin", "whole_blood"),
    ("Peripheral Blood", "whole_blood"),
    ("Whole blood (sodium heparin)", "whole_blood"),
]
AMBIGUOUS_SPECIMENS = [
    ("Saliva/Buccal", None),
    ("Extracted DNA from outside laboratory", None),
]

FIRST_NAMES = {
    "Female": (
        "Avery",
        "Mara",
        "Lena",
        "Priya",
        "Sofia",
        "Hana",
        "Talia",
        "Ines",
        "Noor",
        "Clara",
        "Joanna",
        "Rosa",
        "Imani",
        "Keira",
    ),
    "Male": (
        "Mateo",
        "Elias",
        "Rowan",
        "Darius",
        "Kenji",
        "Omar",
        "Felix",
        "Jonah",
        "Tobias",
        "Arjun",
        "Malik",
        "Silas",
        "Andre",
        "Luca",
    ),
}
LAST_NAMES = (
    "Brandt",
    "Okafor",
    "Lindqvist",
    "Ferreira",
    "Nakamura",
    "Haddad",
    "Kowalczyk",
    "Delgado",
    "Achterberg",
    "Moreau",
    "Ivanova",
    "Castellano",
    "Whitlock",
    "Szabo",
    "Raman",
    "Oyelaran",
    "Petrov",
    "Quintero",
    "Holloway",
    "Marchetti",
)
