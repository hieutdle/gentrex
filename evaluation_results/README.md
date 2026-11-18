# Evaluation results

This folder holds the results of the evaluations in
[`evaluation/`](../evaluation/README.md).

| File | What it holds |
| --- | --- |
| `analysis.ipynb` | A notebook with the tables and figures of the benchmark results, in the order of a paper's results section |
| `walkthrough.ipynb` | A notebook that follows one benchmark report through Gentrex's four commands |
| `benchruns.py` | The tables and figures that the two notebooks show |
| `paper/` | The tables and figures as files, which `analysis.ipynb` writes |
| `hpo-matching.md` | [What the HPO matching of `gentrex normalize` got right](hpo-matching.md) on GSC+, and what that means for Gentrex |
| `hpo_normalization.md`, `hpo_normalization.json` | The tables and the details of that run |
| `mondo-matching.md` | [What the MONDO matching of `gentrex normalize` got right](mondo-matching.md) on ClinVar's condition names, and what that means for Gentrex |
| `mondo_normalization.md`, `mondo_normalization.json` | The tables and the details of that run |

## Read the notebooks

The notebooks read the runs in `results/gentrex-bench/` on your machine.
Make them first with `evaluation/local/run_pipeline.sh` or the Minerva job
([Evaluate Gentrex](../evaluation/README.md)), and then open a notebook from
the Gentrex folder:

```bash
uv run --group notebook jupyter lab evaluation_results/analysis.ipynb
```

`--group notebook` installs JupyterLab, pandas and matplotlib on the first
run. In JupyterLab, choose Run, then Run All Cells. Both notebooks are saved
without outputs, because their numbers come from your own runs.

`analysis.ipynb` compares the newest run of each setup on one split. A
setup is a copy of the reports, with or without `gentrex select`. Set
`SPLIT` to `"dev"` or `"test"` in its second cell.

| Section | Tables and figures |
| --- | --- |
| Data and setup | The reports of the split, and the software, GPUs, models and reference data of the runs |
| The whole pipeline | Report accuracy, value F1 and the other main numbers of each setup with 95% intervals, each setup's difference to the native PDFs, and how many stated values each command lost |
| Each command on its own | Each command measured on what the command before gave it: how well OCR read each copy, which pages `gentrex select` kept and what other thresholds would keep, what `gentrex extract` got right of the values that reached it with the F1 and the kinds of error of every field, each kind of variant and how each classification was written, and the standard values and HPO terms of `gentrex normalize` |
| Kinds of report | Report accuracy by kind of test, result, length, challenge and template |
| Checks for a person | How well each check of Gentrex flags wrong values and wrong reports |
| Dev, test and repeated runs | Dev next to test, the held-out templates, and how far runs with the same settings differ |
| Time and cost | Seconds, tokens and GPU-hours per report |
| Appendix | Every field in numbers, the wrong reports and the errors |

The first output gives the main numbers and what they say in a few
sentences. Runs that were scored with `--label` count as a setup of their
own, as a run with another model.

Each table is also written to `evaluation_results/paper/<split>/` as CSV and
LaTeX, and each figure as PDF and PNG. Set `bench.EXPORT` to `None` in the
second cell to write none.

`walkthrough.ipynb` takes one report from the PDF to the scored record. It
shows the report's pages with the ones that `gentrex select` kept, and one
table with each field as the report states it, as `gentrex extract` copied
it and as `gentrex normalize` standardized it. A figure boxes each copied
value on the page, blue if it is right and red if it isn't.

The scores are those of each run's `scores.json`. The notebook itself
computes the difference between two runs, with the scorer's
`score.difference`, the intervals of fields and groups of reports, and the
accuracy of `gentrex normalize` on values that were extracted right.

A run that an older scorer wrote lacks numbers that the tables need, so the
notebooks leave it out and name it. Score it again with
`gentrex-bench/scorer/score.py`.

Some tables quote values from the reports. After a run on real reports,
clear the outputs before you save or share a notebook.
