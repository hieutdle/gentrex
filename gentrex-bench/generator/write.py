"""Write the free text of each report with a language model, from its case card.

The model runs on any OpenAI-compatible server, such as vLLM, like the models
of Gentrex itself. It returns the text as JSON, which fill.py puts into the
report's template.
"""

import datetime
import hashlib
import json
import pathlib

import openai

from gentrex import llm

PROMPT_PATH = pathlib.Path(__file__).with_name("prompt.md")
_PARAGRAPHS = {"type": "array", "items": {"type": "string"}}
_LISTS = ("interpretation", "variant_details", "recommendations", "patient_summary")
_CONDITION = ("characteristics", "incidence", "inheritance", "penetrance", "cause")
PROSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "interpretation": _PARAGRAPHS,
        "variant_details": _PARAGRAPHS,
        "condition": {
            "type": "object",
            "properties": {key: {"type": "string"} for key in _CONDITION},
            "required": list(_CONDITION),
            "additionalProperties": False,
        },
        "recommendations": _PARAGRAPHS,
        "patient_summary": _PARAGRAPHS,
    },
    "required": [
        "summary",
        "interpretation",
        "variant_details",
        "condition",
        "recommendations",
        "patient_summary",
    ],
    "additionalProperties": False,
}


class WriteError(Exception):
    """The model returned no usable text."""


def paragraphs(prose: dict) -> dict:
    """Returns the prose with each list field that is one string split up.

    Some servers don't hold the model to the schema, and it then writes a
    list of paragraphs as one string, which a template would print letter by
    letter.
    """
    return {
        key: [part.strip() for part in value.split("\n\n") if part.strip()]
        if key in _LISTS and isinstance(value, str)
        else value
        for key, value in prose.items()
    }


def problems(case: dict, prose: dict) -> list[str]:
    """Returns what is wrong with the model's prose for a case; empty if nothing."""
    found = []
    if set(prose) != set(PROSE_SCHEMA["required"]):
        found.append(f"the fields are {sorted(prose)}")
    elif wrong := [
        key
        for key in _LISTS
        if not isinstance(prose[key], list)
        or not all(isinstance(part, str) for part in prose[key])
    ]:
        found.append(f"{', '.join(wrong)} must be lists of paragraphs")
    elif len(prose["variant_details"]) != len(case["record"]["variants"]):
        found.append(
            f"{len(prose['variant_details'])} variant details for "
            f"{len(case['record']['variants'])} variants"
        )
    elif not prose["interpretation"] or not prose["recommendations"]:
        found.append("the interpretation or the recommendations are empty")
    return found


def write(client: openai.OpenAI, case: dict, model: str, max_tokens: int) -> dict:
    """Asks the model for the free text of one report and returns the response record.

    Args:
        client: A client for the model server.
        case: A case from sample.py.
        model: The model that writes the text, as the server names it.
        max_tokens: The longest answer allowed, in tokens.

    Returns:
        The prose, with the model that wrote it, the token counts, the
        prompt's checksum and the date.

    Raises:
        WriteError: The answer was cut off or isn't the JSON asked for.
        openai.OpenAIError: The request failed after the retries.
    """
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    response = llm.with_retries(
        lambda: client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(case["card"], indent=2)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "report_text", "schema": PROSE_SCHEMA},
            },
        )
    )
    choice = response.choices[0]
    if choice.finish_reason != "stop":
        raise WriteError(f"{case['case_id']}: stopped with {choice.finish_reason}")
    try:
        prose = json.loads(choice.message.content or "")
    except json.JSONDecodeError as exc:
        raise WriteError(f"{case['case_id']}: the answer isn't JSON") from exc
    if not isinstance(prose, dict):
        raise WriteError(f"{case['case_id']}: the answer isn't a JSON object")
    prose = paragraphs(prose)
    if found := problems(case, prose):
        raise WriteError(f"{case['case_id']}: {'; '.join(found)}")
    usage = response.usage
    return {
        "case_id": case["case_id"],
        "model": response.model,
        "input_tokens": usage.prompt_tokens if usage else None,
        "output_tokens": usage.completion_tokens if usage else None,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "date": datetime.date.today().isoformat(),
        "prose": prose,
    }
