"""Model servers that are started for one command and stopped after it."""

import contextlib
import logging
import os
import pathlib
import signal
import socket
import subprocess
import time
import urllib.request
from collections.abc import Iterator

_POLL_SECONDS = 5.0

_logger = logging.getLogger(__name__)


def _answers(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5):
            return True
    except OSError:
        return False


@contextlib.contextmanager
def served(script: pathlib.Path | None, model: str) -> Iterator[str | None]:
    """Starts the model server of one command, and stops it afterwards.

    The script gets the model's name and a free port, and must serve the
    model there until it is stopped.

    Args:
        script: The script that starts a model server, or None to use the
            servers that are already running.
        model: The model's name in settings.yaml.

    Yields:
        The server's address, or None without a script.

    Raises:
        RuntimeError: The script ended before the server answered.
    """
    if script is None:
        yield None
        return
    with socket.socket() as probe:
        probe.bind(("", 0))
        port = probe.getsockname()[1]
    base_url = f"http://localhost:{port}/v1"
    start = time.perf_counter()
    # In a process group of its own, so that stopping reaches its children.
    server = subprocess.Popen(
        [str(script.resolve()), model, str(port)], start_new_session=True
    )
    try:
        _logger.info("waiting for %s at %s", model, base_url)
        while not _answers(f"{base_url}/models"):
            if server.poll() is not None:
                raise RuntimeError(f"{script} ended before {model} was ready")
            time.sleep(_POLL_SECONDS)
        _logger.info("%s is ready after %.0f s", model, time.perf_counter() - start)
        yield base_url
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(server.pid, signal.SIGTERM)
        server.wait()
