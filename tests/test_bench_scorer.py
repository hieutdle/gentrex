"""Tests of the scorer in gentrex-bench/scorer/."""

import copy
import json
import pathlib
import sys
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "gentrex-bench" / "scorer"))

import compare  # noqa: E402
import score  # noqa: E402

from gentrex import config  # noqa: E402

_PAGES = [
    "MRN: SYN-MRN-0001 Born: 10/10/1999\n"
    "Indication: Waddling gait\nPOSITIVE: Pathogenic variant detected",
    "Specimen: Saliva\n"
    "DMD c.5266dup Pathogenic Hemizygous Duchenne muscular dystrophy\n"
    "Literature reports c.100C>T in other patients.",
]


def _truth(name: str = "SYN-0001", split: str = "dev") -> dict[str, Any]:
    return {
        "case": {
            "case_id": name,
            "split": split,
            "lab": "exome-box",
            "kind": "exome",
            "scenario": "positive",
            "tags": ["repeated_variant"],
        },
        "record": {
            "mrn": "SYN-MRN-0001",
            "date_of_birth": "10/10/1999",
            "specimen_type": "Saliva",
            "overall_result_raw": "POSITIVE: Pathogenic variant detected",
            "karyotype": None,
            "patient_phenotypes": [{"text": "Waddling gait", "present": True}],
            "variants": [
                {
                    "gene_symbol": "DMD",
                    "hgvs_c": "c.5266dup",
                    "dna_change_raw": None,
                    "classification_raw": "Pathogenic",
                    "classification": "pathogenic",
                    "zygosity_raw": "Hemizygous",
                    "zygosity": "hemizygous",
                    "associated_phenotype": "Duchenne muscular dystrophy",
                }
            ],
        },
        "normalized": {
            "date_of_birth": "1999-10-10",
            "specimen_type": "saliva",
            "overall_result": "positive",
            "variants": [{"hgnc_id": "HGNC:2928", "disease_id": "MONDO:0010679"}],
            "patient_phenotypes": [{"hpo_id": "HP:0002515"}],
        },
        "distractors": [{"kind": "literature_variant", "text": "c.100C>T"}],
    }


def _report(truth: dict[str, Any]) -> dict[str, Any]:
    """Returns the line of normalized.jsonl that gets everything right."""
    return {
        "file": f"{truth['case']['case_id']}.pdf",
        "data": copy.deepcopy(truth["record"]),
        "normalized": copy.deepcopy(truth["normalized"]),
    }


def _compare(
    report: dict[str, Any] | None,
    transcribed: list[str] = _PAGES,
    kept: list[str] = _PAGES,
) -> dict[str, compare.Outcome]:
    """Returns the outcomes that are not correct, by field."""
    outcomes = compare.compare(
        _truth(), report, transcribed, kept, config.load_schema()
    )
    return {o.field: o for o in outcomes if o.result != "correct"}


def _write_run(
    tmp_path: pathlib.Path,
    truths: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    seconds: float = 36.0,
) -> tuple[pathlib.Path, pathlib.Path]:
    """Writes truth files and the run folders of the four commands.

    Returns:
        The truth folder and the run folder of gentrex normalize.
    """
    truth_dir = tmp_path / "v1" / "truth"
    truth_dir.mkdir(parents=True, exist_ok=True)
    for truth in truths:
        path = truth_dir / f"{truth['case']['case_id']}.json"
        path.write_text(json.dumps(truth))
    pages = [
        {"file": report["file"], "page": number, "text": text}
        for report in reports
        for number, text in enumerate(_PAGES, 1)
    ]
    previous = tmp_path / "pdf" / "native"
    for name in ("transcribe", "select", "extract", "normalize"):
        folder = tmp_path / "results" / name / "20261110-120000"
        folder.mkdir(parents=True)
        record = {
            "input": str(previous),
            "settings": {"hpo_version": "v2026-09-01"},
            "seconds": seconds,
        }
        (folder / "run.yaml").write_text(yaml.safe_dump(record))
        (folder / "pages.jsonl").write_text(
            "".join(json.dumps(page) + "\n" for page in pages)
        )
        previous = folder
    (previous / "normalized.jsonl").write_text(
        "".join(json.dumps(report) + "\n" for report in reports)
    )
    return truth_dir, previous


def test_the_truth_scores_all_right(tmp_path):
    """A scorer that finds errors in the truth itself can't be trusted."""
    truth = _truth()
    truth_dir, run_dir = _write_run(tmp_path, [truth], [_report(truth)])

    scores, errors = score.score(truth_dir, run_dir, "dev")

    assert errors == []
    assert scores["main"]["report_accuracy"]["value"] == 1
    assert scores["main"]["variant_f1"]["value"] == 1
    assert {f["accuracy"] for f in scores["fields"].values()} == {1}


def test_a_lost_value_is_charged_to_the_first_command_that_lost_it():
    """The error table must point at the command to fix."""
    report = _report(_truth())
    report["data"]["mrn"] = None
    report["data"]["date_of_birth"] = None
    report["data"]["specimen_type"] = "Blood"
    report["normalized"]["specimen_type"] = "whole_blood"
    report["normalized"]["variants"][0]["hgnc_id"] = "HGNC:1"

    wrong = _compare(
        report,
        transcribed=[_PAGES[0].replace("SYN-MRN-0001", "5YN-MRN-OOO1"), _PAGES[1]],
        kept=[_PAGES[1]],
    )

    assert wrong["mrn"].command == "transcribe"
    assert wrong["date_of_birth"].command == "select"
    assert wrong["specimen_type"].command == "extract"
    assert wrong["normalized.variants.hgnc_id"].command == "normalize"
    # The wrong category follows from the wrong specimen, which is charged.
    assert wrong["normalized.specimen_type"].command is None


def test_other_spellings_match_but_are_not_exact():
    """A variant written another way is the same variant."""
    report = _report(_truth())
    report["data"]["variants"][0]["hgvs_c"] = "NM_004006.3:c.5266dupC"
    report["data"]["specimen_type"] = "saliva."

    outcomes = compare.compare(_truth(), report, _PAGES, _PAGES, config.load_schema())

    by_field = {o.field: o for o in outcomes}
    assert {o.result for o in outcomes} == {"correct"}
    assert not by_field["variants.hgvs_c"].strict
    assert not by_field["specimen_type"].strict


def test_a_finding_not_flagged_as_secondary_is_false_or_empty():
    """A report that labels no finding as primary leaves nothing to tell apart."""
    truth = _truth()
    truth["record"]["variants"][0]["is_secondary_finding"] = None
    report = _report(truth)
    report["data"]["variants"][0]["is_secondary_finding"] = False

    outcomes = compare.compare(truth, report, _PAGES, _PAGES, config.load_schema())

    assert {o.result for o in outcomes} == {"correct"}
    report["data"]["variants"][0]["is_secondary_finding"] = True
    outcomes = compare.compare(truth, report, _PAGES, _PAGES, config.load_schema())
    wrong = {o.field: o.result for o in outcomes if o.result != "correct"}
    assert wrong == {"variants.is_secondary_finding": "wrong"}


@pytest.mark.parametrize(
    ("found", "result"),
    [
        ("NoonanScan: Analyses of 11 Genes", "correct"),
        ("DMD Gene Sequencing and Deletion/Duplication", "wrong"),
        ("NoonanScan", "correct"),
        ("Noonan", "wrong"),
        ("Analyses of 11 Genes", "wrong"),
    ],
)
def test_a_test_name_cut_at_another_place_is_the_same_name(found, result):
    """A heading prints the name with a subtitle, and a table without one."""
    truth = _truth()
    truth["record"]["test_name"] = "NoonanScan: Analyses"
    report = _report(truth)
    report["data"]["test_name"] = found

    outcomes = compare.compare(truth, report, _PAGES, _PAGES, config.load_schema())

    by_field = {o.field: o.result for o in outcomes}
    assert by_field["test_name"] == result


def test_a_feature_from_the_reason_for_testing_is_no_extra_feature():
    """The schema sends a feature named as the indication to the features."""
    truth = _truth()
    truth["record"]["clinical_indication"] = "Short stature and seizures"
    report = _report(truth)
    report["data"]["patient_phenotypes"] += [
        {"text": "short stature", "present": True},
        {"text": "Ataxia", "present": True},
    ]
    report["normalized"]["patient_phenotypes"] += [
        {"hpo_id": "HP:0004322"},
        {"hpo_id": "HP:0001251"},
    ]

    outcomes = compare.compare(truth, report, _PAGES, _PAGES, config.load_schema())

    extra = [(o.field, o.found) for o in outcomes if o.result == "extra"]
    assert extra == [
        ("patient_phenotypes", "Ataxia"),
        ("normalized.patient_phenotypes", "HP:0001251"),
    ]


def test_a_feature_without_an_hpo_term_is_missed_and_not_also_extra():
    """gentrex normalize gives no term below its similarity threshold."""
    report = _report(_truth())
    report["normalized"]["patient_phenotypes"] = [{"hpo_id": None}]

    outcomes = compare.compare(_truth(), report, _PAGES, _PAGES, config.load_schema())

    wrong = [(o.field, o.result) for o in outcomes if o.result != "correct"]
    assert wrong == [("normalized.patient_phenotypes", "missed")]


def test_a_reference_before_an_m_change_matches():
    """The schema's own example writes an m. change after its reference."""
    assert compare.key("dna_change_raw", "NC_012920.1:m.3243A>G") == compare.key(
        "dna_change_raw", "m.3243A>G"
    )
    assert compare.key("hgvs_c", "NM_004006.3(DMD):c.5266dup") == "c.5266dup"
    # A colon in other wording starts no reference.
    assert compare.key("dna_change_raw", "SMN1 copy number: 1") != "1"


def test_a_variant_matches_under_its_approved_gene_symbol():
    """The schema doesn't ask for the printed symbol, so MLH1 for COCA2 is right."""
    truth = _truth()
    truth["record"]["variants"][0]["gene_symbol"] = "COCA2"
    truth["normalized"]["variants"][0]["gene_symbol"] = "MLH1"
    report = _report(truth)
    report["data"]["variants"][0]["gene_symbol"] = "MLH1"

    outcomes = compare.compare(truth, report, _PAGES, _PAGES, config.load_schema())

    assert {o.result for o in outcomes} == {"correct"}


def test_a_variant_without_a_change_matches_on_its_gene():
    """An SMN1 copy number has no DNA change, so wording copied there is only extra."""
    truth = _truth()
    truth["record"]["variants"][0]["hgvs_c"] = None
    report = _report(truth)
    report["data"]["variants"][0]["dna_change_raw"] = "DMD copy number: 1"

    outcomes = compare.compare(truth, report, _PAGES, _PAGES, config.load_schema())

    wrong = {o.field: o.result for o in outcomes if o.result != "correct"}
    assert wrong == {"variants.dna_change_raw": "extra"}


def test_an_extra_variant_from_a_distractor_is_told_from_a_made_up_one():
    """Copying a cited variant and inventing one need different fixes."""
    report = _report(_truth())
    cited = {"gene_symbol": "DMD", "hgvs_c": "c.100C>T"}
    made_up = {"gene_symbol": "TTN", "hgvs_c": "c.7G>A"}
    report["data"]["variants"] += [cited, made_up]

    outcomes = compare.compare(_truth(), report, _PAGES, _PAGES, config.load_schema())

    extra = [o for o in outcomes if o.field == "variants" and o.result == "extra"]
    assert [o.cause for o in extra] == ["distractor", "hallucination"]


def test_the_check_of_copied_values_is_scored_against_the_truth(tmp_path):
    """The check is useful if what it names is wrong, and what is wrong is named."""
    truth = _truth()
    report = _report(truth)
    report["data"]["mrn"] = "SYN-MRN-0002"
    report["data"]["variants"].append({"gene_symbol": "TTN", "hgvs_c": "c.7G>A"})
    report["not_in_pages"] = ["variants[1].gene_symbol", "variants[1].hgvs_c"]
    truth_dir, run_dir = _write_run(tmp_path, [truth], [report])

    scores, _ = score.score(truth_dir, run_dir, "dev")

    # The made-up variant is named, and the wrong MRN is not.
    check = scores["checks"]["not_in_pages"]
    assert (check["flagged"], check["not_right"]) == (1, 2)
    assert (check["precision"], check["recall"]) == (1, 0.5)


def test_a_clinvar_id_is_scored_only_after_a_lookup():
    """A run without ClinVar's file must not lose points for the IDs."""
    truth = _truth()
    truth["normalized"]["variants"][0]["clinvar_variation_id"] = "11"
    report = _report(truth)
    report["normalized"]["variants"][0]["clinvar_variation_id"] = None
    schema = config.load_schema()

    without = compare.compare(truth, report, _PAGES, _PAGES, schema)
    looked_up = compare.compare(truth, report, _PAGES, _PAGES, schema, clinvar=True)

    assert {o.result for o in without} == {"correct"}
    missed = [o for o in looked_up if o.result != "correct"]
    assert [(o.field, o.command) for o in missed] == [
        ("normalized.variants.clinvar_variation_id", "normalize")
    ]


@pytest.mark.parametrize(
    ("field", "value", "right"),
    [("zygosity", "heterozygous", False), ("associated_phenotype", "DMD", True)],
)
def test_only_clinical_errors_make_a_report_wrong(tmp_path, field, value, right):
    """Report accuracy counts what would change the patient's care."""
    truth = _truth()
    report = _report(truth)
    report["data"]["variants"][0][field] = value
    truth_dir, run_dir = _write_run(tmp_path, [truth], [report])

    scores, _ = score.score(truth_dir, run_dir, "dev")

    assert scores["main"]["report_accuracy"]["value"] == right


def test_value_numbers_count_only_stated_and_written_values(tmp_path):
    """A field that a report rightly leaves empty would flatter the accuracy,
    so precision, recall and F1 leave it out. One wrong value that isn't
    clinical keeps the report right and its record incomplete."""
    truth = _truth()
    truth["pages"] = [{"page": n, "text": text} for n, text in enumerate(_PAGES, 1)]
    report = _report(truth)
    report["data"]["specimen_type"] = "Blood"
    truth_dir, run_dir = _write_run(tmp_path, [truth], [report])

    scores, _ = score.score(truth_dir, run_dir, "dev")

    main = {name: number["value"] for name, number in scores["main"].items()}
    assert (main["report_accuracy"], main["record_accuracy"]) == (1, 0)
    assert main["value_recall"] == main["value_precision"] < 1
    assert scores["fields"]["karyotype"]["stated"] == 0
    assert scores["fields"]["karyotype"]["f1"] is None
    assert scores["fields"]["specimen_type"]["f1"] == 0
    funnel = scores["funnel"]
    assert funnel["lost"] == {"transcribe": 0, "select": 0, "extract": 1}
    assert funnel["stated"] == funnel["right"] + 1
    assert scores["groups"]["pages"] == {"2": {"reports": 1, "report_accuracy": 1.0}}
    assert scores["by_report"]["SYN-0001"]["case"]["lab"] == "exome-box"


def test_ocr_words_are_compared_with_the_true_page_whatever_their_order():
    """OCR reads the columns of a page in another order than the PDF's text.

    The first page is the only one that prints the MRN, so gentrex select
    must keep it, and the second page is one it may drop.
    """
    true_pages = [(1, "MRN 12 Sex Female"), (2, "Methods")]
    truths = {
        "a": {
            "pages": [{"page": page, "text": text} for page, text in true_pages],
            "record": {"mrn": "12", "variants": [], "patient_phenotypes": []},
        }
    }
    scanned = {"file": "a.pdf", "page": 1, "source": "scanned"}
    native = {"file": "a.pdf", "page": 2, "source": "native", "text": "Methods"}
    pages = [scanned | {"text": "**Sex** Female MRN 72 x"}, native]

    found = score._pages(truths, ["a"], pages, pages[:1])

    assert (found["total"], found["ocr"], found["kept"]) == (2, 1, 1)
    assert found["ocr_word_recall"] == 0.75
    assert found["ocr_word_precision"] == 0.6
    assert (found["needed"], found["needed_kept"]) == (1, 1)
    assert (found["other"], found["other_dropped"]) == (1, 1)


@pytest.mark.parametrize(
    ("field", "found", "kind"),
    [
        # The true value is "Saliva".
        ("specimen_type", "Saliva in Oragene", "partial"),
        # The MRN in the field of the date of birth.
        ("date_of_birth", "SYN-MRN-0001", "other_value"),
        # A variant that the report cites from the literature.
        ("specimen_type", "c.100C>T", "other_value"),
        ("specimen_type", "Buccal swab", "not_in_pages"),
        ("specimen_type", "Pathogenic variant detected", "other_text"),
    ],
)
def test_a_wrong_text_is_told_by_where_it_comes_from(field, found, kind):
    """Each kind of error needs another fix: a longer copy, a sharper field,
    or a model that copies instead of writing."""
    report = _report(_truth())
    report["data"][field] = found

    wrong = _compare(report)

    assert wrong[field].cause == kind


def test_categories_are_counted_by_what_they_were_written_as(tmp_path):
    """A confusion of pathogenic with likely pathogenic differs from one with
    benign, which the accuracy alone doesn't show."""
    truth = _truth()
    report = _report(truth)
    report["data"]["variants"][0]["classification"] = "likely_pathogenic"
    truth_dir, run_dir = _write_run(tmp_path, [truth], [report])

    scores, _ = score.score(truth_dir, run_dir, "dev")

    confusions = scores["confusions"]
    assert confusions["variants.classification"] == {
        "pathogenic": {"likely_pathogenic": 1}
    }
    assert confusions["normalized.overall_result"] == {"positive": {"positive": 1}}
    assert scores["fields"]["variants.classification"]["kinds"] == {"category": 1}


def test_checks_are_scored_by_value_and_by_report(tmp_path):
    """A check is worth a person's time if the reports that it flags are the
    wrong ones."""
    truths = [_truth("SYN-0001"), _truth("SYN-0002")]
    right, wrong = _report(truths[0]), _report(truths[1])
    right["normalized"]["overall_result_conflict"] = True
    wrong["normalized"]["overall_result_conflict"] = False
    wrong["normalized"]["overall_result"] = "negative"
    wrong["normalized"]["variants"][0]["hgvs_c_status"] = "invalid"
    truth_dir, run_dir = _write_run(tmp_path, truths, [right, wrong])

    scores, _ = score.score(truth_dir, run_dir, "dev")

    conflict = scores["checks"]["result_conflict"]
    assert (conflict["values"], conflict["flagged"], conflict["not_right"]) == (2, 1, 1)
    assert conflict["flagged_and_not_right"] == 0
    assert scores["checks"]["hgvs_invalid"]["flagged"] == 1
    assert scores["by_report"]["SYN-0001"]["flags"] == ["result_conflict"]
    assert scores["by_report"]["SYN-0002"]["flags"] == ["hgvs_invalid"]
    review = scores["review"]
    assert (review["reports"], review["wrong"]) == (2, 1)
    assert review["checks"]["any"] == {
        "flagged": 2,
        "flagged_and_wrong": 1,
        "precision": 0.5,
        "recall": 1.0,
    }


def test_variants_are_scored_by_their_kind(tmp_path):
    """A pipeline that reads sequence variants may still miss copy numbers."""
    truth = _truth()
    truth["record"]["variants"].append(
        truth["record"]["variants"][0]
        | {"gene_symbol": "SMN1", "hgvs_c": None, "copy_number": 0}
    )
    truth["normalized"]["variants"].append({"hgnc_id": "HGNC:11117"})
    report = _report(truth)
    del report["data"]["variants"][1]
    truth_dir, run_dir = _write_run(tmp_path, [truth], [report])

    scores, _ = score.score(truth_dir, run_dir, "dev")

    kinds = scores["variant_kinds"]
    assert (kinds["sequence"]["found"], kinds["sequence"]["classification"]) == (1, 1)
    assert (
        kinds["gene_copy_number"]["stated"],
        kinds["gene_copy_number"]["found"],
    ) == (
        1,
        0,
    )


def _terms(*ids: str | None, first: str | None = "HP:0000001") -> list[dict]:
    """Returns the HPO term of one feature, with candidates in the given order."""
    candidates = [{"hpo_id": hpo_id} for hpo_id in ids]
    return [{"hpo_id": first, "models_agree": False, "candidates": candidates}]


@pytest.mark.parametrize(
    ("term", "numbers"),
    [
        # The true term, HP:0002515, is the second candidate.
        (_terms("HP:0000001", "HP:0002515"), (0, 0, 1, 0)),
        (_terms("HP:0002515", first="HP:0002515"), (1, 1, 1, 0)),
        # Too unlike every HPO name: no term, though the first candidate is right.
        (_terms("HP:0002515", first=None), (0, 1, 1, 1)),
    ],
)
def test_hpo_terms_are_scored_at_the_first_place_and_among_the_candidates(
    tmp_path, term, numbers
):
    """A person who checks the candidates finds the term even when the first
    one is wrong, so the paper gives both."""
    truth = _truth()
    report = _report(truth)
    report["normalized"]["patient_phenotypes"] = term
    truth_dir, run_dir = _write_run(tmp_path, [truth], [report])

    scores, _ = score.score(truth_dir, run_dir, "dev")

    hpo = scores["hpo"]["all"]
    names = ("top_1", "first_candidate", "top_5", "no_term")
    assert tuple(hpo[name] for name in names) == numbers
    assert scores["hpo"]["models disagree"]["features"] == 1


def test_genes_are_scored_by_whether_the_report_prints_the_approved_symbol(tmp_path):
    """An older symbol is the hard case of the HGNC lookup."""
    truth = _truth()
    truth["record"]["variants"][0]["gene_symbol"] = "COCA2"
    truth["normalized"]["variants"][0]["gene_symbol"] = "MLH1"
    report = _report(truth)
    report["normalized"]["variants"][0]["hgnc_id"] = None
    truth_dir, run_dir = _write_run(tmp_path, [truth], [report])

    scores, _ = score.score(truth_dir, run_dir, "dev")

    older = scores["normalize"]["normalized.variants.hgnc_id (older symbol)"]
    assert (older["values"], older["right"], older["given_right_source"]) == (1, 0, 0)
    assert "normalized.variants.hgnc_id (approved symbol)" not in scores["normalize"]


def test_page_selection_is_scored_at_the_run_and_at_other_thresholds(tmp_path):
    """The second page is the only one with the variant, so dropping it loses
    the variant. A lower threshold would keep it, which the sweep shows."""
    truth = _truth()
    truth["pages"] = [{"page": n, "text": text} for n, text in enumerate(_PAGES, 1)]
    report = _report(truth)
    truth_dir, run_dir = _write_run(tmp_path, [truth], [report])
    select_dir = run_dir.parents[1] / "select" / run_dir.name
    answers = [(1, 0.9, True), (2, 0.3, False)]
    (select_dir / "decisions.jsonl").write_text(
        "".join(
            json.dumps(
                {"file": "SYN-0001.pdf", "page": page, "p_yes": {"q": p}, "keep": keep}
            )
            + "\n"
            for page, p, keep in answers
        )
    )
    run = yaml.safe_load((select_dir / "run.yaml").read_text())
    run["settings"]["keep_threshold"] = 0.5
    (select_dir / "run.yaml").write_text(yaml.safe_dump(run))

    scores, _ = score.score(truth_dir, run_dir, "dev")

    select = scores["select"]
    assert (select["needed_kept"], select["needed_dropped"]) == (1, 1)
    assert select["values_reachable"] < select["values"]
    sweep = {row["threshold"]: row for row in select["sweep"]}
    assert sweep[0.5]["needed_kept"] == 0.5
    assert (sweep[0.2]["needed_kept"], sweep[0.2]["values_reachable"]) == (1, 1)
    assert select["only_by"] == {"q": {"pages": 1, "needed": 1}}


def test_extract_is_also_scored_on_the_values_that_reached_it(tmp_path):
    """A value on a dropped page is select's loss, not extract's."""
    truth = _truth()
    report = _report(truth)
    report["data"]["specimen_type"] = None
    kept = [_PAGES[0]]
    truth_dir, run_dir = _write_run(tmp_path, [truth], [report])
    select_dir = run_dir.parents[1] / "select" / run_dir.name
    (select_dir / "pages.jsonl").write_text(
        json.dumps({"file": "SYN-0001.pdf", "page": 1, "text": kept[0]}) + "\n"
    )

    scores, _ = score.score(truth_dir, run_dir, "dev")

    funnel = scores["funnel"]
    assert funnel["lost"]["select"] >= 1
    assert funnel["extract_recall"] > funnel["right"] / funnel["stated"]
    specimen = scores["fields"]["specimen_type"]
    assert (specimen["recall"], specimen["recall_given_input"]) == (0, None)


def test_runs_are_listed_by_their_setup(tmp_path):
    """The label tells two runs on the same copy apart, as two models."""
    truth = _truth()
    truth_dir, run_dir = _write_run(tmp_path, [truth], [_report(truth)])
    scores, errors = score.score(truth_dir, run_dir, "dev", label="Qwen")
    out = tmp_path / "scored" / "20261118-120000"
    out.mkdir(parents=True)
    score.write(out, scores, errors)

    (line,) = score.list_runs(tmp_path / "scored")

    assert score.setup(scores) == "native, Qwen"
    assert line.startswith("20261118-120000  dev ")
    assert "report accuracy 100.0%" in line


def test_a_report_without_a_record_counts_as_missed(tmp_path):
    """Dropping failed reports would make a setup that often fails look good."""
    truths = [_truth("SYN-0001"), _truth("SYN-0002")]
    truth_dir, run_dir = _write_run(tmp_path, truths, [_report(truths[0])])

    scores, errors = score.score(truth_dir, run_dir, "dev")

    assert scores["reports"] == 2
    assert scores["without_record"] == 1
    assert scores["main"]["report_accuracy"]["value"] == 0.5
    assert scores["entities"]["variants"]["missed"] == 1
    assert {error["report"] for error in errors} == {"SYN-0002"}


def test_only_the_named_split_is_scored(tmp_path):
    """Test reports must not leak into the numbers used for tuning."""
    truths = [_truth("SYN-0001", "dev"), _truth("SYN-0101", "test")]
    reports = [_report(truths[0]), {"file": "SYN-0101.pdf", "data": None}]
    truth_dir, run_dir = _write_run(tmp_path, truths, reports)

    scores, _ = score.score(truth_dir, run_dir, "dev")

    assert list(scores["by_report"]) == ["SYN-0001"]
    assert scores["main"]["report_accuracy"]["value"] == 1


def test_gpu_hours_come_from_the_time_of_each_command(tmp_path):
    """Cost is the time of each command times the GPUs of its model server."""
    truth = _truth()
    truth_dir, run_dir = _write_run(tmp_path, [truth], [_report(truth)], seconds=36.0)

    scores, _ = score.score(truth_dir, run_dir, "dev", gpus=[1, 1, 2])

    # (36 s x 1 + 36 s x 1 + 36 s x 2) / 3600 for one PDF, times 1,000.
    assert scores["performance"]["gpu_hours_per_1000_files"] == 40.0
    assert scores["performance"]["seconds_per_1000_files"] == 144000


def test_two_runs_are_compared_on_the_reports_they_share():
    """Reports that only one run has would shift the difference."""
    first = {"by_report": {"a": {"correct": False}, "b": {"correct": True}}}
    second = {
        "by_report": {
            "a": {"correct": True},
            "b": {"correct": True},
            "c": {"correct": False},
        }
    }

    gain = score.difference(first, second)

    assert (gain["reports"], gain["value"]) == (2, 0.5)
    assert gain["low"] <= gain["value"] <= gain["high"]
