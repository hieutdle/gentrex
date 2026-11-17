"""Tests of the model servers that a command starts and stops."""

import pathlib
import sys
import urllib.request

import pytest

from gentrex import servers

_SERVER = """#!{python}
import http.server
import sys


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


http.server.HTTPServer(("localhost", int(sys.argv[2])), Handler).serve_forever()
"""


def _script(tmp_path: pathlib.Path, text: str) -> pathlib.Path:
    path = tmp_path / "serve.py"
    path.write_text(text.format(python=sys.executable))
    path.chmod(0o755)
    return path


def test_the_model_server_is_stopped_after_its_command(tmp_path, monkeypatch):
    """The next command's model needs the GPU that this one holds."""
    monkeypatch.setattr(servers, "_POLL_SECONDS", 0.1)

    with servers.served(_script(tmp_path, _SERVER), "some/model") as base_url:
        with urllib.request.urlopen(f"{base_url}/models") as response:
            assert response.status == 200

    with pytest.raises(OSError):
        urllib.request.urlopen(f"{base_url}/models", timeout=1)


def test_a_server_that_fails_to_start_ends_the_run(tmp_path, monkeypatch):
    """A job must not wait until its time limit for a server that crashed."""
    monkeypatch.setattr(servers, "_POLL_SECONDS", 0.1)
    script = _script(tmp_path, "#!{python}\nraise SystemExit(1)\n")

    with pytest.raises(RuntimeError, match="ended before some/model was ready"):
        with servers.served(script, "some/model"):
            pass
