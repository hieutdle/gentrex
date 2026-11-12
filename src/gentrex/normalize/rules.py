"""Rules that turn report wording into dates and fixed categories."""

import datetime
import re
from typing import Any

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%b-%Y",
    "%d-%B-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%B %d, %Y",
    "%b %d, %Y",
)
# A date with slashes fits one of these. Where both fit, as for 03/04/2020,
# the setting normalize.day_first decides.
_MONTH_FIRST = "%m/%d/%Y"
_DAY_FIRST = "%d/%m/%Y"
# A time of day after the date, as in "29-Jul-25 08:27".
_TIME = re.compile(r",?[ T]\s*\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]m)?$", re.IGNORECASE)

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

# The result of a karyotype or array, as in "Normal male karyotype" or
# "NORMAL MICROARRAY RESULT". With "ab" before it, the result is abnormal.
_NORMAL = (
    r"normal (?:(?:male|female|snp|chromosomal) ){0,2}"
    r"(?:karyotype|microarray|array|chromosome)s?\b"
)
# Wording that states each result category. In a result statement, the
# category whose wording comes first decides. "No" or "not" up to six words
# before "variants" comes before any "pathogenic variants" it negates, as in
# "No pathogenic or likely pathogenic variants were identified.", and the same
# goes for an abnormal karyotype or array.
_RESULT_WORDING = {
    "positive": (
        r"\bpositive\b|\b(?:likely )?pathogenic (?:variant|mutation)s?\b"
        rf"|\bab{_NORMAL}"
    ),
    "negative": (
        rf"\bnegative\b|\bnot a carrier\b|\b{_NORMAL}"
        rf"|\bnot?(?: [\w,-]+){{0,6}} (?:(?:variant|mutation)s?\b|ab{_NORMAL})"
    ),
    "uncertain": r"\buncertain\b|\bvus\b|\bunknown significance\b",
    "carrier": r"\bcarrier\b",
    "inconclusive": r"\binconclusive\b|\bindeterminate\b",
}

# Categories that both the wording and the classifications can give, so a
# difference between the two is a real disagreement.
_COMPARABLE = {"positive", "negative", "uncertain"}


def parse_date(raw: str | None, day_first: bool = False) -> str | None:
    """Returns a printed date as YYYY-MM-DD, or None if it has no known format.

    A time of day after the date is ignored. A year of two digits is read as
    the latest year that doesn't put the date in the future.

    Args:
        raw: The date as printed.
        day_first: Whether a date with slashes that can be read both ways,
            as 03/04/2020, has the day first.
    """
    text = _TIME.sub("", (raw or "").strip())
    slashed = (_DAY_FIRST, _MONTH_FIRST) if day_first else (_MONTH_FIRST, _DAY_FIRST)
    formats = [*_DATE_FORMATS, *slashed]
    # A date that starts with its year always has all four digits of it.
    formats += [f.replace("%Y", "%y") for f in formats if not f.startswith("%Y")]
    for date_format in formats:
        try:
            parsed = datetime.datetime.strptime(text, date_format).date()
        except ValueError:
            continue
        if "%y" in date_format and parsed > datetime.date.today():
            parsed = parsed.replace(year=parsed.year - 100)
        return parsed.isoformat()
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
    # In "POSITIVE: CARRIER", positive only says that something was found.
    if {"carrier", "positive"} <= {category for _, category in found}:
        return "carrier"
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
    raw: str | None, variants: list[dict[str, Any]], test_name: str | None = None
) -> dict[str, str | bool | None]:
    """Returns the report's result category, its source and any disagreement.

    The laboratory's result statement decides. The classifications of the
    primary findings decide only when the statement names no category. On a
    carrier screen, which its test name calls one, a positive statement means
    that the patient is a carrier.

    Args:
        raw: The report's result statement (`overall_result_raw`).
        variants: The report's variants, as Gentrex extracted them.
        test_name: The name of the test (`test_name`), or None.

    Returns:
        `overall_result`: positive, negative, uncertain, carrier,
        inconclusive or None. `overall_result_basis`: "wording",
        "variants" or None. `overall_result_conflict`: whether the
        statement and the classifications give different categories.
    """
    stated = _stated_category(raw)
    if stated == "positive" and "carrier" in (test_name or "").casefold():
        stated = "carrier"
    derived = _derived_category(variants)
    category, basis = (stated, "wording") if stated else (derived, "variants")
    return {
        "overall_result": category,
        "overall_result_basis": basis if category else None,
        "overall_result_conflict": (
            stated in _COMPARABLE and derived in _COMPARABLE and stated != derived
        ),
    }
