"""Tests of the synthetic report generator in gentrex-bench/generator/."""

import os
import pathlib
import random
import subprocess
import sys

import pytest
from PIL import Image

sys.path.insert(
    0, str(pathlib.Path(__file__).parents[1] / "gentrex-bench" / "generator")
)

import check  # noqa: E402
import labs  # noqa: E402
import sample  # noqa: E402
import scan  # noqa: E402
import sources  # noqa: E402

from gentrex import config  # noqa: E402

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
    return sources.References(variants, terms, {"BRCA1": ["RNF53"]})


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


def test_zygosity_fits_inheritance_and_sex(refs):
    """X-linked findings are hemizygous in males, carrier findings heterozygous."""
    for case in sample.sample(refs, "seed", 60, 60):
        for variant in case["record"]["variants"]:
            mode = variant["mode_of_inheritance"]
            if mode.startswith("x_linked") and not variant["is_secondary_finding"]:
                assert case["card"]["patient"]["sex"] == "Male"
                assert variant["zygosity"] == "hemizygous"
            if case["scenario"] == "carrier":
                assert variant["zygosity"] == "heterozygous"
                assert mode == "autosomal_recessive"


def test_locate_finds_whole_values_and_wrapped_cells():
    pages = [
        check.page_lines("Sex: Female\nTest: Whole-\nexome sequencing"),
        check.page_lines("Peripheral blood, Other cell\nEDTA text"),
    ]
    assert check.locate("Male", pages) == ([], [])
    assert check.locate("Whole-exome sequencing", pages) == ([1], [])
    assert check.locate("Peripheral blood, EDTA", pages) == ([], [2])


def test_scan_is_reproducible():
    """The same case gives the same damage, so the scanned copies can be rebuilt."""
    page = Image.new("L", (400, 300), 255)
    for level in scan.LEVELS:
        a = scan.degrade(page, level, random.Random("SYN-0001:" + level))
        b = scan.degrade(page, level, random.Random("SYN-0001:" + level))
        assert a.tobytes() == b.tobytes()
