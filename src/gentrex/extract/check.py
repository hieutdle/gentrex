"""Check that the values copied from a report are in the pages that were read."""

import unicodedata
from collections.abc import Iterator
from collections.abc import Sequence
from typing import Any

# How many lines after a part of a wrapped value its next part may come.
_REACH = 3


def _letters(text: str) -> str:
    """Returns the letters and digits of a text, without case."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in folded if character.isalnum())


def _wrapped(value: str, text: str) -> bool:
    """Whether the words of a value run over nearby lines of a page, in order.

    A PDF's text is read line by line across the page. A table cell or a
    column that wraps therefore continues a few lines further down, after
    the text of its neighbours on the same line.
    """
    words = [word for word in map(_letters, value.split()) if word]
    lines = [_letters(line) for line in text.splitlines()]
    for start in range(len(lines)):
        done, last = 0, start
        for at in range(start, min(len(lines), start + _REACH * len(words) + 1)):
            if at - last > _REACH:
                break
            for end in range(len(words), done, -1):
                if "".join(words[done:end]) in lines[at]:
                    done, last = end, at
                    break
            if done in (0, len(words)):
                break
        if words and done == len(words):
            return True
    return False


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
    don't count. A value that wraps in a table cell or a column counts as
    found when its words run over nearby lines of one page.

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
        and not any(_wrapped(value, text) for text in texts)
    ]


def first_page(value: str, pages: Sequence[tuple[int, str]]) -> int | None:
    """Returns the first page that prints a value, or None if none does.

    Only letters and digits are compared, as in not_in_pages.

    Args:
        value: The value as the record holds it.
        pages: The number and the text of each page, in page order.
    """
    wanted = _letters(value)
    if not wanted:
        return None
    return next((number for number, text in pages if wanted in _letters(text)), None)
