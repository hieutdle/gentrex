# Evaluation results

This folder holds the results of the evaluations in
[`evaluation/`](../evaluation/README.md).

| File | What it holds |
| --- | --- |
| `benchruns.py` | The tables and figures that [`presentation.ipynb`](../presentation.ipynb) shows |
| `hpo-matching.md` | [What the HPO matching of `gentrex normalize` got right](hpo-matching.md) on GSC+, and what that means for Gentrex |
| `hpo_normalization.md`, `hpo_normalization.json` | The tables and the details of that run |
| `mondo-matching.md` | [What the MONDO matching of `gentrex normalize` got right](mondo-matching.md) on ClinVar's condition names, and what that means for Gentrex |
| `mondo_normalization.md`, `mondo_normalization.json` | The tables and the details of that run |

## Read the presentation

[`presentation.ipynb`](../presentation.ipynb), in the Gentrex folder, holds
the text, tables and figures of the paper in the order of the paper, with a
supplement that follows one report through every command. The abstract and
the sentences under the main numbers are written from the scores, so they
change with the runs. The notebook reads the runs in
`results/gentrex-bench/`, so make them first with `evaluation/local/run_pipeline.sh` or the Minerva job
([Evaluate Gentrex](../evaluation/README.md)). Then open it from the Gentrex
folder and choose Run, Run All Cells:

```bash
uv run --group notebook jupyter lab presentation.ipynb
```

`--group notebook` installs JupyterLab, pandas and matplotlib on the first
run. The tables are also written to `figures/` as CSV and LaTeX, and the
figures as PDF and PNG, such as `figures/table-main.tex`. This makes slides with the code hidden:

```bash
uv run --group notebook jupyter nbconvert --to slides --execute --no-input presentation.ipynb
```

A run that an older scorer wrote lacks numbers that the figures need, so
the notebook leaves it out and names it. Score it again with
`gentrex-bench/scorer/score.py`.

Some tables quote values from the reports. After a run on real reports,
clear the outputs before you save or share the notebook.
