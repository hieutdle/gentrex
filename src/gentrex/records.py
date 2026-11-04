"""Records passed between commands, one JSON object per line."""

import dataclasses
import json
from typing import Any
from typing import Literal

PageSource = Literal["native", "scanned"]


@dataclasses.dataclass
class PageRecord:
    """One PDF page after `gentrex transcribe`.

    Attributes:
        file: PDF file name; identifies the report in the output of every command.
        page: 1-indexed page number.
        source: How `text` was produced.
        text: Page text; empty for a scanned page that was not transcribed.
        error: Why OCR produced no text, if it failed.
    """

    file: str
    page: int
    source: PageSource
    text: str = ""
    error: str | None = None

    def to_json(self) -> str:
        """Returns the record as one JSONL line, without the newline."""
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False)


@dataclasses.dataclass
class PageDecision:
    """One page after `gentrex select`.

    Attributes:
        file: PDF file name.
        page: 1-indexed page number.
        p_yes: Probability that the answer is yes, by question name; None for
            a question that was not asked or failed.
        keep: Whether `gentrex extract` reads the page.
        error: Why questions failed, or the page's error from `gentrex transcribe`.
    """

    file: str
    page: int
    p_yes: dict[str, float | None]
    keep: bool
    error: str | None = None

    def to_json(self) -> str:
        """Returns the record as one JSONL line, without the newline."""
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False)


@dataclasses.dataclass
class ReportExtraction:
    """One report after `gentrex extract`.

    With `data` set and no `error`, the record is complete; with both set,
    pages are missing from it; with `data` None, the report failed.

    Attributes:
        file: PDF file name.
        pages: Pages whose text was sent to the model, in page order.
        data: The record the model returned, following the extraction schema;
            None if there was no request or it failed.
        error: Pages left out for an error from `gentrex transcribe`, and why
            the request failed.
    """

    file: str
    pages: list[int]
    data: dict[str, Any] | None
    error: str | None = None

    def to_json(self) -> str:
        """Returns the record as one JSONL line, without the newline."""
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False)


@dataclasses.dataclass
class NormalizedReport:
    """One report after `gentrex normalize`.

    Attributes:
        file: PDF file name.
        pages: Pages whose text `gentrex extract` sent to the model, in page order.
        data: The record from `gentrex extract`, unchanged; None if it failed.
        normalized: Standard values derived from `data`; None if there is no
            data or normalizing it failed.
        error: The error from `gentrex extract`, and why normalizing failed.
    """

    file: str
    pages: list[int]
    data: dict[str, Any] | None
    normalized: dict[str, Any] | None
    error: str | None = None

    def to_json(self) -> str:
        """Returns the record as one JSONL line, without the newline."""
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False)
