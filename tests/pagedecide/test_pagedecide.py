import json
import math
import pathlib
from collections.abc import Callable
from unittest import mock

import openai
import pytest
from openai.types.chat import chat_completion
from openai.types.chat import chat_completion_token_logprob as token_logprob

from gentrex import records
from gentrex.pagedecide import run
from gentrex.pagedecide import score

_CONFIG = score.DecideConfig(
    model="fake",
    instruction="Read the page.",
    questions={
        "has_result": "Is there a result?",
        "has_phenotype": "Is there a phenotype?",
    },
    keep_threshold=0.5,
    timeout_seconds=1,
    concurrency=2,
)


def _first_token(
    probabilities: dict[str, float],
) -> token_logprob.ChatCompletionTokenLogprob:
    """Returns a first answer token: the likeliest of the given alternatives."""
    alternatives = [
        token_logprob.TopLogprob(token=token, logprob=math.log(probability))
        for token, probability in probabilities.items()
    ]
    chosen = max(alternatives, key=lambda alternative: alternative.logprob)
    return token_logprob.ChatCompletionTokenLogprob(
        token=chosen.token, logprob=chosen.logprob, top_logprobs=alternatives
    )


def _client(
    answer: Callable[[str], token_logprob.ChatCompletionTokenLogprob | None],
) -> mock.Mock:
    """Returns a client that answers a prompt with `answer(prompt)`.

    An answer of None is a response without logprobs.
    """

    def create(**kwargs) -> chat_completion.ChatCompletion:
        first = answer(kwargs["messages"][0]["content"])
        logprobs = (
            chat_completion.ChoiceLogprobs(content=[first])
            if first is not None
            else None
        )
        return chat_completion.ChatCompletion.model_construct(
            choices=[chat_completion.Choice.model_construct(logprobs=logprobs)]
        )

    client = mock.Mock()
    client.chat.completions.create.side_effect = create
    return client


def _run(
    tmp_path: pathlib.Path, client: mock.Mock, page: records.PageRecord
) -> tuple[list[str], dict]:
    """Runs stage 2 on one page; returns the failed files and the decision."""
    input_path = tmp_path / "pages.jsonl"
    input_path.write_text(page.to_json() + "\n")
    output = tmp_path / "decisions.jsonl"
    failed = run.run(input_path, output, score.PageScorer(_CONFIG, client))
    (line,) = output.read_text().splitlines()
    return failed, json.loads(line)


def _request(text: str, question: str) -> dict:
    """Returns the arguments of the request that asks `question` about `text`."""
    client = _client(lambda prompt: _first_token({"Yes": 1.0}))
    score.PageScorer(_CONFIG, client).ask(text, question)
    return client.chat.completions.create.call_args.kwargs


def test_p_yes_adds_up_spellings_and_ignores_other_tokens():
    """One answer has several tokens; tokens that are no answer do not count."""
    first = _first_token({"Yes": 0.5, " yes": 0.1, "No": 0.2, "The": 0.2})

    assert score.p_yes(first) == pytest.approx(0.6 / 0.8)


def test_first_token_other_than_yes_or_no_is_an_error_not_a_score():
    """A model that opens a thought channel first has not answered yet."""
    first = _first_token({"<|channel>": 0.9, "Yes": 0.1})

    with pytest.raises(ValueError, match="answer starts with"):
        score.p_yes(first)


def test_request_asks_for_the_first_token_odds_with_thinking_off():
    """With thinking on, the first token would open a thought, not answer."""
    request = _request("Result: negative", "Is there a result?")

    assert request["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert request["max_tokens"] == 1
    assert request["logprobs"] is True
    assert request["top_logprobs"] == 20


def test_page_comes_before_the_question():
    """The server can then reuse the page it read for the page's next question."""
    prompt = _request("PAGE TEXT", "Is there a result?")["messages"][0]["content"]

    assert prompt.index("PAGE TEXT") < prompt.index("Is there a result?")


def test_response_without_logprobs_stops_the_run(tmp_path):
    """Every request would fail the same way, so the run must not go on."""
    page = records.PageRecord("a.pdf", 1, "native", "Result: negative")

    with pytest.raises(score.MissingLogprobsError):
        _run(tmp_path, _client(lambda prompt: None), page)


@pytest.mark.parametrize(("p_yes", "keep"), [(0.51, True), (0.49, False)])
def test_threshold_decides_keep(tmp_path, p_yes, keep):
    """A page is kept from `keep_threshold` (0.5) up and dropped below it."""
    client = _client(lambda prompt: _first_token({"Yes": p_yes, "No": 1 - p_yes}))
    page = records.PageRecord("a.pdf", 1, "native", "Result: negative")

    _, decision = _run(tmp_path, client, page)

    assert decision["keep"] is keep


@pytest.mark.parametrize(
    ("page", "keep"),
    [
        pytest.param(records.PageRecord("a.pdf", 1, "scanned", ""), False, id="blank"),
        pytest.param(
            records.PageRecord("a.pdf", 1, "scanned", "", "OCR failed"),
            True,
            id="stage-1-error",
        ),
    ],
)
def test_pages_without_text_skip_the_model(tmp_path, page, keep):
    """A blank page holds nothing; a page stage 1 failed on must not be lost."""
    client = _client(lambda prompt: _first_token({"Yes": 1.0}))

    _, decision = _run(tmp_path, client, page)

    assert decision["keep"] is keep
    assert not client.chat.completions.create.called


def test_failed_question_costs_only_that_answer(tmp_path):
    """The page is kept: the unanswered question might have kept it."""

    def answer(prompt: str) -> token_logprob.ChatCompletionTokenLogprob:
        if "Is there a phenotype?" in prompt:
            raise openai.OpenAIError("server unavailable")
        return _first_token({"Yes": 0.1, "No": 0.9})

    page = records.PageRecord("a.pdf", 1, "native", "Methods")

    failed, decision = _run(tmp_path, _client(answer), page)

    assert failed == ["a.pdf"]
    assert decision["p_yes"] == {
        "has_result": pytest.approx(0.1),
        "has_phenotype": None,
    }
    assert decision["keep"] is True
    assert decision["error"] == "has_phenotype: OpenAIError: server unavailable"
