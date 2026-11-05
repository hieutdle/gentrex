"""Facts about a patient that the patient's reports give, for every export."""

import logging
from collections.abc import Callable

from gentrex import records

_SEXES = {"f": "FEMALE", "female": "FEMALE", "m": "MALE", "male": "MALE"}

_logger = logging.getLogger(__name__)


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


def agreed(
    reports: list[records.NormalizedReport],
    value: Callable[[records.NormalizedReport], str | None],
    what: str,
    export: str,
) -> str | None:
    """Returns the value that all reports giving one agree on, else None.

    Args:
        reports: The patient's reports.
        value: Gives a report's value, or None.
        what: The values as the warning names them, such as "dates of birth".
        export: What leaves them out, as the warning names it, such as
            "Phenopacket".
    """
    values = given(reports, value)
    if len(values) > 1:
        _logger.warning(
            "%s give different %s, so the %s leaves them out",
            ", ".join(report.file for report in reports),
            what,
            export,
        )
        return None
    return next(iter(values), None)
