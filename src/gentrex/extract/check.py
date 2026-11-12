"""Check that the values copied from a report are in the pages that were read."""

import unicodedata
from collections.abc import Iterator
from typing import Any


def _letters(text: str) -> str:
    """Returns the letters and digits of a text, without case."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in folded if character.isalnum())


def copied_values(
    data: dict[str, Any], schema: dict[str, Any], path: str = ""
) -> Iterator[tuple[str, str]]:
    """Yields the path and the value of every text copied from the report.

    These are the text fields of the schema without a list of allowed values,
    also inside the variants and the clinical features. A path is the
    field's name, as `mrn` or `variants[0].hgvs_c`.
    """
    for name, field in schema.get("properties", {}).items():
        value = data.get(name)
        if isinstance(value, str) and "enum" not in field:
            yield f"{path}{name}", value
        elif isinstance(value, list) and "items" in field:
            for number, item in enumerate(value):
                if isinstance(item, dict):
                    yield from copied_values(
                        item, field["items"], f"{path}{name}[{number}]."
                    )


def not_in_pages(
    data: dict[str, Any], schema: dict[str, Any], texts: list[str]
) -> list[str]:
    """Returns the paths of the copied values that the pages don't have.

    Only letters and digits are compared, without case, so that line breaks,
    spacing and the marks that OCR puts around bold text and table cells
    don't count.

    Args:
        data: The record that the model returned.
        schema: The extraction schema.
        texts: The text of each page that the model read.
    """
    pages = _letters("".join(texts))
    return [
        path
        for path, value in copied_values(data, schema)
        if _letters(value) not in pages
    ]
