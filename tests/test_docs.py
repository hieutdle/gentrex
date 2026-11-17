"""The docs name commands, settings and pages that exist.

A renamed option, setting or heading otherwise stays in the docs until a
reader runs into it.
"""

import collections
import pathlib
import re
import shlex

import pytest

from gentrex import cli
from gentrex import config

_ROOT = pathlib.Path(__file__).parents[1]
_PAGES = sorted(
    path
    for pattern in (
        "README.md",
        ".github/*.md",
        "docs/**/*.md",
        "evaluation/*.md",
        "evaluation_results/*.md",
        "gentrex-bench/**/*.md",
    )
    for path in _ROOT.glob(pattern)
)
_FENCED = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_SETTING = re.compile(rf"`((?:{'|'.join(config.load_settings())})\.[a-z_.]+)`")
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)|<img src=\"([^\"]+)\"")
_HEADING = re.compile(r"^#+ (.+)$", re.MULTILINE)
_SHELL_OPERATORS = {"|", ">", ">>", "&&", "||", ";", "<"}
_COMMANDS = {"transcribe", "select", "extract", "normalize", "load", "export", "run"}


def _text(page: pathlib.Path) -> str:
    return page.read_text(encoding="utf-8")


def _commands(text: str) -> list[list[str]]:
    """Returns the arguments of every gentrex command in the page's code blocks."""
    blocks = "\n".join(_FENCED.findall(text)).replace("\\\n", " ")
    found = []
    for line in blocks.splitlines():
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError:
            continue
        for i, token in enumerate(tokens):
            # "gentrex" is also the name of databases and their users.
            if pathlib.Path(token).name == "gentrex" and (
                set(tokens[i + 1 : i + 2]) & _COMMANDS
            ):
                arguments = tokens[i + 1 :]
                end = next(
                    (j for j, a in enumerate(arguments) if a in _SHELL_OPERATORS),
                    len(arguments),
                )
                found.append(arguments[:end])
                break
    return found


def _anchors(text: str) -> set[str]:
    """Returns the anchors that GitHub gives the page's headings."""
    seen: collections.Counter[str] = collections.Counter()
    anchors = set()
    for heading in _HEADING.findall(_FENCED.sub("", text)):
        slug = re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")
        anchors.add(f"{slug}-{seen[slug]}" if seen[slug] else slug)
        seen[slug] += 1
    return anchors


@pytest.mark.parametrize("page", _PAGES, ids=lambda p: str(p.relative_to(_ROOT)))
def test_the_commands_of_a_page_are_ones_that_gentrex_takes(page):
    parser = cli._build_parser()
    for arguments in _commands(_text(page)):
        try:
            parser.parse_args(arguments)
        except SystemExit:
            pytest.fail(f"gentrex doesn't take: gentrex {shlex.join(arguments)}")


@pytest.mark.parametrize("page", _PAGES, ids=lambda p: str(p.relative_to(_ROOT)))
def test_the_settings_of_a_page_are_in_settings_yaml(page):
    for name in _SETTING.findall(_text(page)):
        if name.endswith((".lsf", ".md", ".yaml", ".py")):
            continue
        settings = config.load_settings()
        for key in name.split("."):
            assert isinstance(settings, dict) and key in settings, name
            settings = settings[key]


@pytest.mark.parametrize("page", _PAGES, ids=lambda p: str(p.relative_to(_ROOT)))
def test_the_links_of_a_page_lead_to_a_file_and_a_heading(page):
    for link, image in _LINK.findall(_FENCED.sub("", _text(page))):
        target = link or image
        if re.match(r"[a-z]+:", target):
            continue
        path, _, anchor = target.partition("#")
        file = (page.parent / path).resolve() if path else page
        assert file.exists(), f"{target} leads nowhere"
        if anchor and file.suffix == ".md":
            assert anchor in _anchors(_text(file)), f"{target} has no such heading"
