from __future__ import annotations

import subprocess
import re
from collections.abc import Callable
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.token import Token
from pygments.styles import get_style_by_name
from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.pager import Pager
from rich.text import Text
from rich.theme import Theme

from mdp.markdown import LeftAlignedMarkdown


def _run_less(args: list[str], content: str) -> None:
    """Default command runner that invokes subprocess.run."""
    subprocess.run(args, input=content, text=True)


class LessPager(Pager):
    """Pager that uses less with ANSI color support."""

    def __init__(
        self,
        runner: Callable[[list[str], str], None] | None = None,
        prompt: str | None = None,
    ) -> None:
        self._runner = runner if runner is not None else _run_less
        self._prompt = prompt

    def show(self, content: str) -> None:
        args = ["less", "-R"]
        if self._prompt is not None:
            total_lines = content.count("\n")
            prompt = self._prompt.replace("{total_lines}", str(total_lines))
            args.extend(["-P", prompt])
        self._runner(args, content)


__all__ = ["render_markdown", "LeftAlignedMarkdown"]

DEFAULT_CODE_THEME = "nord-darker"
DEFAULT_WIDTH = 100
AVERAGE_READING_SPEED_WPM = 200
_code_background = get_style_by_name(DEFAULT_CODE_THEME).background_color
DEFAULT_CONSOLE_THEME = Theme({
    "markdown.code": f"#81a1c1 on {_code_background}",
    "markdown.hr": "#4c566a",
    "markdown.item.number": "#4c566a bold",
})
WORD_PATTERN = re.compile(r"[^\W_]+(?:[-'’][^\W_]+)*", re.UNICODE)
MARKDOWN_PARSER = MarkdownIt().enable("strikethrough").enable("table")


@dataclass(frozen=True)
class DocumentStats:
    word_count: int
    reading_time_minutes: int


def _flatten_tokens(tokens: list[Token]) -> list[Token]:
    flattened_tokens: list[Token] = []
    for token in tokens:
        is_fence = token.type == "fence"
        is_image = token.tag == "img"
        if token.children and not (is_fence or is_image):
            flattened_tokens.extend(_flatten_tokens(token.children))
        else:
            flattened_tokens.append(token)
    return flattened_tokens


def _iter_countable_text_fragments(markdown_text: str) -> list[str]:
    tokens = MARKDOWN_PARSER.parse(markdown_text)
    text_fragments: list[str] = []

    for token in _flatten_tokens(tokens):
        if token.type in {"fence", "code_block", "html_block", "html_inline"}:
            continue
        if token.type in {"text", "code_inline"} and token.content:
            text_fragments.append(token.content)
            continue
        if token.type == "image" and token.content:
            text_fragments.append(token.content)
            continue
        if token.type in {"softbreak", "hardbreak"}:
            text_fragments.append(" ")

    return text_fragments


def _get_document_stats(markdown_text: str) -> DocumentStats:
    readable_text = " ".join(_iter_countable_text_fragments(markdown_text))
    word_count = len(WORD_PATTERN.findall(readable_text))
    reading_time_minutes = (
        max(1, -(-word_count // AVERAGE_READING_SPEED_WPM))
        if word_count
        else 0
    )
    return DocumentStats(
        word_count=word_count,
        reading_time_minutes=reading_time_minutes,
    )


def _build_footer(stats: DocumentStats) -> Text:
    word_label = "word" if stats.word_count == 1 else "words"
    reading_label = (
        f"~{stats.reading_time_minutes} min read"
        if stats.word_count
        else "~0 min read"
    )
    return Text(
        f"{stats.word_count:,} {word_label} • {reading_label}",
        style="dim",
    )


def _build_pager_prompt(stats: DocumentStats) -> str:
    word_label = "word" if stats.word_count == 1 else "words"
    reading_label = (
        f"~{stats.reading_time_minutes} min read"
        if stats.word_count
        else "~0 min read"
    )
    return (
        f"{stats.word_count:,} {word_label} | {reading_label}"
        " | line %lt-%lb of {total_lines}?Pb (%Pb\\%)."
    )


def render_markdown(
    text: str,
    *,
    width: int = DEFAULT_WIDTH,
    center: bool = False,
    page: bool = False,
    code_theme: str = DEFAULT_CODE_THEME,
    hyperlinks: bool = True,
    pager: Pager | None = None,
) -> None:
    """Render markdown text to the console.

    Args:
        text: Markdown string to render.
        width: Maximum width for rendering.
        center: Center output horizontally in terminal.
        page: Send output through a pager (less).
        code_theme: Pygments theme for code blocks.
        hyperlinks: Render clickable hyperlinks.
        pager: Custom pager instance (defaults to LessPager when page=True).
    """
    console = Console(
        width=None if center else width,
        theme=DEFAULT_CONSOLE_THEME,
        force_terminal=True if page else None,
    )
    markdown = LeftAlignedMarkdown(
        text,
        code_theme=code_theme,
        hyperlinks=hyperlinks,
    )
    stats = _get_document_stats(text)
    footer = _build_footer(stats)
    renderable: RenderableType = Group(markdown, Text(""), footer)
    if center:
        renderable = Align.center(renderable, width=width, pad=False)
    if page:
        actual_pager = (
            pager
            if pager is not None
            else LessPager(prompt=_build_pager_prompt(stats))
        )
        with console.pager(pager=actual_pager, styles=True):
            console.print(renderable)
    else:
        console.print(renderable)
