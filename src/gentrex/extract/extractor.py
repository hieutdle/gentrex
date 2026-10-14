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

    def extract(self, pages: list[records.PageRecord]) -> dict[str, Any]:
        """Returns the record of the report that `pages` come from.

        Connection, rate-limit and 5xx errors are retried.

        Args:
            pages: The pages to send, in page order.

        Raises:
            ValueError: The answer was cut off at max_tokens, or is not JSON.
            openai.OpenAIError: The request still failed, or cannot succeed.
        """
        return llm.with_retries(lambda: self._request(pages))

    def extract_or_error(
        self, pages: list[records.PageRecord]
    ) -> dict[str, Any] | Exception:
        """Returns the record of the report, or the error that prevented it.

        Raises:
            openai.OpenAIError: The endpoint is misconfigured (llm.FATAL_ERRORS).
        """
        try:
            return self.extract(pages)
        except llm.FATAL_ERRORS:
            raise
        except Exception as exc:  # One report's failure must not cost the others.
            return exc

    def _request(self, pages: list[records.PageRecord]) -> dict[str, Any]:
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
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise ValueError(f"answer cut off at max_tokens ({self.config.max_tokens})")
        return json.loads(choice.message.content or "")
