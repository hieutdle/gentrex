"""Rules that turn report wording into dates and fixed categories."""

import datetime
import re
from typing import Any

# Dates with slashes are read month first, as US laboratories print them.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d-%b-%Y",
    "%d-%B-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
)

_SPECIMEN_PATTERNS = {
    "buccal_swab": r"\b(?:buccal|cheek\s+swab|oracollect)\b",
    "whole_blood": r"\b(?:whole\s+)?blood\b",
    "saliva": r"\bsaliva\b",
    "bone_marrow": r"\bbone\s+marrow\b",
    "amniotic_fluid": r"\bamniotic\s+fluid\b",
    "chorionic_villus": r"\bchorionic\s+villi?(?:us)?\b",
    "fibroblast": r"\bfibroblasts?\b",
    "tissue": r"\b(?:fresh|frozen|tumou?r|normal)?\s*tissue\b",
}

# Wording that states each result category. In a result statement, the
# category whose wording comes first decides. "No" or "not" up to six words
# before "variants" comes before any "pathogenic variants" it negates, as in
# "No pathogenic or likely pathogenic variants were identified."
_RESULT_WORDING = {
    "positive": r"\bpositive\b|\b(?:likely )?pathogenic (?:variant|mutation)s?\b",
    "negative": (
        r"\bnegative\b|\bnot a carrier\b"
        r"|\bnot?(?: [\w,-]+){0,6} (?:variant|mutation)s?\b"
    ),
    "uncertain": r"\buncertain\b|\bvus\b|\bunknown significance\b",
    "carrier": r"\bcarrier\b",
    "inconclusive": r"\binconclusive\b",
}

# Categories that both the wording and the classifications can give, so a
# difference between the two is a real disagreement.
_COMPARABLE = {"positive", "negative", "uncertain"}


def parse_date(raw: str | None) -> str | None:
    """Returns a printed date as YYYY-MM-DD, or None if it has no known format."""
    for date_format in _DATE_FORMATS:
        try:
            parsed = datetime.datetime.strptime((raw or "").strip(), date_format)
        except ValueError:
            continue
        return parsed.date().isoformat()
    return None


def specimen_category(raw: str | None) -> str | None:
    """Returns the specimen's category, or None unless exactly one rule matches."""
    matches = [
        category
        for category, pattern in _SPECIMEN_PATTERNS.items()
        if re.search(pattern, raw or "", re.IGNORECASE)
    ]
    return matches[0] if len(matches) == 1 else None


def _stated_category(raw: str | None) -> str | None:
    """Returns the category the result statement names, ignoring secondary results."""
    primary = " ".join((raw or "").casefold().split()).split("secondary", 1)[0]
    found = [
        (match.start(), category)
        for category, pattern in _RESULT_WORDING.items()
        if (match := re.search(pattern, primary))
    ]
    return min(found)[1] if found else None


def _derived_category(variants: list[dict[str, Any]]) -> str | None:
    """Returns the category the primary findings' classifications imply."""
    classes = {
        variant.get("classification")
        for variant in variants
        if variant.get("is_secondary_finding") is not True
    } - {None}
    if classes & {"pathogenic", "likely_pathogenic"}:
        return "positive"
    if "uncertain_significance" in classes:
        return "uncertain"
    if classes and classes <= {"benign", "likely_benign"}:
        return "negative"
    return None


def overall_result(
    raw: str | None, variants: list[dict[str, Any]]
) -> dict[str, str | bool | None]:
    """Returns the report's result category, its source and any disagreement.

    The laboratory's result statement decides. The classifications of the
    primary findings decide only when the statement names no category.

    Args:
        raw: The report's result statement (`overall_result_raw`).
        variants: The report's variants, as Gentrex extracted them.

    Returns:
        `overall_result`: positive, negative, uncertain, carrier,
        inconclusive or None. `overall_result_basis`: "wording",
        "variants" or None. `overall_result_conflict`: whether the
        statement and the classifications give different categories.
    """
    stated = _stated_category(raw)
    derived = _derived_category(variants)
    category, basis = (stated, "wording") if stated else (derived, "variants")
    return {
        "overall_result": category,
        "overall_result_basis": basis if category else None,
        "overall_result_conflict": (
            stated in _COMPARABLE and derived in _COMPARABLE and stated != derived
        ),
    }
