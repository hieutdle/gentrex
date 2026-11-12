"""Compare what Gentrex wrote for one report with the report's truth.

Every value becomes one Outcome. Variants are matched one to one by gene and
DNA change, and clinical features by their text and, after gentrex normalize,
by their HPO ID. docs/development/benchmark.md explains the rules.
"""

import dataclasses
import pathlib
import re
import sys
import unicodedata
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "generator"))

import check  # noqa: E402

from gentrex.extract import check as extract_check  # noqa: E402

RESULTS = ("correct", "missed", "extra", "wrong")
# Variants and clinical features, which are matched and then counted as found,
# missed or extra.
ENTITIES = ("variants", "patient_phenotypes", "normalized.patient_phenotypes")
# A report is right when all of these are. A matched variant has the right
# gene and DNA change.
CLINICAL = frozenset(
    {
        "normalized.overall_result",
        "karyotype",
        "variants",
        "variants.copy_number",
        "variants.classification",
        "variants.zygosity",
    }
)
_NORMALIZED = (
    "date_of_birth",
    "collection_date",
    "received_date",
    "test_started_date",
    "report_date",
    "specimen_type",
)
# What gentrex normalize adds to a variant, and the field it reads it from.
_NORMALIZED_VARIANT = {"hgnc_id": "gene_symbol", "disease_id": "associated_phenotype"}


@dataclasses.dataclass
class Outcome:
    """One value of a report, compared with the truth.

    Attributes:
        field: The field, as `mrn`, `variants.zygosity` or
            `normalized.report_date`. The names in ENTITIES stand for a whole
            variant or clinical feature.
        result: correct, missed, extra or wrong.
        strict: Whether the value is also the same character for character.
        truth: The true value.
        found: Gentrex's value.
        command: The command that lost or added the value. None for a correct
            value, and for a normalized value whose source was already wrong.
        cause: For an extra variant or feature, distractor or hallucination.
        flagged: Whether gentrex extract named the value in not_in_pages.
            None for a value that it didn't check, such as a missed one.
    """

    field: str
    result: str
    strict: bool
    truth: Any
    found: Any
    command: str | None = None
    cause: str | None = None
    flagged: bool | None = None


def key(field: str, value: Any) -> Any:
    """Returns a value as the lenient match compares it.

    Text loses its case, spacing and trailing punctuation, and empty text
    counts as no value. A c. change also loses its transcript and the bases
    after del or dup, so c.5266dupC equals c.5266dup. A protein change loses
    its parentheses.
    """
    if not isinstance(value, str):
        return value
    text = "".join(unicodedata.normalize("NFKC", value).split()).casefold()
    text = text.rstrip(".,;:")
    name = field.rpartition(".")[2]
    if name == "hgvs_c":
        text = re.sub(r"^[a-z]{2}_\d+(\.\d+)?:", "", text)
        text = re.sub(r"(del|dup)[acgt]+(?=$|ins)", r"\1", text)
    if name == "hgvs_p":
        text = text.replace("(", "").replace(")", "")
    return text or None


def _result(field: str, truth: Any, found: Any) -> str:
    expected, got = key(field, truth), key(field, found)
    if expected == got:
        return "correct"
    if got is None:
        return "missed"
    return "extra" if expected is None else "wrong"


def _source(properties: dict[str, Any], field: str, values: dict[str, Any]) -> Any:
    """Returns the printed text that a field's true value is read from, if any.

    A field with allowed values is read from the wording in <field>_raw, and
    the kind of test from the test's name.
    """
    if field == "test_type":
        return values.get("test_name")
    if "enum" in properties.get(field, {}):
        return values.get(f"{field}_raw")
    return values.get(field)


def _change(variant: dict[str, Any]) -> tuple[str, str | None]:
    """Returns the field that holds a variant's DNA change, and the change."""
    if variant.get("hgvs_c"):
        return "hgvs_c", variant["hgvs_c"]
    return "dna_change_raw", variant.get("dna_change_raw")


def _identity(variant: dict[str, Any]) -> tuple[Any, Any]:
    return key("gene_symbol", variant.get("gene_symbol")), key(*_change(variant))


def _label(variant: dict[str, Any]) -> str:
    return " ".join(filter(None, (variant.get("gene_symbol"), _change(variant)[1])))


def _is_distractor(variant: dict[str, Any], distractors: list[dict[str, Any]]) -> bool:
    """Whether a distractor's text is the variant's change or starts with its gene."""
    field, change = _change(variant)
    gene = (variant.get("gene_symbol") or "").casefold()
    for distractor in distractors:
        text = distractor["text"]
        if change and key(field, text) == key(field, change):
            return True
        if gene and re.match(rf"{re.escape(gene)}\b", text.casefold()):
            return True
    return False


def compare(
    truth: dict[str, Any],
    report: dict[str, Any] | None,
    transcribed: list[str],
    kept: list[str],
    schema: dict[str, Any],
    hpo: bool = True,
    clinvar: bool = False,
) -> list[Outcome]:
    """Compares Gentrex's record of one report with the report's truth.

    A missed or wrong value is charged to gentrex transcribe if its text is
    not in the transcribed pages, to gentrex select if it is not in the kept
    pages, and else to gentrex extract. A normalized value is charged to
    gentrex normalize if the value it is read from was right.

    Args:
        truth: The report's truth file.
        report: The report's line of normalized.jsonl, or None if it has none.
        transcribed: The text of each page that gentrex transcribe wrote.
        kept: The text of each page that gentrex select kept.
        schema: The extraction schema.
        hpo: Whether gentrex normalize looked up HPO terms.
        clinvar: Whether gentrex normalize looked up ClinVar IDs.

    Returns:
        One outcome per value, variant and clinical feature.
    """
    data = (report or {}).get("data") or {}
    normalized = (report or {}).get("normalized") or {}
    stages = [
        ("transcribe", [check.page_lines(text) for text in transcribed]),
        ("select", [check.page_lines(text) for text in kept]),
    ]
    outcomes: list[Outcome] = []
    # None for a run from before gentrex extract checked the copied values.
    not_in_pages = (report or {}).get("not_in_pages")
    checked = {path for path, _ in extract_check.copied_values(data, schema)}

    def flagged(*paths: str) -> bool | None:
        """Whether a checked value at one of the paths is not in the pages."""
        if not_in_pages is None or not checked.intersection(paths):
            return None
        return any(path in not_in_pages for path in paths)

    def charge(text: Any) -> str:
        if isinstance(text, str):
            for command, pages in stages:
                if not any(check.locate(text, pages)):
                    return command
        return "extract"

    def add(field: str, expected: Any, found: Any, source: Any, path: str) -> str:
        """Adds a value of the record, and returns its result."""
        result = _result(field, expected, found)
        command = None
        if result in ("missed", "wrong"):
            command = charge(source)
        elif result == "extra":
            command = "extract"
        outcomes.append(
            Outcome(
                field,
                result,
                expected == found,
                expected,
                found,
                command,
                flagged=flagged(path),
            )
        )
        return result

    def add_normalized(field: str, expected: Any, found: Any, source_ok: bool) -> None:
        result = _result(field, expected, found)
        command = "normalize" if result != "correct" and source_ok else None
        outcomes.append(
            Outcome(
                f"normalized.{field}",
                result,
                expected == found,
                expected,
                found,
                command,
            )
        )

    properties = schema["properties"]
    record = truth["record"]
    results = {}
    for field, expected in record.items():
        if field not in ("variants", "patient_phenotypes", "overall_result_raw"):
            results[field] = add(
                field,
                expected,
                data.get(field),
                _source(properties, field, record),
                field,
            )
    for field in _NORMALIZED:
        add_normalized(
            field,
            truth["normalized"].get(field),
            normalized.get(field),
            results.get(field) == "correct",
        )

    # The statement is scored through its category, because there is no
    # single right place for the copied text to end.
    stated = key("", record.get("overall_result_raw"))
    copied = key("", data.get("overall_result_raw"))
    statement_ok = stated == copied or bool(
        stated and copied and (stated in copied or copied in stated)
    )
    result = _result(
        "", truth["normalized"].get("overall_result"), normalized.get("overall_result")
    )
    command = None
    if result != "correct":
        command = (
            "normalize" if statement_ok else charge(record.get("overall_result_raw"))
        )
    outcomes.append(
        Outcome(
            "normalized.overall_result",
            result,
            result == "correct",
            truth["normalized"].get("overall_result"),
            normalized.get("overall_result"),
            command,
        )
    )

    variant_properties = properties["variants"]["items"]["properties"]
    found_variants = list(enumerate(data.get("variants") or []))
    for expected, expected_ids in zip(
        record["variants"], truth["normalized"]["variants"], strict=True
    ):
        match = next(
            (f for f in found_variants if _identity(f[1]) == _identity(expected)),
            None,
        )
        if match is None:
            lost = _change(expected)[1] or expected.get("gene_symbol")
            outcomes.append(
                Outcome(
                    "variants", "missed", False, _label(expected), None, charge(lost)
                )
            )
            continue
        found_variants.remove(match)
        index, found = match
        outcomes.append(
            Outcome("variants", "correct", True, _label(expected), _label(found))
        )
        variant_results = {
            field: add(
                f"variants.{field}",
                value,
                found.get(field),
                _source(variant_properties, field, expected),
                f"variants[{index}].{field}",
            )
            for field, value in expected.items()
        }
        ids = (normalized.get("variants") or [])[index : index + 1]
        for field, source in _NORMALIZED_VARIANT.items():
            add_normalized(
                f"variants.{field}",
                expected_ids.get(field),
                ids[0].get(field) if ids else None,
                variant_results.get(source) == "correct",
            )
        # ClinVar is looked up by gene and c. change only.
        has_id = "clinvar_variation_id" in expected_ids
        if clinvar and has_id and expected.get("hgvs_c"):
            add_normalized(
                "variants.clinvar_variation_id",
                expected_ids["clinvar_variation_id"],
                ids[0].get("clinvar_variation_id") if ids else None,
                variant_results.get("gene_symbol") == "correct"
                and variant_results.get("hgvs_c") == "correct",
            )
    for index, extra in found_variants:
        cause = "hallucination"
        if _is_distractor(extra, truth["distractors"]):
            cause = "distractor"
        outcomes.append(
            Outcome(
                "variants",
                "extra",
                False,
                None,
                _label(extra),
                "extract",
                cause,
                flagged(
                    f"variants[{index}].gene_symbol",
                    f"variants[{index}].{_change(extra)[0]}",
                ),
            )
        )

    printed = {key("", d["text"]) for d in truth["distractors"]}
    found_features = list(enumerate(data.get("patient_phenotypes") or []))
    by_text: dict[int, int] = {}
    for number, expected in enumerate(record["patient_phenotypes"]):
        match = next(
            (
                f
                for f in found_features
                if key("", f[1].get("text")) == key("", expected["text"])
            ),
            None,
        )
        if match is None:
            outcomes.append(
                Outcome(
                    "patient_phenotypes",
                    "missed",
                    False,
                    expected["text"],
                    None,
                    charge(expected["text"]),
                )
            )
            continue
        found_features.remove(match)
        by_text[number] = match[0]
        outcomes.append(
            Outcome(
                "patient_phenotypes",
                "correct",
                expected["text"] == match[1].get("text"),
                expected["text"],
                match[1].get("text"),
                flagged=flagged(f"patient_phenotypes[{match[0]}].text"),
            )
        )
        add(
            "patient_phenotypes.present",
            expected.get("present"),
            match[1].get("present"),
            None,
            f"patient_phenotypes[{match[0]}].present",
        )
    for index, extra in found_features:
        cause = "distractor" if key("", extra.get("text")) in printed else None
        outcomes.append(
            Outcome(
                "patient_phenotypes",
                "extra",
                False,
                None,
                extra.get("text"),
                "extract",
                cause or "hallucination",
                flagged(f"patient_phenotypes[{index}].text"),
            )
        )

    if hpo:
        terms = normalized.get("patient_phenotypes") or []
        found_ids = [(i, (term or {}).get("hpo_id")) for i, term in enumerate(terms)]
        for number, expected in enumerate(truth["normalized"]["patient_phenotypes"]):
            match = next((f for f in found_ids if f[1] == expected["hpo_id"]), None)
            if match is not None:
                found_ids.remove(match)
            outcomes.append(
                Outcome(
                    "normalized.patient_phenotypes",
                    "correct" if match else "missed",
                    bool(match),
                    expected["hpo_id"],
                    match[1] if match else None,
                    None if match or number not in by_text else "normalize",
                )
            )
        outcomes += [
            Outcome(
                "normalized.patient_phenotypes",
                "extra",
                False,
                None,
                hpo_id,
                "normalize" if index in by_text.values() else None,
            )
            for index, hpo_id in found_ids
        ]
    return outcomes
