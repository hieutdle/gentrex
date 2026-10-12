"""Records passed between stages, one JSON object per line."""

import dataclasses
import json
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
