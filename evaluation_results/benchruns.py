"""What the two notebooks of this folder share: the scored runs and the plots.

A scored run is a folder under results/gentrex-bench/ with the scores.json
and errors.jsonl that gentrex-bench/run.py wrote.
"""

# The notebook group provides matplotlib and pandas.
# pyright: reportMissingImports=false

import json
import math
import pathlib
import sys
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import ticker

ROOT = pathlib.Path(__file__).parents[1]
RESULTS = ROOT / "results"
COMMANDS = ("transcribe", "select", "extract", "normalize")
COPIES = ("native", "scan", "fax", "mixed", "image")
_SURFACE, _BLUE, _INK, _MUTED, _GRID = (
    "#fcfcfb",
    "#2a78d6",
    "#0b0b0b",
    "#52514e",
    "#e5e4e0",
)

sys.path.insert(0, str(ROOT / "gentrex-bench" / "scorer"))

import score  # noqa: E402

# The fields that decide whether a report counts as correct.
CLINICAL = score.compare.CLINICAL

plt.rcParams.update(
    {
        "figure.facecolor": _SURFACE,
        "axes.facecolor": _SURFACE,
        "axes.edgecolor": _GRID,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": _GRID,
        "grid.linewidth": 0.8,
        "axes.titlelocation": "left",
        "axes.titlesize": 11,
        "axes.labelcolor": _MUTED,
        "text.color": _INK,
        "xtick.color": _MUTED,
        "ytick.color": _INK,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
    }
)


def load_runs() -> dict[str, dict[str, Any]]:
    """Returns the scores.json of every scored run, by folder name, oldest first."""
    return {
        path.parent.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(RESULTS.glob("gentrex-bench/*/scores.json"))
    }


def copy_of(run: dict[str, Any]) -> str:
    """Returns the copy of the reports that a run read, such as native or scan."""
    return pathlib.Path(run["pdfs"]).name


def setup_of(run: dict[str, Any]) -> str:
    """Returns a run's setup: its copy, and whether it skipped gentrex select."""
    skipped = "" if "select" in run["runs"] else ", no select"
    return f"{copy_of(run)}{skipped}"


def newest(runs: dict[str, dict[str, Any]], split: str) -> dict[str, str]:
    """Returns the folder of the newest run of each setup on a split.

    The setups come in the order native, scan, fax, mixed, image, and each
    copy's run without gentrex select after its run with it.
    """
    found = {setup_of(run): name for name, run in runs.items() if run["split"] == split}

    def order(setup: str) -> tuple[int, str]:
        copy = setup.partition(",")[0]
        return (COPIES.index(copy) if copy in COPIES else len(COPIES), setup)

    return {setup: found[setup] for setup in sorted(found, key=order)}


def repeats(runs: dict[str, dict[str, Any]], split: str) -> dict[str, list[str]]:
    """Returns the folders of all runs of each setup on a split, oldest first."""
    found: dict[str, list[str]] = {}
    for name, run in runs.items():
        if run["split"] == split:
            found.setdefault(setup_of(run), []).append(name)
    return {setup: found[setup] for setup in newest(runs, split)}


def wilson(correct: float, total: float) -> dict[str, float | None]:
    """Returns a share with its 95% Wilson interval, shaped like a main number.

    The scorer gives intervals only for the main numbers. This one serves
    the tables of fields and groups, and it also holds for a few reports.
    """
    if not total:
        return {"value": None, "low": None, "high": None}
    z = 1.96
    share = correct / total
    middle = share + z * z / (2 * total)
    spread = z * math.sqrt(share * (1 - share) / total + z * z / (4 * total * total))
    scale = 1 + z * z / total
    low, high = (middle - spread) / scale, (middle + spread) / scale
    return {"value": share, "low": max(0.0, low), "high": min(1.0, high)}


def run_folder(run: dict[str, Any], command: str) -> pathlib.Path | None:
    """Returns the run folder of a command of a scored run.

    Returns:
        The folder, or None if the run skipped the command. Scores copied
        from another machine still name that machine's folders, so the
        folder of the same name under results/ stands in for a missing one.
    """
    record = run["runs"].get(command)
    if record is None:
        return None
    folder = pathlib.Path(record["path"])
    return folder if folder.exists() else RESULTS / command / folder.name


def records(run: dict[str, Any], command: str, name: str) -> list[dict[str, Any]]:
    """Returns the lines of a JSONL file in a command's run folder.

    Returns:
        The records, or none if the run skipped the command or the file is
        not on this machine.
    """
    folder = run_folder(run, command)
    if folder is None or not (folder / name).is_file():
        return []
    lines = (folder / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def errors(name: str) -> pd.DataFrame:
    """Returns every value of a scored run that isn't right, one row each."""
    path = RESULTS / "gentrex-bench" / name / "errors.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    columns = [
        "report",
        "field",
        "result",
        "truth",
        "found",
        "command",
        "cause",
        "flagged",
    ]
    return pd.DataFrame([json.loads(line) for line in lines], columns=columns)


def percent(number: float | None) -> str:
    return "n/a" if number is None else f"{number:.1%}"


def with_interval(number: dict[str, Any]) -> str:
    """Formats a main number with its 95% interval."""
    if number["value"] is None:
        return "n/a"
    return (
        f"{percent(number['value'])}"
        f" ({percent(number['low'])} to {percent(number['high'])})"
    )


def difference(first: dict[str, Any], second: dict[str, Any]) -> str:
    """Formats the second run's report accuracy minus the first's.

    The two runs are compared on the reports that both scored, with a 95%
    interval. An interval that includes 0 means the runs can't be told apart.
    """
    gain = score.difference(first, second)
    if not gain["reports"]:
        return "no shared reports"
    return (
        f"{gain['value']:+.1%} ({gain['low']:+.1%} to {gain['high']:+.1%})"
        f" on {gain['reports']} reports"
    )


def _share_axis(ax) -> None:
    ax.set_xlim(0, 1.12)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(1))
    ax.grid(axis="y", visible=False)
    ax.invert_yaxis()


def bars(numbers: Any, title: str, label, shares: bool = False) -> None:
    """Draws numbers as horizontal bars in the given order, each with its value.

    Args:
        numbers: A pandas Series of the numbers, by their labels.
        title: The title of the plot.
        label: Formats a number for the end of its bar.
        shares: Whether the numbers are shares, on an axis from 0% to 100%.
    """
    if numbers.empty:
        print(f"{title}: nothing to show")
        return
    _, ax = plt.subplots(figsize=(7.5, 0.3 * len(numbers) + 1))
    ax.barh(numbers.index, numbers, height=0.55, color=_BLUE)
    longest = 1 if shares else max(numbers.max(), 1e-9)
    for position, number in enumerate(numbers):
        ax.text(
            number + 0.012 * longest, position, label(number), va="center", fontsize=9
        )
    if shares:
        _share_axis(ax)
    else:
        ax.set_xlim(0, longest * 1.12)
        ax.grid(axis="y", visible=False)
        ax.invert_yaxis()
    ax.set_title(title)
    plt.show()


def intervals(numbers: dict[str, dict[str, Any]], title: str) -> None:
    """Draws shares with their 95% intervals, one row per label."""
    if not numbers:
        print(f"{title}: nothing to show")
        return
    _, ax = plt.subplots(figsize=(7.5, 0.4 * len(numbers) + 1))
    for position, number in enumerate(numbers.values()):
        if number["value"] is None:
            continue
        ax.hlines(position, number["low"], number["high"], color=_BLUE, linewidth=2)
        ax.plot(
            number["value"],
            position,
            "o",
            color=_BLUE,
            markersize=9,
            markeredgecolor=_SURFACE,
            markeredgewidth=2,
            clip_on=False,
            zorder=3,
        )
        ax.text(
            number["high"] + 0.015,
            position,
            percent(number["value"]),
            va="center",
            fontsize=9,
        )
    ax.set_yticks(range(len(numbers)), list(numbers))
    _share_axis(ax)
    ax.set_ylim(len(numbers) - 0.4, -0.6)
    # Room on the left, so that a marker at 0% doesn't sit on the labels.
    ax.set_xlim(-0.03, 1.12)
    ax.set_title(title)
    plt.show()


def points(numbers: dict[str, tuple[float, float]], title: str, xlabel: str) -> None:
    """Draws one labelled point per setup, with a share on the vertical axis.

    Setups whose points would cover each other share one point and label.
    """
    if not numbers:
        print(f"{title}: nothing to show")
        return
    widest = max(x for x, _ in numbers.values()) or 1
    places: dict[tuple[float, float], list[str]] = {}
    for label, (x, share) in numbers.items():
        near = (round(x / widest, 1), round(share, 1))
        places.setdefault(near, []).append(label)
    merged = {" / ".join(labels): numbers[labels[0]] for labels in places.values()}
    _, ax = plt.subplots(figsize=(7.5, 4))
    for label, (x, share) in merged.items():
        ax.plot(
            x,
            share,
            "o",
            color=_BLUE,
            markersize=9,
            markeredgecolor=_SURFACE,
            markeredgewidth=2,
            clip_on=False,
            zorder=3,
        )
        ax.annotate(
            label,
            (x, share),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
        )
    ax.set_xlim(0, widest * 1.5)
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(1))
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    plt.show()
