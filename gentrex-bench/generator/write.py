"""Write each report as HTML with a language model, from its case card.

The model runs on any OpenAI-compatible server, such as vLLM, like the models
of Gentrex itself.
"""

import datetime
import hashlib
import json
import pathlib
import re

import openai

from gentrex import llm

PROMPT_PATH = pathlib.Path(__file__).with_name("prompt.md")
_HTML_BLOCK = re.compile(r"```html\s*\n(.*?)\n```", re.DOTALL)


class WriteError(Exception):
    """The model returned no usable report."""


def write(client: openai.OpenAI, case: dict, model: str, max_tokens: int) -> dict:
    """Asks the model for one report and returns the response record.

    Args:
        client: A client for the model server.
        case: A case from sample.py.
        model: The model that writes the report, as the server names it.
        max_tokens: The longest answer allowed, in tokens.

    Returns:
        The HTML, with the model that wrote it, the token counts, the prompt's
        checksum and the date.

    Raises:
        WriteError: The answer was cut off or has no HTML block.
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
        )
    )
    choice = response.choices[0]
    if choice.finish_reason != "stop":
        raise WriteError(f"{case['case_id']}: stopped with {choice.finish_reason}")
    match = _HTML_BLOCK.search(choice.message.content or "")
    if not match:
        raise WriteError(f"{case['case_id']}: the answer has no html block")
    usage = response.usage
    return {
        "case_id": case["case_id"],
        "model": response.model,
        "input_tokens": usage.prompt_tokens if usage else None,
        "output_tokens": usage.completion_tokens if usage else None,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "date": datetime.date.today().isoformat(),
        "html": match[1],
    }
