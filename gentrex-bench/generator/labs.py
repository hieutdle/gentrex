"""The fictional laboratories, clinical areas and wording of the synthetic reports.

Every name and layout here is invented. A lab fixes how a report looks and how
it words each value, so that the same truth reads differently from lab to lab.
Labs with `held_out` set appear only in the test split.
"""

import dataclasses
import datetime
import random
from collections.abc import Callable


def _digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789") for _ in range(n))


def _letters(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(n))


DATE_FORMATS: dict[str, Callable[[datetime.date], str]] = {
    "m/d/yyyy": lambda d: f"{d.month}/{d.day}/{d.year}",
    "mm/dd/yyyy": lambda d: d.strftime("%m/%d/%Y"),
    "dd-mon-yyyy": lambda d: d.strftime("%d-%b-%Y").upper(),
    "month d, yyyy": lambda d: f"{d.strftime('%B')} {d.day}, {d.year}",
    "yyyy-mm-dd": lambda d: d.isoformat(),
}

# Formats for the unusual_date_format tag, which `gentrex normalize` doesn't
# read, so the truth's ISO dates test whether it says so.
UNUSUAL_DATE_FORMATS: dict[str, Callable[[datetime.date], str]] = {
    "yyyy/mm/dd": lambda d: d.strftime("%Y/%m/%d"),
    "d.m.yyyy": lambda d: f"{d.day}.{d.month}.{d.year}",
    "mon d yyyy": lambda d: f"{d.strftime('%b')} {d.day} {d.year}",
}


@dataclasses.dataclass(frozen=True)
class Lab:
    """A fictional laboratory.

    Attributes:
        key: Short name, used in the case files.
        name: The name printed in the letterhead.
        layout: How the report looks, written for the model that writes it.
        date_format: Key of DATE_FORMATS.
        ids: Makes the MRN, submitter ID and accession number; a field the
            lab doesn't print is missing from the result.
        result: The headline result wording for each result scenario.
        classification: The wording of each classification.
        zygosity: The wording of each zygosity.
        inheritance: The wording of each mode of inheritance.
        panel_name: The name of a panel test, from the clinical area's name.
        exome_name: The names of the proband and trio exome tests.
        protein_parentheses: Whether protein changes print as p.(Arg412Trp).
        prints_sex: Whether the header has a sex field.
        held_out: Whether the lab is kept out of the dev split.
    """

    key: str
    name: str
    layout: str
    date_format: str
    ids: Callable[[random.Random], dict[str, str]]
    result: dict[str, str]
    classification: dict[str, str]
    zygosity: dict[str, str]
    inheritance: dict[str, str]
    panel_name: Callable[[str], str]
    exome_name: tuple[str, str]
    protein_parentheses: bool
    prints_sex: bool
    held_out: bool = False


_FIVE_TIER = {
    "pathogenic": "Pathogenic",
    "likely_pathogenic": "Likely Pathogenic",
    "uncertain_significance": "Uncertain Significance",
    "likely_benign": "Likely Benign",
    "benign": "Benign",
}
_ZYGOSITY = {
    "heterozygous": "Heterozygous",
    "homozygous": "Homozygous",
    "hemizygous": "Hemizygous",
    "heteroplasmic": "Heteroplasmic",
    "homoplasmic": "Homoplasmic",
}
_INHERITANCE = {
    "autosomal_dominant": "Autosomal dominant",
    "autosomal_recessive": "Autosomal recessive",
    "x_linked": "X-linked",
    "x_linked_dominant": "X-linked dominant",
    "x_linked_recessive": "X-linked recessive",
    "mitochondrial": "Mitochondrial",
}

LABS = [
    Lab(
        key="A",
        name="Harborline Genetics",
        layout=(
            "Compact results report. Header fields: Patient Name, DOB, Sex, "
            "Accession #, Submitter/Patient ID, Source, Date Collected, Date "
            "Received, Test Started, Date Reported, Test(s) Requested, Provider, "
            "Indication. The patient's features form one full-width line "
            "starting 'Features include:'. A line 'RESULT:' with the result "
            "wording. A borderless variant table: Gene | Mode of Inheritance | "
            "Variant | Zygosity | Classification, where the Variant cell reads "
            "'c.1234C>T (p.Arg412Trp)'. Then Interpretation, Recommendations, "
            "Methods, Limitations, References. The result page ends with "
            "'Report electronically signed by', a name, credentials and date. "
            "Pages 2 and later carry a running header with name, DOB and "
            "accession."
        ),
        date_format="m/d/yyyy",
        ids=lambda rng: {
            "lab_accession_number": _digits(rng, 7),
            "submitter_patient_id": _letters(rng, 1) + _digits(rng, 6),
        },
        result={
            "positive": "Positive",
            "negative": "Negative",
            "vus_only": "Uncertain",
            "mixed": "Positive",
            "carrier": "Positive - Carrier",
            "secondary_finding": "Negative",
        },
        classification=_FIVE_TIER,
        zygosity=_ZYGOSITY,
        inheritance=_INHERITANCE,
        panel_name=lambda area: f"{area} Panel",
        exome_name=("Exome Sequencing", "Exome Sequencing - Trio"),
        protein_parentheses=False,
        prints_sex=True,
    ),
    Lab(
        key="B",
        name="Wrenfield Genomics",
        layout=(
            "Banner report with variant details. Header fields: Patient name, "
            "DOB, Sex assigned at birth, Patient ID (MRN), Sample type, Sample "
            "collection date, Sample accession date (the received date), Report "
            "date, Lab #, Clinical team. 'Reason for testing' and 'Test "
            "performed' follow, then 'Clinical history' with the patient's "
            "features. A shaded RESULT banner with the result wording and a "
            "one-sentence summary. Variant table: GENE | VARIANT | ZYGOSITY | "
            "VARIANT CLASSIFICATION, with the c. change on one line and the p. "
            "change on the next. Later: clinical summary, next steps, 'Variant "
            "details' with one block per variant (gene, transcript, HGVS, "
            "zygosity, classification, an evidence paragraph), 'Genes analyzed', "
            "Methods, Limitations, Resources. Every page has a running header "
            "with name, DOB and Lab #, and a footer naming the lab director."
        ),
        date_format="dd-mon-yyyy",
        ids=lambda rng: {
            "mrn": _digits(rng, 8),
            "lab_accession_number": _letters(rng, 2) + _digits(rng, 7),
        },
        result={
            "positive": "POSITIVE",
            "negative": "NEGATIVE",
            "vus_only": "UNCERTAIN",
            "mixed": "POSITIVE",
            "carrier": "CARRIER",
            "secondary_finding": "NEGATIVE",
        },
        classification=_FIVE_TIER,
        zygosity=_ZYGOSITY,
        inheritance=_INHERITANCE,
        panel_name=lambda area: f"Comprehensive {area} Panel",
        exome_name=(
            "Proband Exome Sequencing",
            "Trio Exome Sequencing (Proband, Mother, Father)",
        ),
        protein_parentheses=True,
        prints_sex=True,
    ),
    Lab(
        key="C",
        name="Calder Ridge Molecular",
        layout=(
            "Detailed variant table. Header grid: Patient Legal Name, Birthdate, "
            "Sex assigned at birth, MRN #, Accession #, Specimen #, Specimen, "
            "Collected, Received, Test Started, Indication, Medical "
            "Professional, Client. The test name is the report title. A result "
            "banner with the result wording. Variant table: Gene (RefSeq ID) | "
            "Associated Phenotype (Inheritance) | Genotype | Variant | "
            "Classification | Category, where Category is Primary or Secondary "
            "Finding. Then Results, Interpretation, Genetic Counseling "
            "Recommendations, Test Description, Analytical Range, Limitations "
            "and a signature block. The patient's features are a short "
            "'Clinical Information' paragraph."
        ),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "mrn": _digits(rng, 7),
            "lab_accession_number": f"{_digits(rng, 2)}-{_digits(rng, 6)}",
        },
        result={
            "positive": "POSITIVE: Pathogenic Variant Detected",
            "negative": "NEGATIVE: No Clinically Significant Variants Identified",
            "vus_only": "VARIANT OF UNCERTAIN SIGNIFICANCE DETECTED",
            "mixed": "POSITIVE: Reportable Variants Detected",
            "carrier": "CARRIER: One Pathogenic Variant Detected",
            "secondary_finding": "NEGATIVE: No Clinically Significant Variants "
            "Identified",
        },
        classification={
            "pathogenic": "Pathogenic (Class 5)",
            "likely_pathogenic": "Likely Pathogenic (Class 4)",
            "uncertain_significance": "Uncertain Significance (Class 3)",
            "likely_benign": "Likely Benign (Class 2)",
            "benign": "Benign (Class 1)",
        },
        zygosity=_ZYGOSITY,
        inheritance={
            "autosomal_dominant": "AD",
            "autosomal_recessive": "AR",
            "x_linked": "XL",
            "x_linked_dominant": "XLD",
            "x_linked_recessive": "XLR",
            "mitochondrial": "Mito",
        },
        panel_name=lambda area: f"{area} Sequencing and Deletion/Duplication Panel",
        exome_name=("Proband Exome with Secondary Findings", "Trio Exome Analysis"),
        protein_parentheses=False,
        prints_sex=True,
    ),
    Lab(
        key="D",
        name="Bellmont Diagnostic Laboratory",
        layout=(
            "Short letter. Header fields: Patient Name, Date of Birth, "
            "Submitter's ID No, Accession No, Specimen Type, Ordered By, Date "
            "Specimen Obtained, Date Received, Date Test(s) Started, Date of "
            "Report. A 'Relevant Information' paragraph gives the clinical "
            "history from the ordering clinician, with the patient's features. "
            "A result sentence that starts with the result wording, then a "
            "small table: Gene | Variant | Zygosity | Classification (for "
            "mitochondrial variants: Gene | mtDNA Variant | Heteroplasmy | "
            "Classification). Then Interpretation, Recommendation, short "
            "methods and a signature. No sex field; the narrative may still "
            "use pronouns only if the sex is given below."
        ),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "lab_accession_number": _digits(rng, 7),
            "submitter_patient_id": _letters(rng, 3) + _digits(rng, 5),
        },
        result={
            "positive": "Positive.",
            "negative": "Negative.",
            "vus_only": "Uncertain.",
            "mixed": "Positive.",
            "carrier": "Carrier.",
            "secondary_finding": "Negative.",
        },
        classification=_FIVE_TIER,
        zygosity=_ZYGOSITY,
        inheritance=_INHERITANCE,
        panel_name=lambda area: f"{area} Gene Panel",
        exome_name=("Clinical Exome", "Clinical Exome (Trio)"),
        protein_parentheses=False,
        prints_sex=False,
    ),
    Lab(
        key="E",
        name="Molecular Diagnostics Laboratory, Eastvale University Medical Center",
        layout=(
            "Academic hospital laboratory. Letterhead 'Molecular Diagnostics "
            "Laboratory', a department and the university medical center. "
            "Header table: Name, MRN, DOB, Gender, Accession #, Specimen Type, "
            "Date Collected, Date Received, Date Reported, Ordering Physician, "
            "Test Description, Referral Reason. A 'Result:' line with the "
            "result wording. Prose sections: Result Details (with the HGVS), "
            "Clinical Significance, Recommendations, Methodology, Limitations. "
            "The patient's features are in 'Clinical History'. An attending's "
            "signature with 'Date Signed' closes the report."
        ),
        date_format="month d, yyyy",
        ids=lambda rng: {
            "mrn": _digits(rng, 8),
            "lab_accession_number": f"{_letters(rng, 2)}{_digits(rng, 2)}-"
            f"{_digits(rng, 5)}",
        },
        result={
            "positive": "ABNORMAL",
            "negative": "NORMAL",
            "vus_only": "Abnormal - variant of uncertain significance detected",
            "mixed": "ABNORMAL",
            "carrier": "Abnormal - heterozygous carrier",
            "secondary_finding": "NORMAL",
        },
        classification={
            "pathogenic": "Pathogenic",
            "likely_pathogenic": "Likely pathogenic",
            "uncertain_significance": "Variant of uncertain significance",
            "likely_benign": "Likely benign",
            "benign": "Benign",
        },
        zygosity={k: v.lower() for k, v in _ZYGOSITY.items()},
        inheritance={k: v.lower() for k, v in _INHERITANCE.items()},
        panel_name=lambda area: f"{area} Multigene Panel",
        exome_name=("Clinical Exome Sequencing", "Clinical Trio Exome Sequencing"),
        protein_parentheses=True,
        prints_sex=True,
        held_out=True,
    ),
    Lab(
        key="F",
        name="Northgate Clinical Genomics",
        layout=(
            "Two-column summary page. A narrow left sidebar holds the patient "
            "and specimen fields as label-over-value pairs: Patient, Date of "
            "Birth, Sex, MRN, Order ID (the accession number), Specimen, "
            "Collected, Received, Reported. The wide right column has the test "
            "name as a heading, 'Indication for testing', a colored result box "
            "with the result wording, and a findings table: Gene | Transcript | "
            "Nucleotide | Protein | Zygosity | Inheritance | Classification, "
            "with the c. and p. changes in their own columns. The patient's "
            "features are in 'Clinical notes provided'. Later pages: "
            "Interpretation per finding, Recommendations, Methods, Genes "
            "Tested, Limitations, Glossary."
        ),
        date_format="mm/dd/yyyy",
        ids=lambda rng: {
            "mrn": _letters(rng, 1) + _digits(rng, 6),
            "lab_accession_number": f"NG-{_digits(rng, 8)}",
        },
        result={
            "positive": "Positive result",
            "negative": "Negative result",
            "vus_only": "Uncertain result",
            "mixed": "Positive result",
            "carrier": "Carrier result",
            "secondary_finding": "Negative result",
        },
        classification=_FIVE_TIER,
        zygosity=_ZYGOSITY,
        inheritance=_INHERITANCE,
        panel_name=lambda area: f"{area} Panel (Sequencing and CNV)",
        exome_name=("Exome Sequencing, Proband", "Exome Sequencing, Trio"),
        protein_parentheses=True,
        prints_sex=True,
    ),
    Lab(
        key="G",
        name="Keystone Reference Laboratories",
        layout=(
            "Reference-lab report with numbered sections. A requisition-style "
            "header block in two columns: PATIENT, DOB, SEX, MRN, ACCESSION, "
            "SPECIMEN TYPE, COLLECTION DATE, RECEIVED DATE, REPORT DATE, "
            "ORDERING PROVIDER, TEST. Sections '1. Result Summary' (the result "
            "wording on its own line in bold), '2. Findings' (a ruled table: "
            "Gene | DNA Change | Protein Change | Zygosity | Classification | "
            "Condition), '3. Clinical Information' (the indication and the "
            "patient's features), '4. Interpretation', '5. Recommendations', "
            "'6. Methodology', '7. Limitations', '8. References'. A sign-off "
            "line with two reviewers."
        ),
        date_format="yyyy-mm-dd",
        ids=lambda rng: {
            "mrn": _digits(rng, 9),
            "lab_accession_number": f"K{_digits(rng, 9)}",
        },
        result={
            "positive": "POSITIVE - clinically significant variant identified",
            "negative": "NEGATIVE - no clinically significant variant identified",
            "vus_only": "UNCERTAIN - variant of uncertain significance identified",
            "mixed": "POSITIVE - clinically significant variant identified",
            "carrier": "CARRIER - one pathogenic variant identified",
            "secondary_finding": "NEGATIVE - no clinically significant variant "
            "identified",
        },
        classification={
            "pathogenic": "PATHOGENIC",
            "likely_pathogenic": "LIKELY PATHOGENIC",
            "uncertain_significance": "VUS",
            "likely_benign": "LIKELY BENIGN",
            "benign": "BENIGN",
        },
        zygosity={k: v.upper() for k, v in _ZYGOSITY.items()},
        inheritance=_INHERITANCE,
        panel_name=lambda area: f"{area} NGS Panel",
        exome_name=("Whole Exome Sequencing", "Whole Exome Sequencing, Trio"),
        protein_parentheses=False,
        prints_sex=True,
    ),
    Lab(
        key="H",
        name="Genomics Service, Riverbend Children's Hospital",
        layout=(
            "Children's hospital genomics letter addressed to the referring "
            "clinician. Letterhead with the service name and hospital. An "
            "opening block: Re:, DOB, Hospital No. (the MRN), Lab ref (the "
            "accession number), Sample, Sample taken, Sample received, Report "
            "issued. 'Dear Dr ...' then a paragraph on why the test was done, "
            "naming the test and the patient's features. A boxed 'Summary of "
            "result' with the result wording, then the findings as prose and a "
            "small table: Gene | Variant | Zygosity | Inheritance | ACMG "
            "class. Then Interpretation, Implications for the family, Next "
            "steps, Technical details, and a signature from a clinical "
            "scientist."
        ),
        date_format="month d, yyyy",
        ids=lambda rng: {
            "mrn": _digits(rng, 6),
            "lab_accession_number": f"RCH{_digits(rng, 2)}-{_digits(rng, 4)}",
        },
        result={
            "positive": "Diagnostic result",
            "negative": "No diagnostic variant found",
            "vus_only": "Variant of uncertain significance found",
            "mixed": "Diagnostic result",
            "carrier": "Carrier result",
            "secondary_finding": "No diagnostic variant found",
        },
        classification={
            "pathogenic": "Pathogenic",
            "likely_pathogenic": "Likely pathogenic",
            "uncertain_significance": "VUS",
            "likely_benign": "Likely benign",
            "benign": "Benign",
        },
        zygosity=_ZYGOSITY,
        inheritance=_INHERITANCE,
        panel_name=lambda area: f"{area} Gene Panel",
        exome_name=("Exome Analysis (Singleton)", "Exome Analysis (Trio)"),
        protein_parentheses=True,
        prints_sex=False,
        held_out=True,
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
