"""Yes/no questions about page text, scored from the first answer token."""

import dataclasses
import math

import openai
from openai.types.chat import chat_completion_token_logprob

from gentrex import llm


class MissingLogprobsError(Exception):
    """The server sent no logprobs, so no answer can be scored."""


@dataclasses.dataclass(frozen=True)
class SelectConfig:
    """The `select` settings.

    Attributes:
        model: Text model name on the server.
        instruction: Text sent before every page.
        questions: Yes/no question by name.
        keep_threshold: P(yes) at or above which a question keeps its page.
        timeout_seconds: Time allowed for one request.
        concurrency: Pages in flight at the same time.
    """

    model: str
    instruction: str
    questions: dict[str, str]
    keep_threshold: float
    timeout_seconds: float
    concurrency: int


def p_yes(
    first_token: chat_completion_token_logprob.ChatCompletionTokenLogprob,
) -> float:
    """Returns P(yes) from the alternatives for the first answer token.

    Alternatives that read the same once stripped and lowercased, such as
    "Yes" and " yes", are added up. The result is renormalised over yes and
    no; a side missing from the alternatives counts as 0.

    Raises:
        ValueError: The answer starts with neither yes nor no.
    """
    if first_token.token.strip().lower() not in ("yes", "no"):
        raise ValueError(f"answer starts with {first_token.token!r}")
    totals = {"yes": 0.0, "no": 0.0}
    for alternative in first_token.top_logprobs:
        word = alternative.token.strip().lower()
        if word in totals:
            totals[word] += math.exp(alternative.logprob)
    return totals["yes"] / (totals["yes"] + totals["no"])


class PageScorer:
    """Asks a text model yes/no questions about page text."""

    def __init__(self, config: SelectConfig, client: openai.OpenAI) -> None:
        self.config = config
        self._client = client

    def ask_or_error(self, text: str, question: str) -> float | Exception:
        """Returns P(yes) for `question` about `text`, or the error that prevented it.

        Raises:
            MissingLogprobsError: The server sent no logprobs.
            openai.OpenAIError: The endpoint is misconfigured or can't be
                reached (llm.result_or_error).
        """
        return llm.result_or_error(
            lambda: self._request(text, question), fatal=(MissingLogprobsError,)
        )

    def _request(self, text: str, question: str) -> float:
        # Page before question: a page's questions then share a cached prefix.
        prompt = (
            f"{self.config.instruction}\n\n<page>\n{text}\n</page>\n\n"
            f"{question}\nAnswer with Yes or No."
        )
        response = self._client.chat.completions.create(
            model=self.config.model,
            max_tokens=1,
            temperature=0,
            logprobs=True,
            top_logprobs=20,
            messages=[{"role": "user", "content": prompt}],
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        llm.count(response)
        logprobs = response.choices[0].logprobs
        if logprobs is None or not logprobs.content:
            raise MissingLogprobsError("the server sent no logprobs")
        return p_yes(logprobs.content[0])
