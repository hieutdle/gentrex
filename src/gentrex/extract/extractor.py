"""One request per report, answered in JSON that follows the extraction schema."""

import copy
import dataclasses
import json
from typing import Any

import openai

from gentrex import llm
from gentrex import records


@dataclasses.dataclass(frozen=True)
class ExtractConfig:
    """The `extract` settings and the extraction schema.

    Attributes:
        model: Text model name on the server.
        instruction: System message, sent before the schema.
        max_tokens: Cap on one report's answer.
        timeout_seconds: Time allowed for one request.
        concurrency: Reports in flight at the same time.
        schema: JSON Schema of one report's record.
    """

    model: str
    instruction: str
    max_tokens: int
    timeout_seconds: float
    concurrency: int
    schema: dict[str, Any]


@dataclasses.dataclass(frozen=True)
class Answer:
    """The model's record of one report, with the tokens of its request.

    Attributes:
        data: The record, following the extraction schema.
        prompt_tokens: Tokens that the model read, or None if the server
            doesn't count them.
        completion_tokens: Tokens that the model wrote, or None.
    """

    data: dict[str, Any]
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def _require_all(node: dict[str, Any]) -> None:
    """Marks every property in `node`, nested ones too, as required.

    The types allow null, so a field the report does not state comes back
    null instead of missing.
    """
    if "properties" in node:
        node["required"] = list(node["properties"])
        for child in node["properties"].values():
            _require_all(child)
    if "items" in node:
        _require_all(node["items"])


class ReportExtractor:
    """Asks a text model for the record of one report."""

    def __init__(self, config: ExtractConfig, client: openai.OpenAI) -> None:
        self.config = config
        self._client = client
        # The model reads the descriptions; the server enforces the schema.
        self._system = (
            f"{config.instruction}\n\n{json.dumps(config.schema, ensure_ascii=False)}"
        )
        self._answer_schema = copy.deepcopy(config.schema)
        _require_all(self._answer_schema)

    def extract_or_error(self, pages: list[records.PageRecord]) -> Answer | Exception:
        """Returns the record of the report, or the error that prevented it.

        An answer that was cut off at max_tokens or is not a JSON object is
        an error.

        Args:
            pages: The pages to send, in page order.

        Raises:
            openai.OpenAIError: The endpoint is misconfigured or can't be
                reached (llm.result_or_error).
        """
        return llm.result_or_error(lambda: self._request(pages))

    def _request(self, pages: list[records.PageRecord]) -> Answer:
        text = "\n\n".join(f"--- PAGE {page.page} ---\n{page.text}" for page in pages)
        response = self._client.chat.completions.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=0,
            messages=[
                {"role": "system", "content": self._system},
                {"role": "user", "content": text},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "report", "schema": self._answer_schema},
            },
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        llm.count(response)
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise ValueError(f"answer cut off at max_tokens ({self.config.max_tokens})")
        data = json.loads(choice.message.content or "")
        if not isinstance(data, dict):
            raise ValueError("answer is not a JSON object")
        usage = response.usage
        return Answer(
            data,
            usage.prompt_tokens if usage else None,
            usage.completion_tokens if usage else None,
        )
