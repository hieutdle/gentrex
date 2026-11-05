"""Facts about a patient that the patient's reports give, for every export."""

from collections.abc import Callable

from gentrex import records

_SEXES = {"f": "FEMALE", "female": "FEMALE", "m": "MALE", "male": "MALE"}


def sex(report: records.NormalizedReport) -> str | None:
    """Returns FEMALE or MALE for the sex that the report prints, else None."""
    return _SEXES.get(((report.data or {}).get("sex") or "").strip().casefold())


def date_of_birth(report: records.NormalizedReport) -> str | None:
    """Returns the report's date of birth from `gentrex normalize`, if any."""
    return (report.normalized or {}).get("date_of_birth")


def given(
    reports: list[records.NormalizedReport],
    value: Callable[[records.NormalizedReport], str | None],
) -> set[str]:
    """Returns the different values that the reports give, leaving out None."""
    return {v for report in reports if (v := value(report)) is not None}
