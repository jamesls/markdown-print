from __future__ import annotations

import subprocess
from collections.abc import Callable

from pygments.styles import get_style_by_name
from rich.align import Align
from rich.console import Console, RenderableType
from rich.pager import Pager
from rich.theme import Theme

from mdp.markdown import LeftAlignedMarkdown


def _run_less(args: list[str], content: str) -> None:
    """Default command runner that invokes subprocess.run."""
    subprocess.run(args, input=content, text=True)


class LessPager(Pager):
    """Pager that uses less with ANSI color support."""

    def __init__(
        self, runner: Callable[[list[str], str], None] | None = None
    ) -> None:
        self._runner = runner if runner is not None else _run_less

    def show(self, content: str) -> None:
        self._runner(["less", "-R"], content)


__all__ = ["render_markdown", "LeftAlignedMarkdown"]

DEFAULT_CODE_THEME = "nord-darker"
DEFAULT_WIDTH = 100
_code_background = get_style_by_name(DEFAULT_CODE_THEME).background_color
DEFAULT_CONSOLE_THEME = Theme({
    "markdown.code": f"#81a1c1 on {_code_background}",
    "markdown.hr": "#4c566a",
    "markdown.item.number": "#4c566a bold",
})


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
    renderable: RenderableType = markdown
    if center:
        renderable = Align.center(markdown, width=width, pad=False)
    if page:
        actual_pager = pager if pager is not None else LessPager()
        with console.pager(pager=actual_pager, styles=True):
            console.print(renderable)
    else:
        console.print(renderable)
