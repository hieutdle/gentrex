"""Tests of gentrex-bench/run.py, which runs and scores the benchmark."""

import json
import pathlib
import sys
import urllib.request

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "gentrex-bench"))

import run  # noqa: E402

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
    monkeypatch.setattr(run, "_POLL_SECONDS", 0.1)

    with run.served(_script(tmp_path, _SERVER), "some/model") as base_url:
        with urllib.request.urlopen(f"{base_url}/models") as response:
            assert response.status == 200

    with pytest.raises(OSError):
        urllib.request.urlopen(f"{base_url}/models", timeout=1)


def test_a_server_that_fails_to_start_ends_the_run(tmp_path, monkeypatch):
    """A job must not wait until its time limit for a server that crashed."""
    monkeypatch.setattr(run, "_POLL_SECONDS", 0.1)
    script = _script(tmp_path, "#!{python}\nraise SystemExit(1)\n")

    with pytest.raises(RuntimeError, match="ended before some/model was ready"):
        with run.served(script, "some/model"):
            pass


def test_only_the_pdfs_of_the_split_are_read(tmp_path):
    """Tuning runs must not spend GPU time on the test reports."""
    for name, split in (("SYN-0001", "dev"), ("SYN-0101", "test")):
        truth = tmp_path / "truth" / f"{name}.json"
        truth.parent.mkdir(exist_ok=True)
        truth.write_text(json.dumps({"case": {"split": split}}))
        pdf = tmp_path / "pdf" / "scan" / f"{name}.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(b"%PDF")

    linked = run.link_pdfs(tmp_path, "scan", "dev", tmp_path / "out")

    assert linked == 1
    assert [p.name for p in (tmp_path / "out").iterdir()] == ["SYN-0001.pdf"]
    assert (tmp_path / "out" / "SYN-0001.pdf").read_bytes() == b"%PDF"
