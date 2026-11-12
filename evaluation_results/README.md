# Evaluation results

This folder holds the results of the evaluations in
[`evaluation/`](../evaluation/README.md).

| File | What it holds |
| --- | --- |
| `pipeline.ipynb` | A notebook that follows one benchmark report through Gentrex's four commands, and shows the accuracy, time and tokens of a benchmark run, as a whole and for each command |
| `hpo-matching.md` | [What the HPO matching of `gentrex normalize` got right](hpo-matching.md) on GSC+, and what that means for Gentrex |
| `hpo_normalization.md`, `hpo_normalization.json` | The tables and the details of that run |

## Read the pipeline notebook

The notebook reads the runs in `results/gentrex-bench/` on your machine.
Make one first with `evaluation/local/run_pipeline.sh` or the Minerva job
([Evaluate Gentrex](../evaluation/README.md)), and then open the notebook
from the Gentrex folder:

```bash
uv run --group notebook jupyter lab evaluation_results/pipeline.ipynb
```

`--group notebook` installs JupyterLab, pandas and matplotlib on the first
run. In JupyterLab, choose Run, then Run All Cells.

The notebook has these parts:

| Part | What it shows |
| --- | --- |
| The runs | Every scored run with its copy of the reports, its report accuracy and its GPU-hours |
| Walk through the pipeline | One report from the PDF page to the scored record: the text that `gentrex transcribe` read, the pages that `gentrex select` kept, the record of `gentrex extract` and the standard values of `gentrex normalize` |
| The whole pipeline | Report accuracy, variant F1 and the other main numbers of one run, with their 95% intervals |
| Each command | The values that each command lost, got wrong or added, its time, requests and tokens, and what it did to the pages |
| Each field | The accuracy of every field of the record |
| Each kind of report | Report accuracy by challenge tag, template, test and result |
| Compare runs | All runs side by side, the difference between two runs with its interval, and accuracy against GPU-hours |
| The errors of the run | Every value that isn't right, with the truth and what Gentrex wrote |

It is saved without outputs, because its numbers come from your own runs. It
computes no scores itself, so they are those of each run's `scores.md`.

Some tables quote values from the reports. After a run on real reports,
clear the outputs before you save or share the notebook.
