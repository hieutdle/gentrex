"""The four commands of gentrex run and the scorer together, on the example reports.

A model server that answers with each report's truth stands in for the
models, so whatever the scorer finds wrong was lost between the commands,
by the rules of gentrex normalize or by the scorer itself.
"""

import contextlib
import http.server
import json
import pathlib
import sys
import threading

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "gentrex-bench" / "scorer"))

import score  # noqa: E402

from gentrex import cli  # noqa: E402
from gentrex import servers  # noqa: E402

_EXAMPLES = pathlib.Path(__file__).parents[1] / "gentrex-bench" / "examples"
_YES = {"token": "Yes", "logprob": -0.01, "bytes": None}


def _truths() -> dict[str, dict]:
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(_EXAMPLES.glob("*.json"))
    }


class _TruthServer(http.server.BaseHTTPRequestHandler):
    """Answers gentrex select with Yes and gentrex extract with the truth."""

    records: dict[str, dict] = {}

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        text = request["messages"][-1]["content"]
        choice: dict = {"index": 0, "finish_reason": "stop"}
        if "response_format" in request:
            # Every page of a synthetic report prints its case ID.
            record = next(r for case, r in self.records.items() if case in text)
            choice["message"] = {"role": "assistant", "content": json.dumps(record)}
        else:
            choice["message"] = {"role": "assistant", "content": "Yes"}
            choice["logprobs"] = {"content": [{**_YES, "top_logprobs": [_YES]}]}
        body = json.dumps(
            {
                "id": "1",
                "object": "chat.completion",
                "created": 0,
                "model": request["model"],
                "choices": [choice],
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def _reference_files(folder: pathlib.Path, truths: dict[str, dict]) -> dict:
    """Writes an HGNC set and a MONDO release with the examples' genes and diseases.

    Returns:
        The settings of gentrex normalize that name the two files.
    """
    genes = {}
    diseases = {}
    for truth in truths.values():
        for printed, ids in zip(
            truth["record"]["variants"], truth["normalized"]["variants"], strict=True
        ):
            if ids.get("hgnc_id"):
                old = printed["gene_symbol"]
                genes[ids["hgnc_id"]] = (
                    ids["gene_symbol"],
                    old if old != ids["gene_symbol"] else "",
                )
            if ids.get("disease_id"):
                diseases[ids["disease_id"]] = printed["associated_phenotype"]
    hgnc = folder / "hgnc.txt"
    hgnc.write_text(
        "hgnc_id\tsymbol\talias_symbol\tprev_symbol\n"
        + "".join(f"{i}\t{s}\t\t{old}\n" for i, (s, old) in genes.items()),
        encoding="utf-8",
    )
    mondo = folder / "mondo.json"
    nodes = [
        {
            "id": f"http://purl.obolibrary.org/obo/{mondo_id.replace(':', '_')}",
            "type": "CLASS",
            "lbl": label,
        }
        for mondo_id, label in diseases.items()
    ]
    mondo.write_text(json.dumps({"graphs": [{"nodes": nodes}]}), encoding="utf-8")
    return {"hgnc_path": str(hgnc), "mondo_path": str(mondo)}


def _is_challenge(error: dict, truth: dict) -> bool:
    """Whether the truth's own record can't get the value right, by design.

    The karyotype example prints dates such as 7.12.2024 with the day first,
    as the unusual_date_format tag once did. gentrex normalize reads them
    month first, as US laboratories print them. A result cell that says
    "See Note" names no category.
    """
    field = error["field"].removeprefix("normalized.")
    if field == "overall_result":
        return truth["record"]["overall_result_raw"] == "See Note"
    dated = field == "date_of_birth" or field.endswith("_date")
    return dated and "unusual_date_format" in truth["case"]["tags"]


def test_records_that_match_the_truth_score_as_right(tmp_path, monkeypatch):
    truths = _truths()
    pdfs = tmp_path / "pdf"
    pdfs.mkdir()
    for name in truths:
        (pdfs / f"{name}.pdf").symlink_to(_EXAMPLES / f"{name}.pdf")
    settings = tmp_path / "settings.yaml"
    settings.write_text(
        yaml.safe_dump({"normalize": _reference_files(tmp_path, truths)}),
        encoding="utf-8",
    )
    _TruthServer.records = {t["case"]["case_id"]: t["record"] for t in truths.values()}
    # Requests arrive 16 at a time, more than the default queue of 5 holds.
    http.server.ThreadingHTTPServer.request_queue_size = 64
    server = http.server.ThreadingHTTPServer(("localhost", 0), _TruthServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    @contextlib.contextmanager
    def served(script, model):
        yield f"http://localhost:{server.server_port}" if script else None

    monkeypatch.setattr(servers, "served", served)
    # gentrex run sets the servers' addresses, which must not outlive the test.
    for variable in ("GENTREX_OCR_BASE_URL", "GENTREX_LLM_BASE_URL"):
        monkeypatch.setenv(variable, "")
    monkeypatch.chdir(tmp_path)
    arguments = ["run", "--input-dir", str(pdfs), "--serve", "serve.sh", "--no-hpo"]
    args = cli._build_parser().parse_args([*arguments, "--settings", str(settings)])

    try:
        assert args.func(args) == 0
    finally:
        server.shutdown()
    scores, errors = score.score(
        _EXAMPLES, pathlib.Path("results/normalize/latest"), "all"
    )

    unexpected = [e for e in errors if not _is_challenge(e, truths[e["report"]])]
    assert unexpected == [], json.dumps(unexpected, indent=1)
    assert scores["reports"] == len(truths)
