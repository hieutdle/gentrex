"""Records passed between stages, one JSON object per line."""

import dataclasses
import json
from typing import Any
from typing import Literal

PageSource = Literal["native", "scanned"]


@dataclasses.dataclass
class PageRecord:
    """One PDF page after stage 1.

    Attributes:
        file: PDF file name; identifies the report in every stage.
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
    """One page after stage 2.

    Attributes:
        file: PDF file name.
        page: 1-indexed page number.
        p_yes: Probability that the answer is yes, by question name; None for
            a question that was not asked or failed.
        keep: Whether later stages read the page.
        error: Why questions failed, or the page's stage 1 error.
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
    """One report after stage 3.

    With `data` set and no `error`, the record is complete; with both set,
    pages are missing from it; with `data` None, the report failed.

    Attributes:
        file: PDF file name.
        pages: Pages whose text was sent to the model, in page order.
        data: The record the model returned, following the extraction schema;
            None if there was no request or it failed.
        error: Pages left out for a stage 1 error, and why the request failed.
    """

    file: str
    pages: list[int]
    data: dict[str, Any] | None
    error: str | None = None

    def to_json(self) -> str:
        """Returns the record as one JSONL line, without the newline."""
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False)
