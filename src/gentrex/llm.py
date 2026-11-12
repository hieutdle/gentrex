"""Client and retries for OpenAI-compatible model servers."""

import logging
import threading
import time
from collections.abc import Callable

import openai
from openai.types import chat

_logger = logging.getLogger(__name__)

# A shared model server answers 502 while another model loads, which can take
# a minute. Waits before the second, third and fourth attempt.
_RETRY_WAITS_SECONDS = (5, 20, 60)

_RETRYABLE_ERRORS = (
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
)

# Misconfiguration: every later call would fail the same way.
FATAL_ERRORS = (
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
)

_usage_lock = threading.Lock()
_usage = {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0}


def make_client(base_url: str, api_key: str, timeout_seconds: float) -> openai.OpenAI:
    """Returns a client for the server at `base_url`."""
    return openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout_seconds,
        max_retries=0,  # with_retries is the only retry layer.
    )


def with_retries[T](call: Callable[[], T]) -> T:
    """Returns the result of `call`, retrying connection, rate-limit and 5xx errors.

    Raises:
        openai.OpenAIError: The call still failed, or cannot succeed.
    """
    for wait in _RETRY_WAITS_SECONDS:
        try:
            return call()
        except _RETRYABLE_ERRORS as exc:
            _logger.warning(
                "model call failed (%s); retrying in %ds",
                type(exc).__name__,
                wait,
            )
            time.sleep(wait)
    return call()


def count(response: chat.ChatCompletion) -> None:
    """Adds an answer and its token counts to the totals that usage() returns."""
    with _usage_lock:
        _usage["requests"] += 1
        if response.usage:
            _usage["prompt_tokens"] += response.usage.prompt_tokens
            _usage["completion_tokens"] += response.usage.completion_tokens


def usage() -> dict[str, int]:
    """Returns the answers this process got so far, and their tokens."""
    with _usage_lock:
        return dict(_usage)
