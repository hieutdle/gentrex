# Evaluation results

This folder holds the results of the evaluations in
[`evaluation/`](../evaluation/README.md).

| File | What it holds |
| --- | --- |
| `walkthrough.ipynb` | A notebook that follows one benchmark report through Gentrex's four commands, and shows what each command reads and writes |
| `analysis.ipynb` | A notebook that compares the benchmark runs and goes through one run in detail: accuracy, errors, time and tokens |
| `benchruns.py` | What the two notebooks share: reading the runs, and the plots |
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
run. In JupyterLab, choose Run, then Run All Cells.

Start with `walkthrough.ipynb` if you don't know the four commands yet. It
takes one report from the PDF page to the scored record: the text that
`gentrex transcribe` read, the pages that `gentrex select` kept, the record
of `gentrex extract`, the standard values of `gentrex normalize`, and the
values that the scorer counted as wrong. It is saved without outputs,
because it reads the run folders of your own runs.

`analysis.ipynb` has these parts:

| Part | What it shows |
| --- | --- |
| Runs | Every scored run with its setup, which is its copy of the reports and whether it ran `gentrex select`. The software, GPUs, models and reference data of the runs, and what the reports of the split are made of. |
| Accuracy | Report accuracy, variant F1 and the other main numbers of the newest run of each setup, with 95% intervals. The accuracy on templates that only the test split has, and dev next to test. |
| Repeated runs | How far report accuracy moves between runs of the same setup |
| Scanned and faxed copies | What each copy costs against the native PDFs, with the pages sent to OCR and the values lost there |
| With and without `gentrex select` | Accuracy, lost values, tokens and time of a copy's run with `gentrex select` and its run without |
| Fields, commands, time | The fields that differ most between setups, the errors charged to each command, and seconds, tokens and GPU-hours |
| One run | Errors per report, missed and extra variants by cause, the wrong reports, patient identification, each kind of report and every field with intervals, `gentrex normalize` on values that were extracted right, the check of copied values, and every value that isn't right |

Every score comes from a run's `scores.json`, so it agrees with the run's
`scores.md`. The notebook itself computes the difference between two runs,
with the scorer's `score.difference`, the intervals in the tables of groups
and fields, and the accuracy of `gentrex normalize` on values that were
extracted right.

Some tables quote values from the reports. After a run on real reports,
clear the outputs before you save or share a notebook.
