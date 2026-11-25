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


def test_gentrex_run_reuses_server_for_consecutive_steps_with_same_model(
    tmp_path, monkeypatch
):
    """Select and extract share one Gemma 4 server instead of loading it twice."""
    import contextlib

    from gentrex import cli
    from gentrex import runs

    monkeypatch.chdir(tmp_path)
    served_models: list[str] = []

    @contextlib.contextmanager
    def fake_served(script, model):
        if script is not None:
            served_models.append(model)
            yield f"http://localhost:9999/{len(served_models)}/v1"
        else:
            yield None

    def fake_cmd(name):
        def _run(args):
            folder = tmp_path / "results" / name / "20261125-100000"
            folder.mkdir(parents=True, exist_ok=True)
            latest = runs.latest(name)
            if latest.is_symlink():
                latest.unlink()
            latest.symlink_to(folder.name)
            return 0

        return _run

    monkeypatch.setattr(cli.servers, "served", fake_served)
    monkeypatch.setattr(cli, "_run_transcribe", fake_cmd("transcribe"))
    monkeypatch.setattr(cli, "_run_select", fake_cmd("select"))
    monkeypatch.setattr(cli, "_run_extract", fake_cmd("extract"))
    monkeypatch.setattr(cli, "_run_normalize", fake_cmd("normalize"))

    args = cli._build_parser().parse_args(
        ["run", "--input-dir", str(tmp_path), "--serve", str(tmp_path / "serve.sh")]
    )
    assert cli._run_all(args) == 0
    assert served_models == [
        "lightonai/LightOnOCR-3-4B",
        "google/gemma-4-26B-A4B-it",
    ]
