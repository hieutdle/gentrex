"""Tests of the synthetic report generator in gentrex-bench/generator/."""

import collections
import gzip
import html
import os
import pathlib
import random
import re
import subprocess
import sys

import pytest
from PIL import Image

sys.path.insert(
    0, str(pathlib.Path(__file__).parents[1] / "gentrex-bench" / "generator")
)

import check  # noqa: E402
import fill  # noqa: E402
import labs  # noqa: E402
import sample  # noqa: E402
import scan  # noqa: E402
import sources  # noqa: E402
import write  # noqa: E402

from gentrex import config  # noqa: E402
from gentrex.transcribe import native  # noqa: E402

_MODES = {
    "DMD": "x_linked_recessive",
    "CFTR": "autosomal_recessive",
    "MT-TL1": "mitochondrial",
}


def references() -> sources.References:
    """Returns three variants of every gene, one per classification."""
    genes = {g for area in labs.AREAS for g in area.genes}
    genes |= {*labs.CARRIER_GENES, *labs.MITO_GENES, *labs.SECONDARY_GENES}
    terms = {f"HP:000000{i}": sources.Term(f"Feature {i}", ()) for i in range(1, 7)}
    variants = {}
    for n, gene in enumerate(sorted(genes)):
        mode = _MODES.get(
            gene,
            "autosomal_recessive"
            if gene in labs.CARRIER_GENES
            else "autosomal_dominant",
        )
        if gene.startswith("MT-"):
            mode = "mitochondrial"
        disease = sources.Disease(
            f"MONDO:{n:07d}", f"{gene}-related disorder", mode, tuple(terms)
        )
        variants[gene] = [
            sources.Variant(
                f"{n}{i}",
                gene,
                f"HGNC:{n}",
                None if gene.startswith("MT-") else "NM_000001.1",
                None if gene.startswith("MT-") else f"c.{100 + i}C>T",
                None if gene.startswith("MT-") else f"p.Arg{34 + i}Trp",
                f"m.{3243 + i}A>G" if gene.startswith("MT-") else None,
                classification,
                disease,
            )
            for i, classification in enumerate(
                ["pathogenic", "likely_pathogenic", "uncertain_significance"]
            )
        ]
    regions = [
        sources.CopyNumberChange(
            f"9{i}",
            chromosome,
            band,
            {"GRCh37": (1_000_000 + i, 2_500_000 + i), "GRCh38": (900_000, 2_400_000)},
            copies,
            classification,
            20 + i,
            None,
        )
        for i, (chromosome, band, copies, classification) in enumerate(
            [
                ("17", "17p11.2", 3, "pathogenic"),
                ("22", "22q11.21", 1, "pathogenic"),
                ("7", "7q36.3", 3, "uncertain_significance"),
                ("X", "Xp22.31", 0, "uncertain_significance"),
            ]
        )
    ]
    inheritance = {
        "MONDO:0010383": "x_linked_dominant",
        "MONDO:0009669": "autosomal_recessive",
        "MONDO:0007739": "autosomal_dominant",
        "MONDO:0007105": "autosomal_dominant",
    }
    syndromes = {
        mondo_id: sources.Disease(
            mondo_id,
            f"syndrome {mondo_id}",
            inheritance.get(mondo_id, ""),
            tuple(terms),
        )
        for mondo_id in sample.SYNDROMES
    }
    return sources.References(variants, terms, {"BRCA1": ["RNF53"]}, regions, syndromes)


@pytest.fixture(scope="module")
def refs() -> sources.References:
    return references()


def test_same_seed_gives_same_cases():
    """The benchmark is rebuilt exactly from its seed, as TPC's dbgen is.

    Each run is a new process with its own hash seed, which changes the order
    of sets, so the test samples in two processes.
    """
    script = (
        "import json, sys; sys.path[:0] = ['tests', 'gentrex-bench/generator']; "
        "import sample, test_bench_generator as t; print(json.dumps(sample.sample("
        "t.references(), {seed!r}, 10, 10)))"
    )
    runs = [
        subprocess.run(
            [sys.executable, "-c", script.format(seed=seed)],
            capture_output=True,
            check=True,
            text=True,
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            cwd=pathlib.Path(__file__).parents[1],
        ).stdout
        for seed, hash_seed in (("seed", "1"), ("seed", "2"), ("other", "1"))
    ]
    assert runs[0] == runs[1]
    assert runs[0] != runs[2]


def test_records_follow_the_extraction_schema(refs):
    """A truth record has the fields gentrex extract writes, so it can be scored."""
    schema = config.load_schema()["properties"]
    variant_fields = set(schema["variants"]["items"]["properties"])
    for case in sample.sample(refs, "seed", 20, 20):
        assert set(case["record"]) == set(schema)
        for variant in case["record"]["variants"]:
            assert set(variant) == variant_fields


def test_held_out_labs_appear_only_in_test(refs):
    held_out = {lab.key for lab in labs.LABS if lab.held_out}
    cases = sample.sample(refs, "seed", 40, 40)
    assert not {c["lab"] for c in cases if c["split"] == "dev"} & held_out
    assert {c["lab"] for c in cases if c["split"] == "test"} & held_out


def test_templates_word_every_result_of_their_kinds():
    fields = {
        "gene": "BRCA1",
        "hgvs": "c.68_69del, p.(Glu23Valfs*17)",
        "zygosity": "heterozygous",
        "Zygosity": "Heterozygous",
        "classification": "pathogenic",
        "printed_class": "Pathogenic",
        "condition": "cystic fibrosis",
        "size": "~1.5 Mb",
        "SIZE": "1.50 MB",
        "change": "Deletion",
        "CHANGE": "DELETION",
        "BAND": "22Q11.21",
        "sex": "female",
        "Sex": "Female",
        "SEX": "FEMALE",
        "summary": "Positive",
        "syndrome": "Prader-Willi Syndrome",
    }
    for lab in labs.LABS:
        for kind in lab.kinds:
            for scenario in sample._scenarios(lab, kind):
                wording = lab.wording(kind, scenario).format(**fields)
                assert wording and "{" not in wording, (lab.key, kind, scenario)


def test_every_template_gets_enough_test_cases(refs):
    """Results split by template need enough reports of each template."""
    cases = sample.sample(refs, "seed", 100, 200)
    counts = collections.Counter(c["lab"] for c in cases if c["split"] == "test")
    assert {lab.key for lab in labs.LABS} == set(counts)
    assert min(counts.values()) >= 8, counts


def test_templates_share_the_test_cases_under_any_seed(refs):
    """A template takes only cases of its kinds, so evening out the counts can
    need a chain of moves through other templates."""
    for seed in range(10):
        plans = sample._Sampler(refs, str(seed)).plans("test", 200)
        counts = collections.Counter(lab.key for _, lab in plans)
        assert min(counts.values()) >= 8, (seed, counts)


def test_positive_case_has_a_pathogenic_variant():
    """A gene with only variants of uncertain significance can't be positive."""
    refs = references()
    for gene, variants in refs.variants.items():
        if not gene.startswith("MT-") and gene not in labs.CARRIER_GENES:
            refs.variants[gene] = variants[2:] if len(gene) % 2 else variants
    for case in sample.sample(refs, "seed", 100, 100):
        if case["scenario"] == "positive" and case["kind"] == "single_gene":
            classes = {v["classification"] for v in case["record"]["variants"]}
            assert classes & {"pathogenic", "likely_pathogenic"}, case["case_id"]


def test_cases_fit_their_template(refs):
    """A case uses a template that reports its test, with the template's fields."""
    templates = {lab.key: lab for lab in labs.LABS}
    for case in sample.sample(refs, "seed", 60, 60):
        lab = templates[case["lab"]]
        assert case["kind"] in lab.kinds
        assert "{" not in case["record"]["overall_result_raw"]
        assert all(case["record"][field] is None for field in lab.missing)


def test_tags_change_the_report(refs):
    """A tag on a report without its challenge would blur the results split by tag."""
    for case in sample.sample(refs, "seed", 60, 60):
        variants = case["record"]["variants"]
        current = [v["gene_symbol"] for v in case["normalized"]["variants"]]
        if "legacy_gene_symbol" in case["tags"]:
            assert [v["gene_symbol"] for v in variants] != current
        if "nonstandard_hgvs" in case["tags"]:
            assert any(v["hgvs_p"] for v in variants)
        if "multiple_variants" in case["tags"]:
            assert len(variants) >= 2


def test_templates_print_every_value_and_distractor(refs):
    """Code prints the truth, so a report fails the check only for the model's text.

    Every template fills cases of each of its kinds, with the tags that
    change its layout, and the HTML must hold every value and distractor
    of the case.
    """
    for case in sample.sample(refs, "seed", 60, 120):
        page = fill.fill(case, fill.stand_in_prose(case))
        # Comments aren't printed, unlike the page margins' text in the style.
        page = re.sub(r"/\*.*?\*/|<!--.*?-->", " ", page, flags=re.DOTALL)
        text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())
        values = [value for _, value in check._printed(case["record"])]
        values += [d["text"] for d in case["distractors"]]
        if case["unavailable"]:
            values.append("Not provided")
        missing = [v for v in values if " ".join(v.split()) not in text]
        assert not missing, (case["lab"], case["tags"], missing)
        build = case["record"]["genome_build"]
        assert check.named_builds([text]) == ({build} if build else set()), case["lab"]


def test_changes_that_the_case_does_not_print_are_found(refs):
    """A variant that the model prints wrongly would be a false variant in the truth."""
    case = next(
        c for c in sample.sample(refs, "seed", 40, 0) if c["record"]["variants"]
    )
    variant = case["record"]["variants"][0]
    change = variant["hgvs_c"] or variant["dna_change_raw"]
    pages = [f"The {change} variant.", "Compare c.9999del in another gene."]
    assert check.unexpected_changes(case, pages) == ["c.9999del"]


def test_karyotypes_that_the_case_does_not_print_are_found(refs):
    """A karyotype that the model writes may contradict the truth's."""
    case = next(
        c for c in sample.sample(refs, "seed", 40, 0) if c["kind"] == "karyotype"
    )
    karyotype = case["record"]["karyotype"]
    other = "46,XX" if karyotype != "46,XX" else "46,XY"
    pages = [f"RESULTS: {karyotype}", f"Unlike {other}, this karyotype"]
    assert check.unexpected_changes(case, pages) == [other]


def test_clinvar_rows_need_assertion_criteria(tmp_path):
    """ "no assertion criteria provided" contains "criteria provided", yet has none.

    Copy-number changes take their positions from the row of each build, and
    deletions of whole exons are kept although their ends are ranges.
    """
    columns = (
        "VariationID Type Name GeneSymbol HGNC_ID ClinicalSignificance "
        "ReviewStatus PhenotypeIDS Assembly Chromosome Start Stop Cytogenetic Origin"
    ).split()
    reviewed = "criteria provided, single submitter"
    condition = "MONDO:MONDO:0000001,OMIM:100000"
    rows = [
        (
            "1",
            "deletion",
            "NM_1.1(G1):c.10del (p.Leu4fs)",
            "G1",
            "HGNC:1",
            "Pathogenic",
            reviewed,
            condition,
            "GRCh38",
            "1",
            "10",
            "10",
            "1p36",
            "germline",
        ),
        (
            "2",
            "deletion",
            "NM_1.1(G1):c.20del (p.Leu7fs)",
            "G1",
            "HGNC:1",
            "Pathogenic",
            "no assertion criteria provided",
            condition,
            "GRCh38",
            "1",
            "20",
            "20",
            "1p36",
            "germline",
        ),
        (
            "3",
            "deletion",
            "NM_1.1(G1):c.(?_30)_(90_?)del",
            "G1",
            "HGNC:1",
            "Pathogenic",
            reviewed,
            condition,
            "GRCh38",
            "1",
            "30",
            "90",
            "1p36",
            "germline",
        ),
    ]
    name = "GRCh38/hg38 17p11.2(chr17:16852187-20399047)x3"
    rows += [
        (
            "4",
            "copy number gain",
            name,
            "subset of 81 genes: RAI1",
            "",
            "Pathogenic",
            reviewed,
            "-",
            build,
            "17",
            start,
            stop,
            "17p11.2",
            "germline",
        )
        for build, start, stop in (
            ("GRCh37", "16755501", "20302361"),
            ("GRCh38", "16852187", "20399047"),
        )
    ]
    path = tmp_path / "variant_summary.txt.gz"
    with gzip.open(path, "wt") as fh:
        fh.write("\t".join(columns) + "\n")
        fh.writelines("\t".join(row) + "\n" for row in rows)
    disease = ("autosomal_dominant", ("HP:0000001", "HP:0000002"))
    variants, regions = sources.load_clinvar(
        path, {"G1"}, {"MONDO:0000001": "a disease"}, {"OMIM:100000": disease}
    )
    assert [v.hgvs_c for v in variants["G1"]] == ["c.10del", "c.(?_30)_(90_?)del"]
    (region,) = regions
    assert region.positions["GRCh37"] == (16755501, 20302361)
    assert (region.copy_number, region.genes) == (3, 81)


def test_image_copy_goes_to_ocr():
    """The image copy's only text, a document code, is longer than
    transcribe.native_min_chars, so only its full-page image sends it to OCR."""
    code = scan.document_code("SYN-0001")
    min_chars = config.load_settings()["transcribe"]["native_min_chars"]
    assert len("".join(code.split())) >= min_chars
    assert native.classify_source(code, min_chars, 1.0, 0) == "scanned"


def test_zygosity_fits_inheritance_and_sex(refs):
    """X-linked recessive findings are hemizygous in males, X-linked dominant
    ones heterozygous in females, and carrier findings heterozygous."""
    for case in sample.sample(refs, "seed", 60, 60):
        sex = case["card"]["patient"]["sex"]
        for variant in case["record"]["variants"]:
            mode = variant["mode_of_inheritance"]
            if not variant["zygosity"] or variant["is_secondary_finding"]:
                continue
            if mode == "x_linked_recessive":
                assert (sex, variant["zygosity"]) == ("Male", "hemizygous")
            if mode == "x_linked_dominant":
                assert (sex, variant["zygosity"]) == ("Female", "heterozygous")
            if case["scenario"] == "carrier":
                assert variant["zygosity"] == "heterozygous"
                assert mode == "autosomal_recessive"


def test_each_condition_keeps_its_own_ids():
    """ClinVar separates conditions with "|" and ";", and IDs must not mix."""
    mondo = {"MONDO:0012652": "LGMD 2L", "MONDO:0008151": "GDD"}
    annotations = {
        "OMIM:611307": ("autosomal_recessive", ("HP:0000001",)),
        "OMIM:166260": ("autosomal_dominant", ("HP:0000002",)),
    }
    ids = (
        "MedGen:C3661900|MONDO:MONDO:0012652,MedGen:C1969785,OMIM:611307,"
        "Orphanet:206549;MONDO:MONDO:0008151,MedGen:C1833736,OMIM:166260"
    )
    found = sources._diseases(ids, mondo, annotations)
    assert [(d.mondo_id, d.inheritance) for d in found] == [
        ("MONDO:0012652", "autosomal_recessive"),
        ("MONDO:0008151", "autosomal_dominant"),
    ]


def test_locate_finds_whole_values_and_wrapped_cells():
    pages = [
        check.page_lines("Sex: Female\nTest: Whole-\nexome sequencing"),
        check.page_lines("Peripheral blood, Other cell\nEDTA text"),
        check.page_lines("c.1A>G limb- HET\ngirdle dystrophy AR"),
    ]
    assert check.locate("Male", pages) == ([], [])
    assert check.locate("Whole-exome sequencing", pages) == ([1], [])
    assert check.locate("Peripheral blood, EDTA", pages) == ([], [2])
    assert check.locate("limb-girdle dystrophy", pages) == ([], [3])


def test_scan_is_reproducible():
    """The same case gives the same damage, so the scanned copies can be rebuilt."""
    page = Image.new("L", (400, 300), 255)
    for level in scan.LEVELS:
        a = scan.degrade(page, level, random.Random("SYN-0001:" + level))
        b = scan.degrade(page, level, random.Random("SYN-0001:" + level))
        assert a.tobytes() == b.tobytes()


def test_paragraphs_written_as_one_string_are_split():
    """A server that ignores the schema must not get a report printed by letter."""
    case = {"record": {"variants": []}}
    prose = fill.stand_in_prose(case) | {"interpretation": "First.\n\nSecond."}
    prose = write.paragraphs(prose)
    assert prose["interpretation"] == ["First.", "Second."]
    assert write.problems(case, prose) == []


def test_list_field_of_another_type_is_a_problem():
    case = {"record": {"variants": []}}
    prose = fill.stand_in_prose(case) | {"recommendations": {"first": "Rest."}}
    assert write.problems(case, write.paragraphs(prose)) == [
        "recommendations must be lists of paragraphs"
    ]
