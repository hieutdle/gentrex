import gzip
import json
import pathlib

import numpy as np
import pytest

from gentrex import records
from gentrex.normalize import diseases
from gentrex.normalize import genes
from gentrex.normalize import phenotypes
from gentrex.normalize import rules
from gentrex.normalize import run
from gentrex.normalize import variants

_WORDS = ("seizure", "epileptic", "hypotonia", "ataxia")

_OBO = "http://purl.obolibrary.org/obo/"


class _WordEncoder:
    """Embeds a text as the words of _WORDS it contains, each with a weight."""

    def __init__(self, **weights: float) -> None:
        self._weights = [weights.get(word, 1.0) for word in _WORDS]

    def encode(self, texts: list[str], prompt_name: str | None = None) -> np.ndarray:
        weights = list(zip(_WORDS, self._weights, strict=True))
        return np.array([[w * (word in t) for word, w in weights] for t in texts])


# Models by name: "seizure-first" and "hypotonia-first" disagree on a text
# that names both.
_ENCODERS = {
    "words": _WordEncoder(),
    "seizure-first": _WordEncoder(seizure=2.0),
    "hypotonia-first": _WordEncoder(hypotonia=2.0),
}


def _write_release(tmp_path: pathlib.Path) -> pathlib.Path:
    """Writes three HPO terms, a deprecated one and another ontology's class."""
    nodes = [
        {
            "id": f"{_OBO}HP_0001250",
            "type": "CLASS",
            "lbl": "Seizure",
            "meta": {"synonyms": [{"val": "Epileptic seizure"}]},
        },
        {"id": f"{_OBO}HP_0001252", "type": "CLASS", "lbl": "Hypotonia"},
        {"id": f"{_OBO}HP_0001251", "type": "CLASS", "lbl": "Ataxia"},
        {
            "id": f"{_OBO}HP_9999999",
            "type": "CLASS",
            "lbl": "Obsolete seizure",
            "meta": {"deprecated": True},
        },
        {"id": f"{_OBO}UPHENO_9999999", "type": "CLASS", "lbl": "Seizure"},
    ]
    path = tmp_path / "hp-base.json"
    path.write_text(json.dumps({"graphs": [{"nodes": nodes}]}))
    return path


def _hpo_index(
    tmp_path: pathlib.Path, monkeypatch, top_k: int, names=("words",)
) -> phenotypes.HpoIndex:
    """Returns an index of _write_release's terms, embedded by _ENCODERS."""
    monkeypatch.setattr(phenotypes, "load_encoder", lambda model: _ENCODERS[model])
    models = [{"name": name} for name in names]
    phenotypes.build_index(_write_release(tmp_path), tmp_path / "hpo.npz", models)
    return phenotypes.HpoIndex(tmp_path / "hpo.npz", models, top_k)


def _mondo_index(tmp_path: pathlib.Path) -> diseases.MondoIndex:
    """Returns an index over two diseases, two that share a name and an obsolete one."""

    def disease(number: str, label: str, *synonyms: dict) -> dict:
        meta = {"synonyms": list(synonyms)}
        return {
            "id": f"{_OBO}MONDO_{number}",
            "type": "CLASS",
            "lbl": label,
            "meta": meta,
        }

    exact = {"pred": "hasExactSynonym"}
    abbreviation = {**exact, "synonymType": f"{_OBO}mondo#ABBREVIATION"}
    nodes = [
        disease("0010726", "Rett syndrome", {**abbreviation, "val": "RTS"}),
        disease(
            "0003582",
            "hereditary breast ovarian cancer syndrome",
            {**exact, "val": "hereditary breast and ovarian cancer syndrome"},
            {"pred": "hasRelatedSynonym", "val": "breast cancer"},
        ),
        disease("9999991", "SYN disease one", {**exact, "val": "SYN shared name"}),
        disease("9999992", "SYN disease two", {**exact, "val": "SYN shared name"}),
        {**disease("9999993", "SYN obsolete disease"), "meta": {"deprecated": True}},
    ]
    meta = {"version": f"{_OBO}mondo/releases/2026-11-03/mondo-base.owl"}
    path = tmp_path / "mondo-base.json"
    path.write_text(json.dumps({"graphs": [{"meta": meta, "nodes": nodes}]}))
    return diseases.MondoIndex.from_release(path)


def _hgnc_index(tmp_path: pathlib.Path) -> genes.HgncIndex:
    """Returns an index over two genes and a previous symbol they share."""
    path = tmp_path / "hgnc.txt"
    path.write_text(
        "hgnc_id\tsymbol\talias_symbol\tprev_symbol\n"
        "HGNC:1101\tBRCA2\tFAD|FANCD1\tSYN-OLD\n"
        "HGNC:6990\tMECP2\tRTT\tSYN-OLD\n"
    )
    return genes.HgncIndex.from_tsv(path)


@pytest.mark.parametrize(
    ("wording", "category"),
    [
        ("POSITIVE: One pathogenic variant and one VUS were identified.", "positive"),
        ("UNCERTAIN: A variant of uncertain significance was identified.", "uncertain"),
        ("NEGATIVE: No reportable variants were identified.", "negative"),
        ("No pathogenic variants were identified.", "negative"),
        ("No pathogenic or likely pathogenic variants were identified.", "negative"),
        ("This test did not identify any pathogenic variants.", "negative"),
        ("Not a carrier.", "negative"),
        (
            "CARRIER: One heterozygous pathogenic CFTR variant was identified.",
            "carrier",
        ),
        ("POSITIVE: CARRIER", "carrier"),
        ("POSITIVE: PREMUTATION CARRIER", "carrier"),
        ("PRIMARY RESULT: NEGATIVE. SECONDARY RESULT: POSITIVE.", "negative"),
        ("INCONCLUSIVE: Additional characterization is required.", "inconclusive"),
        ("SUMMARY OF RESULTS: Indeterminate", "inconclusive"),
        ("Normal male karyotype", "negative"),
        ("NORMAL MICROARRAY RESULT", "negative"),
        ("Normal SNP array", "negative"),
        ("Abnormal female karyotype", "positive"),
        ("ABNORMAL MICROARRAY RESULT", "positive"),
        ("No abnormal microarray findings were detected.", "negative"),
    ],
)
def test_result_follows_the_lab_wording(wording, category):
    """The first category the statement names decides, except that carrier
    outranks positive; secondary results don't."""
    result = rules.overall_result(wording, [])

    assert (result["overall_result"], result["overall_result_basis"]) == (
        category,
        "wording",
    )


def test_positive_carrier_screen_is_carrier():
    """A carrier screen's "POSITIVE" means that the patient is a carrier."""
    result = rules.overall_result("POSITIVE", [], "Expanded Carrier Panel")

    assert result["overall_result"] == "carrier"


def test_abnormal_counts_only_before_karyotype_or_array():
    """Read on its own, "abnormal" would make this negative statement positive."""
    result = rules.overall_result("No abnormal copy number changes were detected.", [])

    assert result["overall_result"] is None


def test_result_without_wording_comes_from_primary_findings():
    variants = [
        {"classification": "pathogenic", "is_secondary_finding": True},
        {"classification": "uncertain_significance", "is_secondary_finding": False},
    ]

    result = rules.overall_result(None, variants)

    assert (result["overall_result"], result["overall_result_basis"]) == (
        "uncertain",
        "variants",
    )


def test_wording_and_classifications_that_disagree_are_flagged():
    variants = [{"classification": "pathogenic", "is_secondary_finding": None}]

    result = rules.overall_result("NEGATIVE: No reportable variants.", variants)

    assert result["overall_result"] == "negative"
    assert result["overall_result_conflict"] is True


@pytest.mark.parametrize(
    ("printed", "iso"),
    [
        ("23-JAN-2020", "2020-01-23"),
        ("06/19/2001", "2001-06-19"),
        ("2026-08-27", "2026-08-27"),
        ("September 18, 2026", "2026-09-18"),
        ("18 March 1995", "1995-03-18"),
        ("18 Mar 1995", "1995-03-18"),
        ("8 March 1995", "1995-03-08"),
        ("19/06/2001", "2001-06-19"),
        ("29-Jul-25 08:27", "2025-07-29"),
        ("14-Mar-52", "1952-03-14"),
        ("27.08.2026", None),
        (None, None),
    ],
)
def test_dates_are_read_as_laboratories_print_them(printed, iso):
    """A date in an unknown format stays unread.

    19 can only be the day, a time of day is ignored, and a year of two
    digits is never in the future.
    """
    assert rules.parse_date(printed) == iso


def test_day_first_decides_only_dates_that_fit_both_ways():
    """A British report's 03/04/2020 is April 3, which the date alone can't show."""
    assert rules.parse_date("03/04/2020") == "2020-03-04"
    assert rules.parse_date("03/04/2020", day_first=True) == "2020-04-03"
    assert rules.parse_date("03/25/2020", day_first=True) == "2020-03-25"


@pytest.mark.parametrize(
    ("printed", "category"),
    [
        ("Blood in EDTA", "whole_blood"),
        ("Buccal swab", "buccal_swab"),
        ("Blood and saliva", None),
    ],
)
def test_specimen_gets_a_category_only_when_one_rule_matches(printed, category):
    assert rules.specimen_category(printed) == category


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("brca2", ("BRCA2", "HGNC:1101", "approved")),
        ("RTT", ("MECP2", "HGNC:6990", "alias")),
        ("SYN-OLD", (None, None, "ambiguous")),
        ("SYN-NONE", (None, None, "unmapped")),
        (None, (None, None, "missing")),
    ],
)
def test_gene_symbols_map_to_one_approved_symbol(tmp_path, printed, expected):
    """A symbol that several genes share is not resolved to any of them."""
    gene = _hgnc_index(tmp_path).normalize(printed)

    assert (gene["gene_symbol"], gene["hgnc_id"], gene["gene_status"]) == expected


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("RETT SYNDROME", ("MONDO:0010726", "Rett syndrome", "label")),
        (
            "Hereditary breast and ovarian cancer syndrome (HBOC)",
            ("MONDO:0003582", "hereditary breast ovarian cancer syndrome", "synonym"),
        ),
        ("RTS", (None, None, "unmapped")),
        ("Breast cancer", (None, None, "unmapped")),
        ("SYN shared name", (None, None, "ambiguous")),
        ("SYN obsolete disease", (None, None, "unmapped")),
        (None, (None, None, "missing")),
    ],
)
def test_disease_names_map_to_one_mondo_disease(tmp_path, printed, expected):
    """Only a label or exact synonym counts, and never an abbreviation."""
    disease = _mondo_index(tmp_path).normalize(printed)

    assert (
        disease["disease_id"],
        disease["disease_label"],
        disease["disease_status"],
    ) == expected


def test_mondo_index_knows_its_release(tmp_path):
    """`gentrex export phenopackets` names the release in the Phenopackets' metadata."""
    assert _mondo_index(tmp_path).version == "2026-11-03"


def test_phenotype_gets_the_closest_terms_once_each(tmp_path, monkeypatch):
    """Two names of one term must not take two of the top_k places."""
    term = _hpo_index(tmp_path, monkeypatch, top_k=2).map("Epileptic seizure")

    assert term["hpo_id"] == "HP:0001250"
    assert term["candidates"][0]["models"]["words"] == {
        "name": "Epileptic seizure",
        "similarity": 1.0,
    }
    assert len({c["hpo_id"] for c in term["candidates"]}) == 2


def test_only_current_hpo_terms_are_matched(tmp_path, monkeypatch):
    """A deprecated term or another ontology's class must never be a match."""
    term = _hpo_index(tmp_path, monkeypatch, top_k=5).map("Seizure")

    assert {c["hpo_id"] for c in term["candidates"]} == {
        "HP:0001250",
        "HP:0001252",
        "HP:0001251",
    }


def test_term_both_models_rate_well_beats_each_models_favorite():
    """Z-scores make the models' scales comparable, so agreement wins."""
    # Terms X, Y, Z and seven others. The first model prefers Y, the second Z,
    # and both rate X well above average, each on its own scale.
    first = np.array([0.80, 0.85, 0.40] + [0.40] * 7)
    second = np.array([0.975, 0.93, 0.98] + [0.93] * 7)

    assert np.argmax(phenotypes.fuse([first, second])) == 0


def test_match_says_when_the_models_disagree(tmp_path, monkeypatch):
    """Disagreement marks the matches that most need a check."""
    index = _hpo_index(
        tmp_path, monkeypatch, top_k=5, names=("seizure-first", "hypotonia-first")
    )

    term = index.map("Seizure and hypotonia")

    assert term["models_agree"] is False
    assert {c["hpo_id"] for c in term["candidates"][:2]} == {"HP:0001250", "HP:0001252"}


@pytest.mark.parametrize(
    "settings",
    [
        pytest.param([{"name": "hypotonia-first"}], id="other-model"),
        pytest.param([{"name": "words", "prompt": "STS"}], id="other-prompt"),
    ],
)
def test_index_built_another_way_is_refused(tmp_path, monkeypatch, settings):
    """Embeddings from different models or prompts can't be compared."""
    monkeypatch.setattr(phenotypes, "load_encoder", lambda model: _ENCODERS[model])
    path = tmp_path / "hpo.npz"
    phenotypes.build_index(_write_release(tmp_path), path, [{"name": "words"}])

    with pytest.raises(ValueError, match="built with words, but settings.yaml names"):
        phenotypes.HpoIndex(path, settings, top_k=1)


@pytest.mark.parametrize(
    ("change", "kind", "status"),
    [
        ("c.5266dupC", "c", "valid"),
        ("NM_007294.4:c.5266dup", "c", "valid"),
        ("c.(6438+1_6439-1)_(7309+1_7310-1)del", "c", "valid"),
        ("c.5266duplication", "c", "invalid"),
        ("m.3243A>G", "c", "invalid"),
        ("p.(Gln1756Profs*74)", "p", "valid"),
        ("p.R412W", "p", "valid"),
        ("p.Xyz412Trp", "p", "invalid"),
        (None, "c", "missing"),
    ],
)
def test_a_change_that_is_not_hgvs_is_marked_invalid(change, kind, status):
    """Older spellings that laboratories still print count as valid."""
    assert variants.hgvs_status(change, kind) == status


def _clinvar_index(tmp_path: pathlib.Path) -> variants.ClinvarIndex:
    """Writes ClinVar variants of three genes, each row for both genome builds."""
    names = {
        "17677": "NM_007294.4(BRCA1):c.5266dup (p.Gln1756fs)",
        "10381": "NM_000402.4(G6PD):c.1192G>A (p.Glu398Lys)",
        "804134": "NM_001360016.2(G6PD):c.1192G>A (p.Glu398Lys)",
        "9325": "NM_000059.4(BRCA2):c.5946del (p.Ser1982fs)",
    }
    rows = [f"1\t{name}\t{variation_id}\n" * 2 for variation_id, name in names.items()]
    path = tmp_path / "variant_summary.txt.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write("#AlleleID\tName\tVariationID\n" + "".join(rows))
    return variants.ClinvarIndex(path)


@pytest.mark.parametrize(
    ("transcript", "change", "expected"),
    [
        (None, "c.5266dupC", ("17677", "found")),
        ("NM_007294.3", "c.5266dup", ("17677", "found")),
        (None, "NM_007294.4:c.5266dup", ("17677", "found")),
        ("NM_007300.4", "c.5266dup", (None, "other_transcript")),
        (None, "c.5266del", (None, "unmapped")),
        (None, None, (None, "missing")),
    ],
)
def test_clinvar_id_needs_the_same_change_on_the_same_transcript(
    tmp_path, transcript, change, expected
):
    """The same c. change on another transcript can be another variant."""
    index = _clinvar_index(tmp_path)
    index.read({"BRCA1"})

    found = index.normalize("BRCA1", transcript, change)

    assert (found["clinvar_variation_id"], found["clinvar_status"]) == expected


def test_change_of_several_clinvar_variants_needs_a_transcript_to_get_an_id(tmp_path):
    index = _clinvar_index(tmp_path)
    index.read({"G6PD"})

    bare = index.normalize("G6PD", None, "c.1192G>A")
    with_transcript = index.normalize("G6PD", "NM_000402.4", "c.1192G>A")

    assert (bare["clinvar_variation_id"], bare["clinvar_status"]) == (None, "ambiguous")
    assert with_transcript["clinvar_variation_id"] == "10381"


def test_file_that_is_not_clinvars_summary_is_refused(tmp_path):
    path = tmp_path / "variant_summary.txt.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write("<html>\n")

    with pytest.raises(ValueError, match="lacks columns: Name, VariationID"):
        variants.ClinvarIndex(path)


def test_variants_get_their_clinvar_id_by_the_approved_gene_symbol(tmp_path):
    """The lookup runs after the gene lookup, so an alias finds the variant too."""
    extraction = records.ReportExtraction(
        "a.pdf",
        [1],
        {"variants": [{"gene_symbol": "FANCD1", "hgvs_c": "c.5946delT"}]},
    )
    input_path = tmp_path / "extractions.jsonl"
    input_path.write_text(extraction.to_json() + "\n")
    output_path = tmp_path / "normalized.jsonl"

    run.run(
        input_path,
        output_path,
        _hgnc_index(tmp_path),
        _mondo_index(tmp_path),
        None,
        _clinvar_index(tmp_path),
    )

    variant = json.loads(output_path.read_text())["normalized"]["variants"][0]
    assert (variant["clinvar_variation_id"], variant["hgvs_c_status"]) == (
        "9325",
        "valid",
    )


def test_every_report_gets_a_record_and_failures_stay_with_their_report(tmp_path):
    extractions = [
        records.ReportExtraction(
            "a.pdf", [1], {"report_date": "18-SEP-2026", "variants": []}
        ),
        records.ReportExtraction("b.pdf", [1], None, error="TimeoutError: slow"),
        records.ReportExtraction("c.pdf", [1], {"variants": "not a list"}),
    ]
    input_path = tmp_path / "extractions.jsonl"
    input_path.write_text("".join(e.to_json() + "\n" for e in extractions))
    output_path = tmp_path / "normalized.jsonl"

    failed = run.run(
        input_path, output_path, _hgnc_index(tmp_path), _mondo_index(tmp_path), None
    )

    written = [json.loads(line) for line in output_path.read_text().splitlines()]
    assert failed == ["b.pdf", "c.pdf"]
    assert written[0]["normalized"]["report_date"] == "2026-09-18"
    assert (written[1]["normalized"], written[1]["error"]) == (
        None,
        "TimeoutError: slow",
    )
    assert written[2]["normalized"] is None
    assert written[2]["error"].startswith("normalize: AttributeError")
